import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

function getBackendPath(knowledgeFileId: string) {
  return `/chat/knowledge-files/${encodeBackendPathSegment(
    knowledgeFileId
  )}/vectors`;
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ knowledgeFileId: string }> }
) {
  try {
    const { knowledgeFileId } = await params;
    return await proxyToBackend({
      request,
      method: "POST",
      path: getBackendPath(knowledgeFileId),
      bodyMode: "none",
    });
  } catch (error) {
    console.error("Backend file vector index proxy error:", error);

    return backendProxyError(
      { detail: "连接后端文件向量化接口失败，请确认后端服务已启动。" },
      502
    );
  }
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ knowledgeFileId: string }> }
) {
  try {
    const { knowledgeFileId } = await params;
    return await proxyToBackend({
      request,
      method: "DELETE",
      path: getBackendPath(knowledgeFileId),
    });
  } catch (error) {
    console.error("Backend file vector delete proxy error:", error);

    return backendProxyError(
      { detail: "连接后端删除文件向量接口失败，请确认后端服务已启动。" },
      502
    );
  }
}
