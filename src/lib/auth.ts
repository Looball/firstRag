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
