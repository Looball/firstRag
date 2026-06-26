import { NextResponse } from "next/server";

export const runtime = "nodejs";

const backendOrigin =
  process.env.BACKEND_ORIGIN?.replace(/\/+$/, "") || "http://127.0.0.1:8000";
const backendApiPrefix = process.env.BACKEND_API_PREFIX
  ? `/${process.env.BACKEND_API_PREFIX.replace(/^\/+|\/+$/g, "")}`
  : "";

function getBackendUrl(jobId: string) {
  return `${backendOrigin}${backendApiPrefix}/chat/vector-index-jobs/${encodeURIComponent(
    jobId
  )}`;
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ jobId: string }> }
) {
  try {
    const { jobId } = await params;
    const headers = new Headers({ Accept: "application/json" });
    const authorization = request.headers.get("Authorization");

    if (authorization) {
      headers.set("Authorization", authorization);
    }

    const response = await fetch(getBackendUrl(jobId), {
      method: "GET",
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
    console.error("Backend vector index job proxy error:", error);

    return NextResponse.json(
      { detail: "连接后端向量化任务状态接口失败，请确认后端服务已启动。" },
      { status: 502 }
    );
  }
}
