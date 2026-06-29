import { backendProxyError, proxyToBackend } from "@/lib/api-proxy";

export const runtime = "nodejs";

export async function GET(request: Request) {
  try {
    return await proxyToBackend({
      request,
      method: "GET",
      path: "/user/settings",
      includeApiPrefix: false,
    });
  } catch (error) {
    console.error("Backend settings proxy error:", error);
    return backendProxyError(
      { detail: "读取设置失败，请确认后端服务已启动。" },
      502
    );
  }
}

export async function PATCH(request: Request) {
  try {
    return await proxyToBackend({
      request,
      method: "PATCH",
      path: "/user/settings",
      includeApiPrefix: false,
    });
  } catch (error) {
    console.error("Backend update settings proxy error:", error);
    return backendProxyError(
      { detail: "保存设置失败，请确认后端服务已启动。" },
      502
    );
  }
}

export async function POST(request: Request) {
  try {
    return await proxyToBackend({
      request,
      method: "POST",
      path: "/user/settings/test",
      includeApiPrefix: false,
    });
  } catch (error) {
    console.error("Backend settings test proxy error:", error);
    return backendProxyError(
      { detail: "测试设置失败，请确认后端服务已启动。" },
      502
    );
  }
}
