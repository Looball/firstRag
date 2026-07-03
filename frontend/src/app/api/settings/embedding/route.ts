import { backendProxyError, proxyToBackend } from "@/lib/api-proxy";

export const runtime = "nodejs";

export async function GET(request: Request) {
  try {
    return await proxyToBackend({
      request,
      method: "GET",
      path: "/user/settings/embedding",
      includeApiPrefix: false,
    });
  } catch (error) {
    console.error("Backend embedding settings proxy error:", error);
    return backendProxyError(
      { detail: "读取向量模型设置失败，请确认后端服务已启动。" },
      502
    );
  }
}

export async function PATCH(request: Request) {
  try {
    return await proxyToBackend({
      request,
      method: "PATCH",
      path: "/user/settings/embedding",
      includeApiPrefix: false,
    });
  } catch (error) {
    console.error("Backend update embedding settings proxy error:", error);
    return backendProxyError(
      { detail: "保存向量模型设置失败，请确认后端服务已启动。" },
      502
    );
  }
}

export async function POST(request: Request) {
  try {
    return await proxyToBackend({
      request,
      method: "POST",
      path: "/user/settings/embedding/test",
      includeApiPrefix: false,
    });
  } catch (error) {
    console.error("Backend embedding settings test proxy error:", error);
    return backendProxyError(
      { detail: "测试向量模型设置失败，请确认后端服务已启动。" },
      502
    );
  }
}
