import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

type OcrBatchRetryParams = {
  params: Promise<{ knowledgeFileId: string; jobId: string }>;
};

/** 代理失败 OCR 批次的受控重试。 */
export async function POST(
  request: Request,
  { params }: OcrBatchRetryParams,
) {
  try {
    const { knowledgeFileId, jobId } = await params;
    return await proxyToBackend({
      request,
      method: "POST",
      path: `/chat/knowledge-files/${encodeBackendPathSegment(
        knowledgeFileId,
      )}/ocr/reindex-jobs/${encodeBackendPathSegment(jobId)}/retry`,
      bodyMode: "none",
    });
  } catch (error) {
    console.error("Backend PDF OCR batch retry proxy error:", error);
    return backendProxyError(
      { detail: "连接后端 OCR 批次重试接口失败，请确认后端服务已启动。" },
      502,
    );
  }
}
