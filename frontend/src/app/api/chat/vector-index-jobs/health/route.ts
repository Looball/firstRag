import { backendProxyError, proxyToBackend } from "@/lib/api-proxy";

export const runtime = "nodejs";

export async function GET(request: Request) {
  try {
    return await proxyToBackend({
      request,
      method: "GET",
      path: "/chat/vector-index-jobs/health",
    });
  } catch (error) {
    console.error("Backend vector index health proxy error:", error);

    return backendProxyError(
      { detail: "连接后端向量化健康检查接口失败，请确认后端服务已启动。" },
      502
    );
  }
}
