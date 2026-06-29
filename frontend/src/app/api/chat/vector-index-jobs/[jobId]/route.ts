import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

function getBackendPath(jobId: string) {
  return `/chat/vector-index-jobs/${encodeBackendPathSegment(jobId)}`;
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ jobId: string }> }
) {
  try {
    const { jobId } = await params;
    return await proxyToBackend({
      request,
      method: "GET",
      path: getBackendPath(jobId),
    });
  } catch (error) {
    console.error("Backend vector index job proxy error:", error);

    return backendProxyError(
      { detail: "连接后端向量化任务状态接口失败，请确认后端服务已启动。" },
      502
    );
  }
}
