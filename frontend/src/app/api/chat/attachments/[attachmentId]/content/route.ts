import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ attachmentId: string }> },
) {
  try {
    const { attachmentId } = await params;
    return await proxyToBackend({
      request,
      method: "GET",
      path: `/chat/attachments/${encodeBackendPathSegment(attachmentId)}/content`,
      accept: "image/*",
      fallbackContentType: "application/octet-stream",
      stream: true,
    });
  } catch (error) {
    console.error("Backend chat attachment content proxy error:", error);

    return backendProxyError(
      { detail: "读取图片失败，请确认后端服务已启动。" },
      502
    );
  }
}
