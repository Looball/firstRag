import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

function getBackendPath(messageId: string) {
  return `/chat/messages/${encodeBackendPathSegment(messageId)}/feedback`;
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ messageId: string }> },
) {
  try {
    const { messageId } = await params;
    return await proxyToBackend({
      request,
      method: "POST",
      path: getBackendPath(messageId),
    });
  } catch (error) {
    console.error("Backend message feedback proxy error:", error);
    return backendProxyError(
      { detail: "连接后端消息反馈接口失败，请确认后端服务已启动。" },
      502,
    );
  }
}
