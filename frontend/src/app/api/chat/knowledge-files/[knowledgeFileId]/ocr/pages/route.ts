import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

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
      )}/ocr/pages`,
    });
  } catch (error) {
    console.error("Backend PDF OCR quality report proxy error:", error);
    return backendProxyError(
      { detail: "连接后端 OCR 质量巡检接口失败，请确认后端服务已启动。" },
      502,
    );
  }
}
