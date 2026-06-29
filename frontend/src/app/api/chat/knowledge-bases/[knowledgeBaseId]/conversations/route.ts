import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

function getBackendPath(knowledgeBaseId: string) {
  return `/chat/knowledge-bases/${encodeBackendPathSegment(
    knowledgeBaseId
  )}/conversations`;
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ knowledgeBaseId: string }> }
) {
  try {
    const { knowledgeBaseId } = await params;
    return await proxyToBackend({
      request,
      method: "GET",
      path: getBackendPath(knowledgeBaseId),
    });
  } catch (error) {
    console.error("Backend knowledge base conversations proxy error:", error);
    return backendProxyError(
      { detail: "连接后端会话列表接口失败，请确认后端服务已启动。" },
      502
    );
  }
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
    });
  } catch (error) {
    console.error("Backend create conversation proxy error:", error);
    return backendProxyError(
      { detail: "连接后端创建会话接口失败，请确认后端服务已启动。" },
      502
    );
  }
}
