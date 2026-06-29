import { backendProxyError, proxyToBackend } from "@/lib/api-proxy";

export const runtime = "nodejs";

export async function POST(request: Request) {
  try {
    return await proxyToBackend({
      request,
      method: "POST",
      path: "/chat/knowledge-base",
    });
  } catch (error) {
    console.error("Backend create knowledge base proxy error:", error);

    return backendProxyError(
      { detail: "连接后端创建知识库接口失败，请确认后端服务已启动。" },
      502
    );
  }
}
