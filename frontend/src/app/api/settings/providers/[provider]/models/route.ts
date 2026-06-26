import { NextResponse } from "next/server";

export const runtime = "nodejs";

const backendOrigin =
  process.env.BACKEND_ORIGIN?.replace(/\/+$/, "") || "http://127.0.0.1:8000";

export async function POST(
  request: Request,
  context: RouteContext<"/api/settings/providers/[provider]/models">
) {
  try {
    const { provider } = await context.params;
    const headers = new Headers({ Accept: "application/json" });
    const authorization = request.headers.get("Authorization");

    if (authorization) {
      headers.set("Authorization", authorization);
    }

    const upstreamResponse = await fetch(
      `${backendOrigin}/user/settings/providers/${encodeURIComponent(provider)}/models`,
      { method: "POST", headers, cache: "no-store" }
    );

    return new Response(upstreamResponse.body, {
      status: upstreamResponse.status,
      headers: {
        "Cache-Control": "no-cache, no-transform",
        "Content-Type":
          upstreamResponse.headers.get("Content-Type") || "application/json",
      },
    });
  } catch (error) {
    console.error("Backend provider models proxy error:", error);
    return NextResponse.json(
      { detail: "读取厂商模型列表失败，请确认后端服务已启动。" },
      { status: 502 }
    );
  }
}
