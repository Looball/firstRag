import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

function getBackendFilesPath(knowledgeBaseId: string) {
  return `/chat/knowledge-base/${encodeBackendPathSegment(
    knowledgeBaseId
  )}/files`;
}

type KnowledgeBaseFilesParams = {
  params: Promise<{ knowledgeBaseId: string }>;
};

export async function GET(
  request: Request,
  { params }: KnowledgeBaseFilesParams
) {
  try {
    const { knowledgeBaseId } = await params;
    return await proxyToBackend({
      request,
      method: "GET",
      path: getBackendFilesPath(knowledgeBaseId),
    });
  } catch (error) {
    console.error("Backend knowledge files proxy error:", error);

    return backendProxyError(
      { detail: "连接后端知识库文件接口失败，请确认后端服务已启动。" },
      502
    );
  }
}

export async function POST(
  request: Request,
  { params }: KnowledgeBaseFilesParams
) {
  try {
    const { knowledgeBaseId } = await params;
    return await proxyToBackend({
      request,
      method: "POST",
      path: getBackendFilesPath(knowledgeBaseId),
      bodyMode: "formData",
    });
  } catch (error) {
    console.error("Backend knowledge file upload proxy error:", error);

    return backendProxyError(
      { detail: "连接后端文件上传接口失败，请确认后端服务已启动。" },
      502
    );
  }
}
