import { backendProxyError, proxyToBackend } from "@/lib/api-proxy";

export const runtime = "nodejs";

export async function POST(request: Request) {
  try {
    return await proxyToBackend({
      request,
      method: "POST",
      path: "/chat/conversation",
    });
  } catch (error) {
    console.error("Backend conversation proxy error:", error);

    return backendProxyError(
      { detail: "连接后端创建对话接口失败，请确认后端服务已启动。" },
      502
    );
  }
}
