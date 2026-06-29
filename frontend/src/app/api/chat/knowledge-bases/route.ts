import { backendProxyError, proxyToBackend } from "@/lib/api-proxy";

export const runtime = "nodejs";

export async function GET(request: Request) {
  try {
    return await proxyToBackend({
      request,
      method: "GET",
      path: "/chat/knowledge-bases",
    });
  } catch (error) {
    console.error("Backend knowledge bases proxy error:", error);

    return backendProxyError(
      { detail: "连接后端知识库列表接口失败，请确认后端服务已启动。" },
      502
    );
  }
}
