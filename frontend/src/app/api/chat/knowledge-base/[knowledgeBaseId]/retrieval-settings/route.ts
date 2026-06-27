import { NextResponse } from "next/server";

export const runtime = "nodejs";

const backendOrigin =
  process.env.BACKEND_ORIGIN?.replace(/\/+$/, "") || "http://127.0.0.1:8000";
const backendApiPrefix = process.env.BACKEND_API_PREFIX
  ? `/${process.env.BACKEND_API_PREFIX.replace(/^\/+|\/+$/g, "")}`
  : "";

function getBackendRetrievalSettingsUrl(knowledgeBaseId: string) {
  return `${backendOrigin}${backendApiPrefix}/chat/knowledge-base/${encodeURIComponent(
    knowledgeBaseId
  )}/retrieval-settings`;
}

type RetrievalSettingsParams = {
  params: Promise<{ knowledgeBaseId: string }>;
};

function buildForwardHeaders(request: Request) {
  const headers = new Headers({
    Accept: "application/json",
  });
  const authorization = request.headers.get("Authorization");

  if (authorization) {
    headers.set("Authorization", authorization);
  }

  return headers;
}

export async function GET(
  request: Request,
  { params }: RetrievalSettingsParams
) {
  try {
    const { knowledgeBaseId } = await params;
    const upstreamResponse = await fetch(
      getBackendRetrievalSettingsUrl(knowledgeBaseId),
      {
        method: "GET",
        headers: buildForwardHeaders(request),
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
    console.error("Backend retrieval settings proxy error:", error);

    return NextResponse.json(
      { detail: "连接后端检索设置接口失败，请确认后端服务已启动。" },
      { status: 502 }
    );
  }
}

export async function PATCH(
  request: Request,
  { params }: RetrievalSettingsParams
) {
  try {
    const { knowledgeBaseId } = await params;
    const headers = buildForwardHeaders(request);
    headers.set("Content-Type", "application/json");
    const upstreamResponse = await fetch(
      getBackendRetrievalSettingsUrl(knowledgeBaseId),
      {
        method: "PATCH",
        headers,
        body: await request.text(),
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
    console.error("Backend retrieval settings update proxy error:", error);

    return NextResponse.json(
      { detail: "保存检索设置失败，请确认后端服务已启动。" },
      { status: 502 }
    );
  }
}
