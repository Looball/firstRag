import { NextResponse } from "next/server";

export const runtime = "nodejs";

const backendOrigin =
  process.env.BACKEND_ORIGIN?.replace(/\/+$/, "") || "http://127.0.0.1:8000";
const backendApiPrefix = process.env.BACKEND_API_PREFIX
  ? `/${process.env.BACKEND_API_PREFIX.replace(/^\/+|\/+$/g, "")}`
  : "";

function getBackendUrl(knowledgeBaseId: string) {
  return `${backendOrigin}${backendApiPrefix}/chat/knowledge-base/${encodeURIComponent(
    knowledgeBaseId
  )}/vectors`;
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ knowledgeBaseId: string }> }
) {
  try {
    const { knowledgeBaseId } = await params;
    const headers = new Headers({ Accept: "application/json" });
    const authorization = request.headers.get("Authorization");

    if (authorization) {
      headers.set("Authorization", authorization);
    }

    const response = await fetch(getBackendUrl(knowledgeBaseId), {
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
    console.error("Backend knowledge base vector index proxy error:", error);

    return NextResponse.json(
      { detail: "连接后端知识库向量化接口失败，请确认后端服务已启动。" },
      { status: 502 }
    );
  }
}
