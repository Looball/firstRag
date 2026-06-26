import { NextResponse } from "next/server";

export const runtime = "nodejs";

const backendOrigin =
  process.env.BACKEND_ORIGIN?.replace(/\/+$/, "") || "http://127.0.0.1:8000";
const backendApiPrefix = process.env.BACKEND_API_PREFIX
  ? `/${process.env.BACKEND_API_PREFIX.replace(/^\/+|\/+$/g, "")}`
  : "";

function getBackendConversationsUrl() {
  return `${backendOrigin}${backendApiPrefix}/chat/conversations`;
}

export async function GET(request: Request) {
  try {
    const upstreamHeaders = new Headers({
      Accept: "application/json",
    });
    const authorization = request.headers.get("Authorization");

    if (authorization) {
      upstreamHeaders.set("Authorization", authorization);
    }

    const upstreamResponse = await fetch(getBackendConversationsUrl(), {
      method: "GET",
      headers: upstreamHeaders,
      cache: "no-store",
    });
    const responseText = await upstreamResponse.text();

    return new NextResponse(responseText, {
      status: upstreamResponse.status,
      headers: {
        "Content-Type":
          upstreamResponse.headers.get("Content-Type") || "application/json",
      },
    });
  } catch (error) {
    console.error("Backend conversations proxy error:", error);

    return NextResponse.json(
      { detail: "连接后端会话列表接口失败，请确认后端服务已启动。" },
      { status: 502 }
    );
  }
}
