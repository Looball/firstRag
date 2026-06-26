import { NextResponse } from "next/server";

export const runtime = "nodejs";

const backendOrigin =
  process.env.BACKEND_ORIGIN?.replace(/\/+$/, "") || "http://127.0.0.1:8000";
const backendApiPrefix = process.env.BACKEND_API_PREFIX
  ? `/${process.env.BACKEND_API_PREFIX.replace(/^\/+|\/+$/g, "")}`
  : "";

function getBackendUrl(knowledgeBaseId: string) {
  return `${backendOrigin}${backendApiPrefix}/chat/knowledge-bases/${encodeURIComponent(
    knowledgeBaseId
  )}/conversations`;
}

async function proxyRequest(
  request: Request,
  knowledgeBaseId: string,
  method: "GET" | "POST"
) {
  const headers = new Headers({ Accept: "application/json" });
  const authorization = request.headers.get("Authorization");

  if (authorization) {
    headers.set("Authorization", authorization);
  }

  let body: string | undefined;

  if (method === "POST") {
    headers.set(
      "Content-Type",
      request.headers.get("Content-Type") || "application/json"
    );
    body = await request.text();
  }

  const response = await fetch(getBackendUrl(knowledgeBaseId), {
    method,
    headers,
    body,
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
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ knowledgeBaseId: string }> }
) {
  try {
    const { knowledgeBaseId } = await params;
    return await proxyRequest(request, knowledgeBaseId, "GET");
  } catch (error) {
    console.error("Backend knowledge base conversations proxy error:", error);
    return NextResponse.json(
      { detail: "连接后端会话列表接口失败，请确认后端服务已启动。" },
      { status: 502 }
    );
  }
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ knowledgeBaseId: string }> }
) {
  try {
    const { knowledgeBaseId } = await params;
    return await proxyRequest(request, knowledgeBaseId, "POST");
  } catch (error) {
    console.error("Backend create conversation proxy error:", error);
    return NextResponse.json(
      { detail: "连接后端创建会话接口失败，请确认后端服务已启动。" },
      { status: 502 }
    );
  }
}
