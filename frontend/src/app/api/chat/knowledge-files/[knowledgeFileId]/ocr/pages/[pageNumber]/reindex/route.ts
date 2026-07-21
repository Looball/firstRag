import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

type OcrPageReindexParams = {
  params: Promise<{ knowledgeFileId: string; pageNumber: string }>;
};

export async function POST(
  request: Request,
  { params }: OcrPageReindexParams,
) {
  try {
    const { knowledgeFileId, pageNumber } = await params;
    return await proxyToBackend({
      request,
      method: "POST",
      path: `/chat/knowledge-files/${encodeBackendPathSegment(
        knowledgeFileId,
      )}/ocr/pages/${encodeBackendPathSegment(pageNumber)}/reindex`,
      bodyMode: "none",
    });
  } catch (error) {
    console.error("Backend PDF OCR page reindex proxy error:", error);
    return backendProxyError(
      { detail: "连接后端 OCR 重新识别接口失败，请确认后端服务已启动。" },
      502,
    );
  }
}
