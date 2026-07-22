import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

type OcrPagesReindexParams = {
  params: Promise<{ knowledgeFileId: string }>;
};

/** 代理文件级多页 OCR 重新识别批次。 */
export async function POST(
  request: Request,
  { params }: OcrPagesReindexParams,
) {
  try {
    const { knowledgeFileId } = await params;
    return await proxyToBackend({
      request,
      method: "POST",
      path: `/chat/knowledge-files/${encodeBackendPathSegment(
        knowledgeFileId,
      )}/ocr/pages/reindex`,
      bodyMode: "text",
    });
  } catch (error) {
    console.error("Backend PDF OCR batch reindex proxy error:", error);
    return backendProxyError(
      { detail: "连接后端批量 OCR 重新识别接口失败，请确认后端服务已启动。" },
      502,
    );
  }
}
