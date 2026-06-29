import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

function getBackendRelationPath(
  knowledgeBaseId: string,
  knowledgeFileId: string
) {
  return `/chat/knowledge-base/${encodeBackendPathSegment(
    knowledgeBaseId
  )}/files/${encodeBackendPathSegment(knowledgeFileId)}`;
}

type KnowledgeBaseFileRelationParams = {
  params: Promise<{ knowledgeBaseId: string; knowledgeFileId: string }>;
};

export async function POST(
  request: Request,
  { params }: KnowledgeBaseFileRelationParams
) {
  try {
    const { knowledgeBaseId, knowledgeFileId } = await params;
    return await proxyToBackend({
      request,
      method: "POST",
      path: getBackendRelationPath(knowledgeBaseId, knowledgeFileId),
      bodyMode: "none",
    });
  } catch (error) {
    console.error("Backend knowledge file attach proxy error:", error);

    return backendProxyError(
      { detail: "连接后端添加文件关联接口失败，请确认后端服务已启动。" },
      502
    );
  }
}

export async function DELETE(
  request: Request,
  { params }: KnowledgeBaseFileRelationParams
) {
  try {
    const { knowledgeBaseId, knowledgeFileId } = await params;
    return await proxyToBackend({
      request,
      method: "DELETE",
      path: getBackendRelationPath(knowledgeBaseId, knowledgeFileId),
    });
  } catch (error) {
    console.error("Backend knowledge file detach proxy error:", error);

    return backendProxyError(
      { detail: "连接后端解除文件关联接口失败，请确认后端服务已启动。" },
      502
    );
  }
}
