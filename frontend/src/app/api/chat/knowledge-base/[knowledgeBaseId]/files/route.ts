import { NextResponse } from "next/server";

export const runtime = "nodejs";

const backendOrigin =
  process.env.BACKEND_ORIGIN?.replace(/\/+$/, "") || "http://127.0.0.1:8000";
const backendApiPrefix = process.env.BACKEND_API_PREFIX
  ? `/${process.env.BACKEND_API_PREFIX.replace(/^\/+|\/+$/g, "")}`
  : "";

function getBackendFilesUrl(knowledgeBaseId: string) {
  return `${backendOrigin}${backendApiPrefix}/chat/knowledge-base/${encodeURIComponent(
    knowledgeBaseId
  )}/files`;
}

export async function GET(
  request: Request,
  context: RouteContext<
    "/api/chat/knowledge-base/[knowledgeBaseId]/files"
  >
) {
  try {
    const { knowledgeBaseId } = await context.params;
    const upstreamHeaders = new Headers({
      Accept: "application/json",
    });
    const authorization = request.headers.get("Authorization");

    if (authorization) {
      upstreamHeaders.set("Authorization", authorization);
    }

    const upstreamResponse = await fetch(
      getBackendFilesUrl(knowledgeBaseId),
      {
        method: "GET",
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
    console.error("Backend knowledge files proxy error:", error);

    return NextResponse.json(
      { detail: "连接后端知识库文件接口失败，请确认后端服务已启动。" },
      { status: 502 }
    );
  }
}

export async function POST(
  request: Request,
  context: RouteContext<
    "/api/chat/knowledge-base/[knowledgeBaseId]/files"
  >
) {
  try {
    const { knowledgeBaseId } = await context.params;
    const formData = await request.formData();
    const upstreamHeaders = new Headers({
      Accept: "application/json",
    });
    const authorization = request.headers.get("Authorization");

    if (authorization) {
      upstreamHeaders.set("Authorization", authorization);
    }

    const upstreamResponse = await fetch(
      getBackendFilesUrl(knowledgeBaseId),
      {
        method: "POST",
        headers: upstreamHeaders,
        body: formData,
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
    console.error("Backend knowledge file upload proxy error:", error);

    return NextResponse.json(
      { detail: "连接后端文件上传接口失败，请确认后端服务已启动。" },
      { status: 502 }
    );
  }
}
