import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ knowledgeFileId: string }> },
) {
  try {
    const { knowledgeFileId } = await params;
    return await proxyToBackend({
      request,
      method: "GET",
      path: `/chat/knowledge-files/${encodeBackendPathSegment(
        knowledgeFileId,
      )}/content`,
      accept: "*/*",
      fallbackContentType: "application/octet-stream",
      stream: true,
    });
  } catch (error) {
    console.error("Backend knowledge file content proxy error:", error);
    return backendProxyError(
      { detail: "连接后端原始文件接口失败，请确认后端服务已启动。" },
      502,
    );
  }
}
