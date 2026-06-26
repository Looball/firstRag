import { NextResponse } from "next/server";

export const runtime = "nodejs";

const backendOrigin =
  process.env.BACKEND_ORIGIN?.replace(/\/+$/, "") || "http://127.0.0.1:8000";
const backendApiPrefix = process.env.BACKEND_API_PREFIX
  ? `/${process.env.BACKEND_API_PREFIX.replace(/^\/+|\/+$/g, "")}`
  : "";

function getBackendConversationUrl(conversationId: string) {
  return `${backendOrigin}${backendApiPrefix}/chat/conversation/${encodeURIComponent(
    conversationId
  )}`;
}

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ conversationId: string }> }
) {
  try {
    const { conversationId } = await params;
    const body = await request.text();
    const upstreamHeaders = new Headers({
      Accept: "application/json",
      "Content-Type": request.headers.get("Content-Type") || "application/json",
    });
    const authorization = request.headers.get("Authorization");

    if (authorization) {
      upstreamHeaders.set("Authorization", authorization);
    }

    const upstreamResponse = await fetch(
      getBackendConversationUrl(conversationId),
      {
        method: "PATCH",
        headers: upstreamHeaders,
        body,
        cache: "no-store",
      }
    );
    const responseText = await upstreamResponse.text();

    return new NextResponse(responseText, {
      status: upstreamResponse.status,
      headers: {
        "Content-Type":
          upstreamResponse.headers.get("Content-Type") || "application/json",
      },
    });
  } catch (error) {
    console.error("Backend rename conversation proxy error:", error);

    return NextResponse.json(
      { detail: "连接后端会话重命名接口失败，请确认后端服务已启动。" },
      { status: 502 }
    );
  }
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ conversationId: string }> }
) {
  try {
    const { conversationId } = await params;
    const upstreamHeaders = new Headers({
      Accept: "application/json",
    });
    const authorization = request.headers.get("Authorization");

    if (authorization) {
      upstreamHeaders.set("Authorization", authorization);
    }

    const upstreamResponse = await fetch(
      getBackendConversationUrl(conversationId),
      {
        method: "DELETE",
        headers: upstreamHeaders,
        cache: "no-store",
      }
    );
    const responseText = await upstreamResponse.text();

    return new NextResponse(responseText, {
      status: upstreamResponse.status,
      headers: {
        "Content-Type":
          upstreamResponse.headers.get("Content-Type") || "application/json",
      },
    });
  } catch (error) {
    console.error("Backend delete conversation proxy error:", error);

    return NextResponse.json(
      { detail: "连接后端会话删除接口失败，请确认后端服务已启动。" },
      { status: 502 }
    );
  }
}
