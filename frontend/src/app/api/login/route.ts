import { backendProxyError, proxyToBackend } from "@/lib/api-proxy";

export const runtime = "nodejs";

const backendLoginPath = process.env.BACKEND_LOGIN_PATH || "/login";

function getBackendLoginPath() {
  return backendLoginPath.startsWith("/")
    ? backendLoginPath
    : `/${backendLoginPath}`;
}

export async function POST(request: Request) {
  try {
    return await proxyToBackend({
      request,
      method: "POST",
      path: getBackendLoginPath(),
      includeApiPrefix: false,
      copySetCookie: true,
    });
  } catch (error) {
    console.error("Login proxy error:", error);

    return backendProxyError(
      { error: "连接后端登录接口失败，请确认后端服务已启动。" },
      502
    );
  }
}
