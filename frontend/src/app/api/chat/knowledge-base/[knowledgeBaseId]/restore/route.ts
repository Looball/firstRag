import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ knowledgeBaseId: string }> },
) {
  try {
    const { knowledgeBaseId } = await params;
    return await proxyToBackend({
      request,
      method: "POST",
      path: `/chat/knowledge-base/${encodeBackendPathSegment(
        knowledgeBaseId,
      )}/restore`,
      bodyMode: "none",
    });
  } catch (error) {
    console.error("Backend knowledge base restore proxy error:", error);
    return backendProxyError(
      { detail: "连接后端恢复知识库接口失败，请确认后端服务已启动。" },
      502,
    );
  }
}
