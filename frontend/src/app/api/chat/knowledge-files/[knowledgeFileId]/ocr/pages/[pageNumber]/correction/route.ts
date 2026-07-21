import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

type OcrPageCorrectionParams = {
  params: Promise<{ knowledgeFileId: string; pageNumber: string }>;
};

async function proxyOcrCorrection(
  request: Request,
  params: OcrPageCorrectionParams["params"],
  method: "DELETE" | "GET" | "PATCH",
) {
  const { knowledgeFileId, pageNumber } = await params;
  return proxyToBackend({
    request,
    method,
    path: `/chat/knowledge-files/${encodeBackendPathSegment(
      knowledgeFileId,
    )}/ocr/pages/${encodeBackendPathSegment(pageNumber)}/correction`,
  });
}

export async function GET(
  request: Request,
  { params }: OcrPageCorrectionParams,
) {
  try {
    return await proxyOcrCorrection(request, params, "GET");
  } catch (error) {
    console.error("Backend PDF OCR correction read proxy error:", error);
    return backendProxyError(
      { detail: "连接后端 OCR 校对读取接口失败，请确认后端服务已启动。" },
      502,
    );
  }
}

export async function PATCH(
  request: Request,
  { params }: OcrPageCorrectionParams,
) {
  try {
    return await proxyOcrCorrection(request, params, "PATCH");
  } catch (error) {
    console.error("Backend PDF OCR correction save proxy error:", error);
    return backendProxyError(
      { detail: "连接后端 OCR 校对保存接口失败，请确认后端服务已启动。" },
      502,
    );
  }
}

export async function DELETE(
  request: Request,
  { params }: OcrPageCorrectionParams,
) {
  try {
    return await proxyOcrCorrection(request, params, "DELETE");
  } catch (error) {
    console.error("Backend PDF OCR correction delete proxy error:", error);
    return backendProxyError(
      { detail: "连接后端 OCR 校对撤销接口失败，请确认后端服务已启动。" },
      502,
    );
  }
}
