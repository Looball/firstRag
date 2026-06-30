import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

function getBackendPath(messageId: string) {
  return `/chat/messages/${encodeBackendPathSegment(messageId)}/eval-case-draft`;
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ messageId: string }> },
) {
  try {
    const { messageId } = await params;
    return await proxyToBackend({
      request,
      method: "GET",
      path: getBackendPath(messageId),
    });
  } catch (error) {
    console.error("Backend eval case draft proxy error:", error);
    return backendProxyError(
      { detail: "连接后端 eval case 草稿接口失败，请确认后端服务已启动。" },
      502,
    );
  }
}
