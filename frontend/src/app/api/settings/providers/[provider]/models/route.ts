import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ provider: string }> }
) {
  try {
    const { provider } = await params;
    return await proxyToBackend({
      request,
      method: "POST",
      path: `/user/settings/providers/${encodeBackendPathSegment(
        provider
      )}/models`,
      bodyMode: "none",
      includeApiPrefix: false,
    });
  } catch (error) {
    console.error("Backend provider models proxy error:", error);
    return backendProxyError(
      { detail: "读取厂商模型列表失败，请确认后端服务已启动。" },
      502
    );
  }
}
