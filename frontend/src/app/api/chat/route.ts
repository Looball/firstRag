import { NextResponse } from "next/server";

export const runtime = "nodejs";

const backendOrigin =
  process.env.BACKEND_ORIGIN?.replace(/\/+$/, "") || "http://127.0.0.1:8000";
const backendApiPrefix = process.env.BACKEND_API_PREFIX
  ? `/${process.env.BACKEND_API_PREFIX.replace(/^\/+|\/+$/g, "")}`
  : "";

function getBackendChatUrl() {
  return `${backendOrigin}${backendApiPrefix}/chat`;
}

export async function POST(request: Request) {
  try {
    const body = await request.text();
    const upstreamHeaders = new Headers({
      Accept: "text/event-stream",
      "Content-Type": request.headers.get("Content-Type") || "application/json",
    });
    const authorization = request.headers.get("Authorization");

    if (authorization) {
      upstreamHeaders.set("Authorization", authorization);
    }

    const upstreamResponse = await fetch(getBackendChatUrl(), {
      method: "POST",
      headers: upstreamHeaders,
      body,
      cache: "no-store",
    });

    if (!upstreamResponse.body) {
      const text = await upstreamResponse.text();

      return new Response(text, {
        status: upstreamResponse.status,
        headers: {
          "Cache-Control": "no-cache, no-transform",
          "Content-Type":
            upstreamResponse.headers.get("Content-Type") ||
            "text/plain; charset=utf-8",
          "X-Accel-Buffering": "no",
        },
      });
    }

    return new Response(upstreamResponse.body, {
      status: upstreamResponse.status,
      headers: {
        "Cache-Control": "no-cache, no-transform",
        "Content-Type":
          upstreamResponse.headers.get("Content-Type") ||
          "text/plain; charset=utf-8",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (error) {
    console.error("Backend chat proxy error:", error);

    return NextResponse.json(
      { detail: "连接后端失败，请确认 127.0.0.1:8000 已启动。" },
      { status: 502 }
    );
  }
}
