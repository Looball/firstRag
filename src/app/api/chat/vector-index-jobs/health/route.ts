import { NextResponse } from "next/server";

export const runtime = "nodejs";

const backendOrigin =
  process.env.BACKEND_ORIGIN?.replace(/\/+$/, "") || "http://127.0.0.1:8000";
const backendApiPrefix = process.env.BACKEND_API_PREFIX
  ? `/${process.env.BACKEND_API_PREFIX.replace(/^\/+|\/+$/g, "")}`
  : "";

function getBackendUrl() {
  return `${backendOrigin}${backendApiPrefix}/chat/vector-index-jobs/health`;
}

export async function GET(request: Request) {
  try {
    const headers = new Headers({ Accept: "application/json" });
    const authorization = request.headers.get("Authorization");

    if (authorization) {
      headers.set("Authorization", authorization);
    }

    const response = await fetch(getBackendUrl(), {
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
    console.error("Backend vector index health proxy error:", error);

    return NextResponse.json(
      { detail: "连接后端向量化健康检查接口失败，请确认后端服务已启动。" },
      { status: 502 }
    );
  }
}
