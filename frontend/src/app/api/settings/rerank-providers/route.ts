import { backendProxyError, proxyToBackend } from "@/lib/api-proxy";

export const runtime = "nodejs";

export async function GET(request: Request) {
  try {
    return await proxyToBackend({
      request,
      method: "GET",
      path: "/user/settings/rerank-providers",
      includeApiPrefix: false,
    });
  } catch (error) {
    console.error("Backend rerank providers proxy error:", error);
    return backendProxyError(
      { detail: "读取 Rerank 厂商失败，请确认后端服务已启动。" },
      502
    );
  }
}
