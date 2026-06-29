import { afterEach, describe, expect, it, vi } from "vitest";

import {
  buildBackendUrl,
  proxyToBackend,
} from "./api-proxy";

describe("api proxy helpers", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("forwards authorization and JSON body to the backend", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('{"success":true}', {
        status: 201,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);
    const request = new Request("http://localhost/api/chat", {
      method: "POST",
      headers: {
        Authorization: "Bearer token",
        "Content-Type": "application/json",
      },
      body: '{"message":"hi"}',
    });

    const response = await proxyToBackend({
      request,
      method: "POST",
      path: "/chat",
    });
    const [, init] = fetchMock.mock.calls[0];
    const headers = init.headers as Headers;

    expect(fetchMock).toHaveBeenCalledWith(
      buildBackendUrl("/chat"),
      expect.objectContaining({ method: "POST" })
    );
    expect(headers.get("Authorization")).toBe("Bearer token");
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(init.body).toBe('{"message":"hi"}');
    expect(response.status).toBe(201);
    await expect(response.text()).resolves.toBe('{"success":true}');
  });

  it("keeps chat responses streamable with SSE headers", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response("event: done\n\n", {
        headers: { "Content-Type": "text/event-stream; charset=utf-8" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);
    const request = new Request("http://localhost/api/chat", {
      method: "POST",
      body: "{}",
    });

    const response = await proxyToBackend({
      request,
      method: "POST",
      path: "/chat",
      accept: "text/event-stream",
      fallbackContentType: "text/plain; charset=utf-8",
      stream: true,
    });
    const [, init] = fetchMock.mock.calls[0];
    const headers = init.headers as Headers;

    expect(headers.get("Accept")).toBe("text/event-stream");
    expect(response.headers.get("X-Accel-Buffering")).toBe("no");
    expect(response.headers.get("Content-Type")).toContain(
      "text/event-stream"
    );
    await expect(response.text()).resolves.toBe("event: done\n\n");
  });

  it("returns streaming proxy responses before upstream body is consumed", async () => {
    let controller: ReadableStreamDefaultController<Uint8Array> | null = null;
    const upstreamStream = new ReadableStream<Uint8Array>({
      start(nextController) {
        controller = nextController;
      },
    });
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(upstreamStream, {
        headers: { "Content-Type": "text/event-stream; charset=utf-8" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);
    const request = new Request("http://localhost/api/chat", {
      method: "POST",
      body: "{}",
    });

    const response = await Promise.race([
      proxyToBackend({
        request,
        method: "POST",
        path: "/chat",
        accept: "text/event-stream",
        fallbackContentType: "text/plain; charset=utf-8",
        stream: true,
      }),
      new Promise<"timeout">((resolve) => {
        setTimeout(() => resolve("timeout"), 20);
      }),
    ]);

    expect(response).toBeInstanceOf(Response);
    controller?.enqueue(new TextEncoder().encode("event: done\n\n"));
    controller?.close();
    await expect((response as Response).text()).resolves.toBe("event: done\n\n");
  });

  it("forwards multipart form data without forcing content type", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('{"success":true}', {
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);
    const formData = new FormData();
    formData.append("files", new Blob(["# title"]), "notes.md");
    const request = new Request("http://localhost/api/upload", {
      method: "POST",
      headers: { Authorization: "Bearer token" },
      body: formData,
    });

    await proxyToBackend({
      request,
      method: "POST",
      path: "/chat/knowledge-base/kb/files",
      bodyMode: "formData",
    });
    const [, init] = fetchMock.mock.calls[0];
    const headers = init.headers as Headers;

    expect(headers.get("Authorization")).toBe("Bearer token");
    expect(headers.has("Content-Type")).toBe(false);
    expect(init.body).toBeInstanceOf(FormData);
  });
});
