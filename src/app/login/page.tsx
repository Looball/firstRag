"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import {
  AUTH_STORAGE_KEY,
  getAuthErrorMessage,
  isAuthState,
  readAuthResponse,
} from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const normalizedUsername = username.trim();

    if (!normalizedUsername || !password) {
      setError("请输入用户名和密码。");
      return;
    }

    setError("");
    setIsSubmitting(true);

    try {
      const response = await fetch("/api/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: normalizedUsername,
          password,
        }),
      });
      const data = await readAuthResponse(response);

      if (!response.ok) {
        throw new Error(getAuthErrorMessage(data, "登录失败，请稍后再试。"));
      }

      if (!isAuthState(data)) {
        throw new Error("登录响应缺少 access_token 或 token_type。");
      }

      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(data));
      router.push("/");
    } catch (loginError) {
      setError(
        loginError instanceof Error
          ? loginError.message
          : "登录失败，请稍后再试。"
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="research-canvas flex min-h-screen items-center justify-center px-4 py-10">
      <section className="research-paper research-enter w-full max-w-md border border-[#cbd5d1] p-7 md:p-10">
        <div className="border-b border-[#cbd5d1] pb-7">
          <div className="flex items-center justify-between gap-4">
            <p className="font-utility text-[11px] font-semibold uppercase text-[#176b62]">
              Research Desk
            </p>
            <span className="h-2.5 w-2.5 bg-[#e36b4f]" aria-hidden="true" />
          </div>
          <h1 className="font-display mt-8 text-4xl font-semibold text-[#17201f]">
            返回你的研究台
          </h1>
          <p className="mt-3 text-sm leading-6 text-[#64716d]">
            登录后继续查阅知识库、历史会话与研究记录。
          </p>
        </div>

        <form onSubmit={handleSubmit} className="mt-7 space-y-5">
          <div>
            <label
              htmlFor="username"
              className="font-utility block text-xs font-semibold text-[#46514e]"
            >
              用户名
            </label>
            <input
              id="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              className="research-focus mt-2 w-full border border-[#b9c6c1] bg-white px-4 py-3 text-[#17201f]"
              placeholder="请输入用户名"
            />
          </div>

          <div>
            <label
              htmlFor="password"
              className="font-utility block text-xs font-semibold text-[#46514e]"
            >
              密码
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              className="research-focus mt-2 w-full border border-[#b9c6c1] bg-white px-4 py-3 text-[#17201f]"
              placeholder="请输入密码"
            />
          </div>

          {error && (
            <div className="border-l-4 border-[#e36b4f] bg-[#fff1ed] px-4 py-3 text-sm text-[#9b3c29]">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-[#176b62] px-4 py-3.5 text-sm font-semibold text-white transition hover:bg-[#105149] disabled:bg-[#91aaa4]"
          >
            {isSubmitting ? "登录中..." : "登录"}
          </button>

          <p className="border-t border-[#dbe2df] pt-5 text-center text-sm text-[#64716d]">
            还没有账号？{" "}
            <a
              href="/register"
              className="font-semibold text-[#176b62] underline decoration-[#d5a83b] decoration-2 underline-offset-4"
            >
              注册账号
            </a>
          </p>
        </form>
      </section>
    </main>
  );
}
