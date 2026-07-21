import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

type SourcePreviewParams = {
  params: Promise<{ knowledgeFileId: string; chunkIndex: string }>;
};

export async function GET(request: Request, { params }: SourcePreviewParams) {
  try {
    const { knowledgeFileId, chunkIndex } = await params;
    const searchParams = new URL(request.url).searchParams;
    const radius = searchParams.get("radius") || "1";
    const indexVersion = searchParams.get("index_version");
    const indexVersionQuery = indexVersion
      ? `&index_version=${encodeURIComponent(indexVersion)}`
      : "";
    return await proxyToBackend({
      request,
      method: "GET",
      path: `/chat/knowledge-files/${encodeBackendPathSegment(
        knowledgeFileId,
      )}/chunks/${encodeBackendPathSegment(chunkIndex)}?radius=${encodeURIComponent(
        radius,
      )}${indexVersionQuery}`,
    });
  } catch (error) {
    console.error("Backend source preview proxy error:", error);
    return backendProxyError(
      { detail: "连接后端引用原文接口失败，请确认后端服务已启动。" },
      502,
    );
  }
}
