import { NextResponse } from "next/server";

export const runtime = "nodejs";

const backendOrigin =
  process.env.BACKEND_ORIGIN?.replace(/\/+$/, "") || "http://127.0.0.1:8000";
const backendApiPrefix = process.env.BACKEND_API_PREFIX
  ? `/${process.env.BACKEND_API_PREFIX.replace(/^\/+|\/+$/g, "")}`
  : "";

function getBackendUrl(knowledgeBaseId: string, conversationId: string) {
  return `${backendOrigin}${backendApiPrefix}/chat/knowledge-bases/${encodeURIComponent(
    knowledgeBaseId
  )}/conversations/${encodeURIComponent(conversationId)}`;
}

async function proxyRequest(
  request: Request,
  knowledgeBaseId: string,
  conversationId: string,
  method: "PATCH" | "DELETE"
) {
  const headers = new Headers({ Accept: "application/json" });
  const authorization = request.headers.get("Authorization");

  if (authorization) {
    headers.set("Authorization", authorization);
  }

  let body: string | undefined;

  if (method === "PATCH") {
    headers.set(
      "Content-Type",
      request.headers.get("Content-Type") || "application/json"
    );
    body = await request.text();
  }

  const response = await fetch(
    getBackendUrl(knowledgeBaseId, conversationId),
    {
      method,
      headers,
      body,
      cache: "no-store",
    }
  );
  const responseText = await response.text();

  return new NextResponse(responseText, {
    status: response.status,
    headers: {
      "Content-Type":
        response.headers.get("Content-Type") || "application/json",
    },
  });
}

export async function PATCH(
  request: Request,
  {
    params,
  }: {
    params: Promise<{ knowledgeBaseId: string; conversationId: string }>;
  }
) {
  try {
    const { knowledgeBaseId, conversationId } = await params;
    return await proxyRequest(
      request,
      knowledgeBaseId,
      conversationId,
      "PATCH"
    );
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
  {
    params,
  }: {
    params: Promise<{ knowledgeBaseId: string; conversationId: string }>;
  }
) {
  try {
    const { knowledgeBaseId, conversationId } = await params;
    return await proxyRequest(
      request,
      knowledgeBaseId,
      conversationId,
      "DELETE"
    );
  } catch (error) {
    console.error("Backend delete conversation proxy error:", error);
    return NextResponse.json(
      { detail: "连接后端删除会话接口失败，请确认后端服务已启动。" },
      { status: 502 }
    );
  }
}
