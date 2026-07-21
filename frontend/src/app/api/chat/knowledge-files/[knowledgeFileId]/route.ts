import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ knowledgeFileId: string }> },
) {
  try {
    const { knowledgeFileId } = await params;
    return await proxyToBackend({
      request,
      method: "DELETE",
      path: `/chat/knowledge-files/${encodeBackendPathSegment(
        knowledgeFileId,
      )}`,
    });
  } catch (error) {
    console.error("Backend knowledge file permanent delete proxy error:", error);
    return backendProxyError(
      { detail: "连接后端永久删除知识文件接口失败，请确认后端服务已启动。" },
      502,
    );
  }
}
