import { z } from "zod";
import {
  AUTH_STORAGE_KEY,
  buildAuthorizationHeader,
  parseAuthState,
} from "./auth";
import {
  CURRENT_SESSION_KEY,
  STORAGE_KEY,
} from "./chat-workspace/constants";
import { isAuthExpiredMessage } from "./chat-workspace/utils";

const errorDetailItemSchema = z
  .object({
    loc: z.union([z.array(z.union([z.string(), z.number()])), z.string()]).optional(),
    msg: z.string().optional(),
    type: z.string().optional(),
  })
  .passthrough();

const errorResponseSchema = z
  .object({
    answer: z.unknown().optional(),
    detail: z.unknown().optional(),
    error: z.unknown().optional(),
    message: z.unknown().optional(),
  })
  .passthrough();

type AuthenticatedRequestOptions = {
  fallbackMessage: string;
  skipAuthRedirect?: boolean;
};

export class FrontendApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "FrontendApiError";
    this.status = status;
  }
}

function getStringValue(value: unknown) {
  return typeof value === "string" && value.trim() ? value.trim() : "";
}

export function redirectToLogin() {
  localStorage.removeItem(AUTH_STORAGE_KEY);
  localStorage.removeItem(STORAGE_KEY);
  localStorage.removeItem(CURRENT_SESSION_KEY);

  if (window.location.pathname !== "/login") {
    window.location.href = "/login";
  }
}

export function getResponseErrorMessage(
  errorText: string,
  fallback: string,
  status?: number,
) {
  if (status === 401 || status === 403 || isAuthExpiredMessage(errorText)) {
    redirectToLogin();
  }

  const parsed = errorResponseSchema.safeParse(parseJsonValue(errorText));

  if (parsed.success) {
    const errorData = parsed.data;
    const directMessage =
      getStringValue(errorData.answer) ||
      getStringValue(errorData.detail) ||
      getStringValue(errorData.error) ||
      getStringValue(errorData.message);

    if (directMessage) {
      if (isAuthExpiredMessage(directMessage)) {
        redirectToLogin();
      }

      return directMessage;
    }

    if (Array.isArray(errorData.detail)) {
      const detailMessages = errorData.detail
        .map((detail) => {
          const detailItem = errorDetailItemSchema.safeParse(detail);

          if (!detailItem.success) {
            return getStringValue(detail);
          }

          const location = Array.isArray(detailItem.data.loc)
            ? detailItem.data.loc.join(".")
            : getStringValue(detailItem.data.loc);
          const message = getStringValue(detailItem.data.msg);
          const type = getStringValue(detailItem.data.type);

          return location && message ? `${location}: ${message}` : message || type;
        })
        .filter(Boolean);

      if (detailMessages.length > 0) {
        const detailMessage = detailMessages.join("；");

        if (isAuthExpiredMessage(detailMessage)) {
          redirectToLogin();
        }

        return detailMessage;
      }
    }
  }

  const message = errorText.trim() || fallback;

  if (isAuthExpiredMessage(message)) {
    redirectToLogin();
  }

  return message;
}

export function parseJsonValue(value: string) {
  try {
    return JSON.parse(value) as unknown;
  } catch {
    return null;
  }
}

export function getAuthorizationHeader() {
  const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

  if (!authState) {
    redirectToLogin();
    throw new Error("登录已失效，请重新登录。");
  }

  return buildAuthorizationHeader(authState);
}

export async function authenticatedFetch(
  path: string,
  init: RequestInit,
  options: AuthenticatedRequestOptions,
) {
  const headers = new Headers(init.headers);
  headers.set("Authorization", getAuthorizationHeader());

  const response = await fetch(path, {
    cache: init.method === "GET" || !init.method ? "no-store" : init.cache,
    ...init,
    headers,
  });

  if (!response.ok) {
    const errorText = await response.text();

    if (!options.skipAuthRedirect && (response.status === 401 || response.status === 403)) {
      redirectToLogin();
    }

    throw new FrontendApiError(
      getResponseErrorMessage(errorText, options.fallbackMessage, response.status),
      response.status,
    );
  }

  return response;
}

export async function authenticatedJson<T>(
  path: string,
  init: RequestInit,
  options: AuthenticatedRequestOptions,
) {
  const response = await authenticatedFetch(path, init, options);
  return (await response.json()) as T;
}

export async function authenticatedText(
  path: string,
  init: RequestInit,
  options: AuthenticatedRequestOptions,
) {
  const response = await authenticatedFetch(path, init, options);
  return response.text();
}
