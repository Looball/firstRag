import { backendProxyError, proxyToBackend } from "@/lib/api-proxy";

export const runtime = "nodejs";

export async function GET(request: Request) {
  try {
    return await proxyToBackend({
      request,
      method: "GET",
      path: "/user/settings/providers",
      includeApiPrefix: false,
    });
  } catch (error) {
    console.error("Backend settings providers proxy error:", error);
    return backendProxyError(
      { detail: "读取模型厂商失败，请确认后端服务已启动。" },
      502
    );
  }
}
