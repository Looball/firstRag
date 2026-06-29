import { backendProxyError, proxyToBackend } from "@/lib/api-proxy";

export const runtime = "nodejs";

export async function POST(request: Request) {
  try {
    return await proxyToBackend({
      request,
      method: "POST",
      path: "/chat",
      accept: "text/event-stream",
      fallbackContentType: "text/plain; charset=utf-8",
      stream: true,
    });
  } catch (error) {
    console.error("Backend chat proxy error:", error);

    return backendProxyError(
      { detail: "连接后端失败，请确认 127.0.0.1:8000 已启动。" },
      502
    );
  }
}
