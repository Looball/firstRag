import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

function getBackendPath(knowledgeBaseId: string) {
  return `/chat/knowledge-base/${encodeBackendPathSegment(
    knowledgeBaseId
  )}/vectors`;
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ knowledgeBaseId: string }> }
) {
  try {
    const { knowledgeBaseId } = await params;
    return await proxyToBackend({
      request,
      method: "POST",
      path: getBackendPath(knowledgeBaseId),
      bodyMode: "none",
    });
  } catch (error) {
    console.error("Backend knowledge base vector index proxy error:", error);

    return backendProxyError(
      { detail: "连接后端知识库向量化接口失败，请确认后端服务已启动。" },
      502
    );
  }
}
