import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

function getBackendPath(knowledgeBaseId: string, conversationId: string) {
  return `/chat/knowledge-bases/${encodeBackendPathSegment(
    knowledgeBaseId
  )}/conversations/${encodeBackendPathSegment(conversationId)}`;
}

export async function PATCH(
  request: Request,
  {
    params,
  }: {
    params: Promise<{ knowledgeBaseId: string; conversationId: string }>;
  }
) {
  try {
    const { knowledgeBaseId, conversationId } = await params;
    return await proxyToBackend({
      request,
      method: "PATCH",
      path: getBackendPath(knowledgeBaseId, conversationId),
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
  {
    params,
  }: {
    params: Promise<{ knowledgeBaseId: string; conversationId: string }>;
  }
) {
  try {
    const { knowledgeBaseId, conversationId } = await params;
    return await proxyToBackend({
      request,
      method: "DELETE",
      path: getBackendPath(knowledgeBaseId, conversationId),
    });
  } catch (error) {
    console.error("Backend delete conversation proxy error:", error);
    return backendProxyError(
      { detail: "连接后端删除会话接口失败，请确认后端服务已启动。" },
      502
    );
  }
}
