import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

function getBackendPath(messageId: string, sourceIndex: string) {
  return `/chat/messages/${encodeBackendPathSegment(
    messageId,
  )}/sources/${encodeBackendPathSegment(sourceIndex)}/feedback`;
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ messageId: string; sourceIndex: string }> },
) {
  try {
    const { messageId, sourceIndex } = await params;
    return await proxyToBackend({
      request,
      method: "POST",
      path: getBackendPath(messageId, sourceIndex),
    });
  } catch (error) {
    console.error("Backend message source feedback proxy error:", error);
    return backendProxyError(
      { detail: "连接后端引用反馈接口失败，请确认后端服务已启动。" },
      502,
    );
  }
}
