import { backendProxyError, proxyToBackend } from "@/lib/api-proxy";

export const runtime = "nodejs";

export async function GET(request: Request) {
  try {
    return await proxyToBackend({
      request,
      method: "GET",
      path: "/chat/conversations",
    });
  } catch (error) {
    console.error("Backend conversations proxy error:", error);

    return backendProxyError(
      { detail: "连接后端会话列表接口失败，请确认后端服务已启动。" },
      502
    );
  }
}
