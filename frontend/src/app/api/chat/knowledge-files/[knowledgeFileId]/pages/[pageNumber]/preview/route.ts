import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

export async function GET(
  request: Request,
  {
    params,
  }: {
    params: Promise<{ knowledgeFileId: string; pageNumber: string }>;
  },
) {
  try {
    const { knowledgeFileId, pageNumber } = await params;
    return await proxyToBackend({
      request,
      method: "GET",
      path: `/chat/knowledge-files/${encodeBackendPathSegment(
        knowledgeFileId,
      )}/pages/${encodeBackendPathSegment(pageNumber)}/preview`,
      accept: "image/png",
      fallbackContentType: "image/png",
      stream: true,
    });
  } catch (error) {
    console.error("Backend PDF page preview proxy error:", error);
    return backendProxyError(
      { detail: "连接后端 PDF 页面预览接口失败，请确认后端服务已启动。" },
      502,
    );
  }
}
