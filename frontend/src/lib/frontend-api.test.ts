import { afterEach, describe, expect, it, vi } from "vitest";

import { AUTH_STORAGE_KEY } from "./auth";
import {
  CURRENT_SESSION_KEY,
  STORAGE_KEY,
} from "./chat-workspace/constants";
import {
  FrontendApiError,
  authenticatedJson,
  getResponseErrorMessage,
} from "./frontend-api";

function stubBrowserState(authValue?: string) {
  const storage = new Map<string, string>();

  if (authValue !== undefined) {
    storage.set(AUTH_STORAGE_KEY, authValue);
  }

  const localStorageMock = {
    getItem: vi.fn((key: string) => storage.get(key) ?? null),
    removeItem: vi.fn((key: string) => {
      storage.delete(key);
    }),
    setItem: vi.fn((key: string, value: string) => {
      storage.set(key, value);
    }),
  };
  const location = {
    href: "http://localhost/",
    pathname: "/",
  };

  vi.stubGlobal("localStorage", localStorageMock);
  vi.stubGlobal("window", { location });

  return { localStorageMock, location };
}

describe("frontend api helpers", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("adds the auth header and no-store cache for JSON requests", async () => {
    stubBrowserState(
      JSON.stringify({
        access_token: "token-1",
        token_type: "bearer",
      }),
    );
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('{"success":true}', {
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await authenticatedJson<{ success: boolean }>(
      "/api/example",
      { method: "GET" },
      { fallbackMessage: "fallback" },
    );
    const [, init] = fetchMock.mock.calls[0];
    const headers = init.headers as Headers;

    expect(result.success).toBe(true);
    expect(headers.get("Authorization")).toBe("Bearer token-1");
    expect(init.cache).toBe("no-store");
  });

  it("clears persisted auth and redirects on unauthorized responses", async () => {
    const { localStorageMock, location } = stubBrowserState(
      JSON.stringify({
        access_token: "token-1",
        token_type: "Bearer",
      }),
    );
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('{"detail":"登录已过期，请重新登录"}', {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      authenticatedJson(
        "/api/private",
        { method: "GET" },
        { fallbackMessage: "fallback" },
      ),
    ).rejects.toMatchObject<Partial<FrontendApiError>>({
      name: "FrontendApiError",
      status: 401,
      message: "登录已过期，请重新登录",
    });

    expect(localStorageMock.removeItem).toHaveBeenCalledWith(AUTH_STORAGE_KEY);
    expect(localStorageMock.removeItem).toHaveBeenCalledWith(STORAGE_KEY);
    expect(localStorageMock.removeItem).toHaveBeenCalledWith(CURRENT_SESSION_KEY);
    expect(location.href).toBe("/login");
  });

  it("parses structured validation errors into a readable message", () => {
    const message = getResponseErrorMessage(
      JSON.stringify({
        detail: [
          {
            loc: ["body", "files", 0],
            msg: "Field required",
            type: "missing",
          },
        ],
      }),
      "fallback",
      400,
    );

    expect(message).toBe("body.files.0: Field required");
  });

  it("falls back to safe text when error JSON has an unexpected shape", () => {
    expect(getResponseErrorMessage("<html>bad gateway</html>", "fallback", 502)).toBe(
      "<html>bad gateway</html>",
    );
    expect(getResponseErrorMessage("", "fallback", 502)).toBe("fallback");
  });
});
