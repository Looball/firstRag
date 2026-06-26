export const AUTH_STORAGE_KEY = "ai-learning-assistant-auth";

export type LoginResponse = {
  access_token?: unknown;
  token_type?: unknown;
  error?: string;
  message?: string;
  [key: string]: unknown;
};

export type AuthState = Omit<LoginResponse, "access_token" | "token_type"> & {
  access_token: string;
  token_type: string;
};

export function isAuthState(value: unknown): value is AuthState {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const candidate = value as Partial<Record<"access_token" | "token_type", unknown>>;

  return (
    typeof candidate.access_token === "string" &&
    candidate.access_token.trim().length > 0 &&
    typeof candidate.token_type === "string" &&
    candidate.token_type.trim().length > 0
  );
}

export function parseAuthState(rawAuthState: string | null) {
  if (!rawAuthState) {
    return null;
  }

  try {
    const parsedAuthState = JSON.parse(rawAuthState) as unknown;

    return isAuthState(parsedAuthState) ? parsedAuthState : null;
  } catch {
    return null;
  }
}

export function buildAuthorizationHeader(authState: AuthState) {
  const tokenType = authState.token_type.trim();
  const normalizedTokenType =
    tokenType.toLowerCase() === "bearer" ? "Bearer" : tokenType;

  return `${normalizedTokenType} ${authState.access_token.trim()}`;
}

export function getAuthUsername(authState: AuthState) {
  const user = authState.user;

  if (typeof user !== "object" || user === null) {
    return "";
  }

  const candidate = user as { username?: unknown; name?: unknown };

  if (typeof candidate.username === "string" && candidate.username.trim()) {
    return candidate.username.trim();
  }

  if (typeof candidate.name === "string" && candidate.name.trim()) {
    return candidate.name.trim();
  }

  return "";
}

export async function readAuthResponse(response: Response) {
  const responseText = await response.text();

  if (!responseText.trim()) {
    return {} as LoginResponse;
  }

  try {
    const data = JSON.parse(responseText) as unknown;

    if (typeof data === "object" && data !== null) {
      return data as LoginResponse;
    }
  } catch {
    return { error: responseText.trim() } as LoginResponse;
  }

  return { error: responseText.trim() } as LoginResponse;
}

export function getAuthErrorMessage(data: LoginResponse, fallback: string) {
  if (typeof data.error === "string" && data.error.trim()) {
    return data.error.trim();
  }

  if (typeof data.message === "string" && data.message.trim()) {
    return data.message.trim();
  }

  const detail = data.detail;

  if (typeof detail === "string" && detail.trim()) {
    return detail.trim();
  }

  if (Array.isArray(detail)) {
    const detailMessages = detail
      .map((item) => {
        if (typeof item === "string") {
          return item;
        }

        if (typeof item !== "object" || item === null) {
          return "";
        }

        const candidate = item as { loc?: unknown; msg?: unknown };
        const location = Array.isArray(candidate.loc)
          ? candidate.loc.join(".")
          : typeof candidate.loc === "string"
            ? candidate.loc
            : "";
        const message =
          typeof candidate.msg === "string" ? candidate.msg.trim() : "";

        return location && message ? `${location}: ${message}` : message;
      })
      .filter(Boolean);

    if (detailMessages.length > 0) {
      return detailMessages.join("；");
    }
  }

  return fallback;
}
