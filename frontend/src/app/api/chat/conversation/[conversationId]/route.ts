import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

function getBackendConversationPath(conversationId: string) {
  return `/chat/conversation/${encodeBackendPathSegment(conversationId)}`;
}

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ conversationId: string }> }
) {
  try {
    const { conversationId } = await params;
    return await proxyToBackend({
      request,
      method: "PATCH",
      path: getBackendConversationPath(conversationId),
    });
  } catch (error) {
    console.error("Backend rename conversation proxy error:", error);

    return backendProxyError(
      { detail: "连接后端会话重命名接口失败，请确认后端服务已启动。" },
      502
    );
  }
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ conversationId: string }> }
) {
  try {
    const { conversationId } = await params;
    return await proxyToBackend({
      request,
      method: "DELETE",
      path: getBackendConversationPath(conversationId),
    });
  } catch (error) {
    console.error("Backend delete conversation proxy error:", error);

    return backendProxyError(
      { detail: "连接后端会话删除接口失败，请确认后端服务已启动。" },
      502
    );
  }
}
