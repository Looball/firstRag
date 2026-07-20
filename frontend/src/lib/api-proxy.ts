import { NextResponse } from "next/server";

export type ProxyMethod = "DELETE" | "GET" | "PATCH" | "POST";

type ProxyBodyMode = "formData" | "none" | "text";

type ProxyOptions = {
  method: ProxyMethod;
  path: string;
  request: Request;
  accept?: string;
  bodyMode?: ProxyBodyMode;
  contentType?: string;
  copySetCookie?: boolean;
  fallbackContentType?: string;
  includeApiPrefix?: boolean;
  stream?: boolean;
};

const backendOrigin =
  process.env.BACKEND_ORIGIN?.replace(/\/+$/, "") || "http://127.0.0.1:8000";
const backendApiPrefix = process.env.BACKEND_API_PREFIX
  ? `/${process.env.BACKEND_API_PREFIX.replace(/^\/+|\/+$/g, "")}`
  : "";

export function encodeBackendPathSegment(value: string) {
  return encodeURIComponent(value);
}

export function buildBackendUrl(
  path: string,
  options?: { includeApiPrefix?: boolean }
) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const prefix = options?.includeApiPrefix === false ? "" : backendApiPrefix;

  return `${backendOrigin}${prefix}${normalizedPath}`;
}

export function buildProxyHeaders(
  request: Request,
  options?: {
    accept?: string;
    contentType?: string;
  }
) {
  const headers = new Headers({
    Accept: options?.accept || "application/json",
  });
  const authorization = request.headers.get("Authorization");

  if (authorization) {
    headers.set("Authorization", authorization);
  }

  if (options?.contentType) {
    headers.set("Content-Type", options.contentType);
  }

  return headers;
}

async function readProxyBody(
  request: Request,
  bodyMode: ProxyBodyMode
) {
  if (bodyMode === "none") {
    return undefined;
  }

  if (bodyMode === "formData") {
    return request.formData();
  }

  const body = await request.text();
  return body.trim() ? body : undefined;
}

export async function proxyToBackend({
  method,
  path,
  request,
  accept = "application/json",
  bodyMode = method === "GET" || method === "DELETE" ? "none" : "text",
  contentType,
  copySetCookie = false,
  fallbackContentType = "application/json",
  includeApiPrefix = true,
  stream = false,
}: ProxyOptions) {
  const resolvedContentType =
    bodyMode === "text"
      ? contentType || request.headers.get("Content-Type") || "application/json"
      : contentType;
  const headers = buildProxyHeaders(request, {
    accept,
    contentType: resolvedContentType,
  });
  const body = await readProxyBody(request, bodyMode);
  const upstreamResponse = await fetch(
    buildBackendUrl(path, { includeApiPrefix }),
    {
      method,
      headers,
      body,
      cache: "no-store",
    }
  );
  const responseHeaders = new Headers({
    "Cache-Control": "no-cache, no-transform",
    "Content-Type":
      upstreamResponse.headers.get("Content-Type") || fallbackContentType,
  });

  if (stream) {
    responseHeaders.set("X-Accel-Buffering", "no");
  }

  const setCookie = upstreamResponse.headers.get("Set-Cookie");
  if (copySetCookie && setCookie) {
    responseHeaders.set("Set-Cookie", setCookie);
  }

  const retryAfter = upstreamResponse.headers.get("Retry-After");
  if (retryAfter) {
    responseHeaders.set("Retry-After", retryAfter);
  }

  return new Response(upstreamResponse.body, {
    status: upstreamResponse.status,
    headers: responseHeaders,
  });
}

export function backendProxyError(
  body: Record<string, string>,
  status = 502
) {
  return NextResponse.json(body, { status });
}
