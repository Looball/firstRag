import { NextResponse } from "next/server";

export const runtime = "nodejs";

const backendOrigin =
  process.env.BACKEND_ORIGIN?.replace(/\/+$/, "") || "http://127.0.0.1:8000";

function getBackendUrl(path: string) {
  return `${backendOrigin}${path}`;
}

async function proxyRequest(
  request: Request,
  method: "GET" | "PATCH" | "POST",
  path: string
) {
  const headers = new Headers({ Accept: "application/json" });
  const authorization = request.headers.get("Authorization");

  if (authorization) {
    headers.set("Authorization", authorization);
  }

  const requestBody = method === "GET" ? undefined : await request.text();
  const body = requestBody?.trim() ? requestBody : undefined;

  if (body !== undefined) {
    headers.set(
      "Content-Type",
      request.headers.get("Content-Type") || "application/json"
    );
  }

  const upstreamResponse = await fetch(getBackendUrl(path), {
    method,
    headers,
    body,
    cache: "no-store",
  });

  return new Response(upstreamResponse.body, {
    status: upstreamResponse.status,
    headers: {
      "Cache-Control": "no-cache, no-transform",
      "Content-Type":
        upstreamResponse.headers.get("Content-Type") || "application/json",
    },
  });
}

export async function GET(request: Request) {
  try {
    return await proxyRequest(request, "GET", "/user/settings");
  } catch (error) {
    console.error("Backend settings proxy error:", error);
    return NextResponse.json(
      { detail: "读取设置失败，请确认后端服务已启动。" },
      { status: 502 }
    );
  }
}

export async function PATCH(request: Request) {
  try {
    return await proxyRequest(request, "PATCH", "/user/settings");
  } catch (error) {
    console.error("Backend update settings proxy error:", error);
    return NextResponse.json(
      { detail: "保存设置失败，请确认后端服务已启动。" },
      { status: 502 }
    );
  }
}

export async function POST(request: Request) {
  try {
    return await proxyRequest(request, "POST", "/user/settings/test");
  } catch (error) {
    console.error("Backend settings test proxy error:", error);
    return NextResponse.json(
      { detail: "测试设置失败，请确认后端服务已启动。" },
      { status: 502 }
    );
  }
}
