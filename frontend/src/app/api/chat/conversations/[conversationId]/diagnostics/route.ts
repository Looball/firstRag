import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

function getBackendPath(conversationId: string) {
  return `/chat/conversations/${encodeBackendPathSegment(
    conversationId
  )}/diagnostics`;
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ conversationId: string }> }
) {
  try {
    const { conversationId } = await params;
    return await proxyToBackend({
      request,
      method: "GET",
      path: getBackendPath(conversationId),
    });
  } catch (error) {
    console.error("Backend conversation diagnostics proxy error:", error);
    return backendProxyError(
      { detail: "连接后端诊断接口失败，请确认后端服务已启动。" },
      502
    );
  }
}
