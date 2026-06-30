import {
  backendProxyError,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

export async function GET(request: Request) {
  try {
    const url = new URL(request.url);
    const days = url.searchParams.get("days") || "7";

    return await proxyToBackend({
      request,
      method: "GET",
      path: `/chat/quality-dashboard?days=${encodeURIComponent(days)}`,
    });
  } catch (error) {
    console.error("Backend quality dashboard proxy error:", error);
    return backendProxyError(
      { detail: "连接后端质量看板接口失败，请确认后端服务已启动。" },
      502,
    );
  }
}
