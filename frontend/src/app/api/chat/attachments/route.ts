import { backendProxyError, proxyToBackend } from "@/lib/api-proxy";

export const runtime = "nodejs";

export async function POST(request: Request) {
  try {
    const requestUrl = new URL(request.url);
    const conversationId = requestUrl.searchParams.get("conversation_id") || "";

    return await proxyToBackend({
      request,
      method: "POST",
      path: `/chat/attachments?conversation_id=${encodeURIComponent(conversationId)}`,
      bodyMode: "formData",
    });
  } catch (error) {
    console.error("Backend chat attachment upload proxy error:", error);

    return backendProxyError(
      { detail: "上传图片失败，请确认后端服务已启动。" },
      502
    );
  }
}
