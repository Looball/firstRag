import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

type OcrPageHistoryParams = {
  params: Promise<{ knowledgeFileId: string; pageNumber: string }>;
};

/** 代理当前用户指定 PDF 页面的 OCR 识别历史。 */
export async function GET(
  request: Request,
  { params }: OcrPageHistoryParams,
) {
  try {
    const { knowledgeFileId, pageNumber } = await params;
    return await proxyToBackend({
      request,
      method: "GET",
      path: `/chat/knowledge-files/${encodeBackendPathSegment(
        knowledgeFileId,
      )}/ocr/pages/${encodeBackendPathSegment(pageNumber)}/history`,
      bodyMode: "none",
    });
  } catch (error) {
    console.error("Backend PDF OCR history proxy error:", error);
    return backendProxyError(
      { detail: "连接后端 OCR 识别历史接口失败，请确认后端服务已启动。" },
      502,
    );
  }
}
