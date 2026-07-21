import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

type KnowledgeBaseParams = {
  params: Promise<{ knowledgeBaseId: string }>;
};

function getBackendPath(knowledgeBaseId: string) {
  return `/chat/knowledge-base/${encodeBackendPathSegment(knowledgeBaseId)}`;
}

export async function PATCH(request: Request, { params }: KnowledgeBaseParams) {
  try {
    const { knowledgeBaseId } = await params;
    return await proxyToBackend({
      request,
      method: "PATCH",
      path: getBackendPath(knowledgeBaseId),
      contentType: "application/json",
    });
  } catch (error) {
    console.error("Backend knowledge base rename proxy error:", error);
    return backendProxyError(
      { detail: "连接后端重命名知识库接口失败，请确认后端服务已启动。" },
      502,
    );
  }
}

export async function DELETE(request: Request, { params }: KnowledgeBaseParams) {
  try {
    const { knowledgeBaseId } = await params;
    return await proxyToBackend({
      request,
      method: "DELETE",
      path: getBackendPath(knowledgeBaseId),
    });
  } catch (error) {
    console.error("Backend knowledge base delete proxy error:", error);
    return backendProxyError(
      { detail: "连接后端删除知识库接口失败，请确认后端服务已启动。" },
      502,
    );
  }
}
