import { NextResponse } from "next/server";

export const runtime = "nodejs";

const backendOrigin =
  process.env.BACKEND_ORIGIN?.replace(/\/+$/, "") || "http://127.0.0.1:8000";
const backendApiPrefix = process.env.BACKEND_API_PREFIX
  ? `/${process.env.BACKEND_API_PREFIX.replace(/^\/+|\/+$/g, "")}`
  : "";

function getBackendDetachUrl(
  knowledgeBaseId: string,
  knowledgeFileId: string
) {
  return `${backendOrigin}${backendApiPrefix}/chat/knowledge-base/${encodeURIComponent(
    knowledgeBaseId
  )}/files/${encodeURIComponent(knowledgeFileId)}`;
}

export async function DELETE(
  request: Request,
  context: RouteContext<
    "/api/chat/knowledge-base/[knowledgeBaseId]/files/[knowledgeFileId]"
  >
) {
  try {
    const { knowledgeBaseId, knowledgeFileId } = await context.params;
    const upstreamHeaders = new Headers({
      Accept: "application/json",
    });
    const authorization = request.headers.get("Authorization");

    if (authorization) {
      upstreamHeaders.set("Authorization", authorization);
    }

    const upstreamResponse = await fetch(
      getBackendDetachUrl(knowledgeBaseId, knowledgeFileId),
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
    console.error("Backend knowledge file detach proxy error:", error);

    return NextResponse.json(
      { detail: "连接后端解除文件关联接口失败，请确认后端服务已启动。" },
      { status: 502 }
    );
  }
}
