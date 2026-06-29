import {
  backendProxyError,
  encodeBackendPathSegment,
  proxyToBackend,
} from "@/lib/api-proxy";

export const runtime = "nodejs";

function getBackendRetrievalSettingsPath(knowledgeBaseId: string) {
  return `/chat/knowledge-base/${encodeBackendPathSegment(
    knowledgeBaseId
  )}/retrieval-settings`;
}

type RetrievalSettingsParams = {
  params: Promise<{ knowledgeBaseId: string }>;
};

export async function GET(
  request: Request,
  { params }: RetrievalSettingsParams
) {
  try {
    const { knowledgeBaseId } = await params;
    return await proxyToBackend({
      request,
      method: "GET",
      path: getBackendRetrievalSettingsPath(knowledgeBaseId),
    });
  } catch (error) {
    console.error("Backend retrieval settings proxy error:", error);

    return backendProxyError(
      { detail: "连接后端检索设置接口失败，请确认后端服务已启动。" },
      502
    );
  }
}

export async function PATCH(
  request: Request,
  { params }: RetrievalSettingsParams
) {
  try {
    const { knowledgeBaseId } = await params;
    return await proxyToBackend({
      request,
      method: "PATCH",
      path: getBackendRetrievalSettingsPath(knowledgeBaseId),
      contentType: "application/json",
    });
  } catch (error) {
    console.error("Backend retrieval settings update proxy error:", error);

    return backendProxyError(
      { detail: "保存检索设置失败，请确认后端服务已启动。" },
      502
    );
  }
}
