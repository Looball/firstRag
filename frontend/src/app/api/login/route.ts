import { NextResponse } from "next/server";

export const runtime = "nodejs";

const backendOrigin =
  process.env.BACKEND_ORIGIN?.replace(/\/+$/, "") || "http://127.0.0.1:8000";
const backendLoginPath = process.env.BACKEND_LOGIN_PATH || "/login";

function getBackendLoginUrl() {
  const normalizedPath = backendLoginPath.startsWith("/")
    ? backendLoginPath
    : `/${backendLoginPath}`;

  return `${backendOrigin}${normalizedPath}`;
}

export async function POST(request: Request) {
  try {
    const body = await request.text();
    const upstreamResponse = await fetch(getBackendLoginUrl(), {
      method: "POST",
      headers: {
        "Content-Type": request.headers.get("Content-Type") || "application/json",
      },
      body,
      cache: "no-store",
    });
    const responseText = await upstreamResponse.text();
    const response = new NextResponse(responseText, {
      status: upstreamResponse.status,
      headers: {
        "Content-Type":
          upstreamResponse.headers.get("Content-Type") || "application/json",
      },
    });
    const setCookie = upstreamResponse.headers.get("Set-Cookie");

    if (setCookie) {
      response.headers.set("Set-Cookie", setCookie);
    }

    return response;
  } catch (error) {
    console.error("Login proxy error:", error);

    return NextResponse.json(
      { error: "连接后端登录接口失败，请确认后端服务已启动。" },
      { status: 502 }
    );
  }
}
