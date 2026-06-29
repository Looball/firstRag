import { backendProxyError, proxyToBackend } from "@/lib/api-proxy";

export const runtime = "nodejs";

const backendRegisterPath = process.env.BACKEND_REGISTER_PATH || "/register";

function getBackendRegisterPath() {
  return backendRegisterPath.startsWith("/")
    ? backendRegisterPath
    : `/${backendRegisterPath}`;
}

export async function POST(request: Request) {
  try {
    return await proxyToBackend({
      request,
      method: "POST",
      path: getBackendRegisterPath(),
      includeApiPrefix: false,
      copySetCookie: true,
    });
  } catch (error) {
    console.error("Register proxy error:", error);

    return backendProxyError(
      { error: "连接后端注册接口失败，请确认后端服务已启动。" },
      502
    );
  }
}
