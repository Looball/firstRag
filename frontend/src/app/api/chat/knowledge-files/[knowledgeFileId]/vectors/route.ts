import { NextResponse } from "next/server";

export const runtime = "nodejs";

const backendOrigin =
  process.env.BACKEND_ORIGIN?.replace(/\/+$/, "") || "http://127.0.0.1:8000";
const backendApiPrefix = process.env.BACKEND_API_PREFIX
  ? `/${process.env.BACKEND_API_PREFIX.replace(/^\/+|\/+$/g, "")}`
  : "";

function getBackendUrl(knowledgeFileId: string) {
  return `${backendOrigin}${backendApiPrefix}/chat/knowledge-files/${encodeURIComponent(
    knowledgeFileId
  )}/vectors`;
}

export async function POST(
  request: Request,
  context: RouteContext<"/api/chat/knowledge-files/[knowledgeFileId]/vectors">
) {
  try {
    const { knowledgeFileId } = await context.params;
    const headers = new Headers({ Accept: "application/json" });
    const authorization = request.headers.get("Authorization");

    if (authorization) {
      headers.set("Authorization", authorization);
    }

    const response = await fetch(getBackendUrl(knowledgeFileId), {
      method: "POST",
      headers,
      cache: "no-store",
    });
    const responseText = await response.text();

    return new NextResponse(responseText, {
      status: response.status,
      headers: {
        "Content-Type":
          response.headers.get("Content-Type") || "application/json",
      },
    });
  } catch (error) {
    console.error("Backend file vector index proxy error:", error);

    return NextResponse.json(
      { detail: "连接后端文件向量化接口失败，请确认后端服务已启动。" },
      { status: 502 }
    );
  }
}

export async function DELETE(
  request: Request,
  context: RouteContext<"/api/chat/knowledge-files/[knowledgeFileId]/vectors">
) {
  try {
    const { knowledgeFileId } = await context.params;
    const headers = new Headers({ Accept: "application/json" });
    const authorization = request.headers.get("Authorization");

    if (authorization) {
      headers.set("Authorization", authorization);
    }

    const response = await fetch(getBackendUrl(knowledgeFileId), {
      method: "DELETE",
      headers,
      cache: "no-store",
    });
    const responseText = await response.text();

    return new NextResponse(responseText, {
      status: response.status,
      headers: {
        "Content-Type":
          response.headers.get("Content-Type") || "application/json",
      },
    });
  } catch (error) {
    console.error("Backend file vector delete proxy error:", error);

    return NextResponse.json(
      { detail: "连接后端删除文件向量接口失败，请确认后端服务已启动。" },
      { status: 502 }
    );
  }
}
