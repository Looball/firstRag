import { backendProxyError, proxyToBackend } from "@/lib/api-proxy";

export const runtime = "nodejs";

export async function GET(request: Request) {
  try {
    return await proxyToBackend({
      request,
      method: "GET",
      path: "/chat/knowledge-bases/trash",
    });
  } catch (error) {
    console.error("Backend knowledge base trash proxy error:", error);
    return backendProxyError(
      { detail: "连接后端知识库回收站接口失败，请确认后端服务已启动。" },
      502,
    );
  }
}
