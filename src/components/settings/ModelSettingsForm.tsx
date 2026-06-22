"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useMemo, useState } from "react";
import {
  AUTH_STORAGE_KEY,
  buildAuthorizationHeader,
  getAuthUsername,
  parseAuthState,
} from "@/lib/auth";
import {
  DEFAULT_USER_LLM_SETTINGS,
  getSettingsMessage,
  isSuccessfulResponse,
  parseUserLLMSettings,
  toUserLLMSettingsPayload,
  type CredentialMode,
  type UserLLMSettings,
} from "@/lib/user-settings";

const providers = [
  { value: "deepseek", label: "DeepSeek", models: ["deepseek-chat", "deepseek-reasoner"] },
  { value: "qwen", label: "通义千问", models: ["qwen-turbo", "qwen-plus", "qwen-max"] },
  { value: "kimi", label: "Kimi", models: ["moonshot-v1-8k", "kimi-k2"] },
  { value: "zhipu", label: "智谱", models: ["glm-4-flash", "glm-4-plus"] },
  { value: "doubao", label: "豆包", models: ["doubao-seed-1-6-250615"] },
  { value: "minimax", label: "MiniMax", models: ["MiniMax-Text-01"] },
  { value: "custom", label: "自定义兼容服务", models: [] },
] as const;

type RequestState = "idle" | "loading" | "success" | "error";

function getDefaultModel(provider: string) {
  return providers.find((item) => item.value === provider)?.models[0] || "";
}

function getResponseData(response: Response) {
  return response.json().catch(() => null) as Promise<unknown>;
}

export function ModelSettingsForm() {
  const [username, setUsername] = useState("");
  const [settings, setSettings] = useState<UserLLMSettings>(
    DEFAULT_USER_LLM_SETTINGS
  );
  const [apiKey, setApiKey] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [saveState, setSaveState] = useState<RequestState>("idle");
  const [testState, setTestState] = useState<RequestState>("idle");
  const [notice, setNotice] = useState("");

  const provider = useMemo(
    () => providers.find((item) => item.value === settings.provider),
    [settings.provider]
  );
  const modelCandidates = provider?.models || [];
  const isCustomProvider = settings.provider === "custom";
  const isUserKeyMode = settings.credentialMode === "user";

  useEffect(() => {
    let isCancelled = false;
    const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

    if (!authState) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      window.location.href = "/login";
      return;
    }

    const authorization = buildAuthorizationHeader(authState);
    const authenticatedUsername = getAuthUsername(authState);

    async function loadSettings() {
      try {
        const response = await fetch("/api/settings", {
          headers: { Authorization: authorization },
          cache: "no-store",
        });
        const data = await getResponseData(response);

        if (!response.ok) {
          throw new Error(getSettingsMessage(data, "读取设置失败，请稍后重试。"));
        }

        const nextSettings = parseUserLLMSettings(data);

        if (!nextSettings) {
          throw new Error("后端设置响应格式无效，请联系管理员。");
        }

        if (!isCancelled) {
          setSettings(nextSettings);
        }
      } catch (error) {
        if (!isCancelled) {
          setNotice(
            error instanceof Error ? error.message : "读取设置失败，请稍后重试。"
          );
        }
      } finally {
        if (!isCancelled) {
          setUsername(authenticatedUsername);
          setIsLoading(false);
        }
      }
    }

    void loadSettings();

    return () => {
      isCancelled = true;
    };
  }, []);

  function updateCredentialMode(credentialMode: CredentialMode) {
    setSettings((current) => ({ ...current, credentialMode }));
    setApiKey("");
    setNotice("");
  }

  function updateProvider(providerValue: string) {
    setSettings((current) => ({
      ...current,
      provider: providerValue,
      model: getDefaultModel(providerValue),
      baseUrl: providerValue === "custom" ? current.baseUrl : "",
    }));
    setNotice("");
  }

  function getPayload() {
    if (!settings.model.trim()) {
      throw new Error("请输入模型名称。");
    }

    if (isCustomProvider && !settings.baseUrl.trim()) {
      throw new Error("自定义兼容服务需要填写 API 地址。");
    }

    if (isUserKeyMode && !settings.hasApiKey && !apiKey.trim()) {
      throw new Error("请输入 API Key 后再继续。");
    }

    return toUserLLMSettingsPayload(settings, apiKey);
  }

  async function handleTest() {
    setTestState("loading");
    setNotice("");

    try {
      const payload = getPayload();
      const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

      if (!authState) {
        window.location.href = "/login";
        return;
      }

      const response = await fetch("/api/settings", {
        method: "POST",
        headers: {
          Authorization: buildAuthorizationHeader(authState),
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      const data = await getResponseData(response);

      if (!response.ok || !isSuccessfulResponse(data)) {
        throw new Error(getSettingsMessage(data, "连接测试失败，请检查配置。"));
      }

      setTestState("success");
      setNotice(getSettingsMessage(data, "连接测试通过。"));
    } catch (error) {
      setTestState("error");
      setNotice(error instanceof Error ? error.message : "连接测试失败，请检查配置。");
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaveState("loading");
    setNotice("");

    try {
      const payload = getPayload();
      const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

      if (!authState) {
        window.location.href = "/login";
        return;
      }

      const response = await fetch("/api/settings", {
        method: "PATCH",
        headers: {
          Authorization: buildAuthorizationHeader(authState),
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      const data = await getResponseData(response);

      if (!response.ok || !isSuccessfulResponse(data)) {
        throw new Error(getSettingsMessage(data, "保存设置失败，请稍后重试。"));
      }

      setSettings((current) => ({
        ...current,
        hasApiKey: current.credentialMode === "user" ? current.hasApiKey || Boolean(apiKey.trim()) : false,
      }));
      setApiKey("");
      setSaveState("success");
      setNotice(getSettingsMessage(data, "设置已保存。"));
    } catch (error) {
      setSaveState("error");
      setNotice(error instanceof Error ? error.message : "保存设置失败，请稍后重试。");
    }
  }

  if (isLoading) {
    return (
      <main className="research-canvas flex min-h-screen items-center justify-center px-4">
        <p className="font-utility text-xs font-semibold text-[var(--research)]">正在读取模型设置...</p>
      </main>
    );
  }

  return (
    <main className="research-canvas min-h-screen px-4 py-5 md:px-8 md:py-10">
      <form onSubmit={handleSubmit} className="research-enter mx-auto w-full max-w-3xl border border-[var(--line)] bg-[var(--paper)] shadow-[0_20px_50px_rgba(23,32,31,0.08)]">
        <header className="border-b border-[var(--line)] px-6 py-7 md:px-10">
          <div className="flex items-start justify-between gap-5">
            <div>
              <p className="font-utility text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--research)]">模型控制台</p>
              <h1 className="font-display mt-3 text-3xl font-semibold text-[var(--foreground)]">聊天模型设置</h1>
              <p className="mt-2 text-sm text-[var(--ink-muted)]">{username ? `${username} 的设置` : "管理当前账号的模型凭据与默认模型。"}</p>
            </div>
            <Link href="/" className="shrink-0 text-sm font-semibold text-[var(--research)] underline decoration-[var(--index)] decoration-2 underline-offset-4">返回工作台</Link>
          </div>
        </header>

        <div className="space-y-9 px-6 py-8 md:px-10 md:py-10">
          <section aria-labelledby="credential-mode-title">
            <p id="credential-mode-title" className="font-utility text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--ink-muted)]">凭据来源</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              {(["platform", "user"] as const).map((mode) => {
                const selected = settings.credentialMode === mode;
                return <button key={mode} type="button" onClick={() => updateCredentialMode(mode)} className={`border-l-4 px-4 py-4 text-left transition ${selected ? "border-[var(--coral)] bg-[var(--foreground)] text-white" : "border-transparent bg-[var(--paper-muted)] text-[var(--foreground)] hover:border-[var(--index)]"}`}>
                  <span className="block text-sm font-semibold">{mode === "platform" ? "使用平台 Key" : "使用自己的 Key"}</span>
                  <span className={`mt-1 block text-xs leading-5 ${selected ? "text-[#b8c8c3]" : "text-[var(--ink-muted)]"}`}>{mode === "platform" ? "由平台默认凭据提供服务。" : "为当前账号安全保存独立凭据。"}</span>
                </button>;
              })}
            </div>
          </section>

          <section className="grid gap-5 md:grid-cols-2" aria-label="模型参数">
            <label className="font-utility text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--ink-muted)]">厂商
              <select value={settings.provider} onChange={(event) => updateProvider(event.target.value)} className="research-focus mt-2 w-full border border-[var(--line)] bg-white px-3 py-3 text-sm normal-case tracking-normal text-[var(--foreground)]">
                {providers.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
            </label>
            <label className="font-utility text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--ink-muted)]">模型名
              <input list="model-candidates" value={settings.model} onChange={(event) => setSettings((current) => ({ ...current, model: event.target.value }))} placeholder="输入模型名称" className="research-focus mt-2 w-full border border-[var(--line)] bg-white px-3 py-3 text-sm normal-case tracking-normal text-[var(--foreground)]" />
              <datalist id="model-candidates">{modelCandidates.map((model) => <option key={model} value={model} />)}</datalist>
            </label>
          </section>

          {isCustomProvider && <label className="font-utility block text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--ink-muted)]">API 地址
            <input type="url" value={settings.baseUrl} onChange={(event) => setSettings((current) => ({ ...current, baseUrl: event.target.value }))} placeholder="https://api.example.com/v1" className="research-focus mt-2 w-full border border-[var(--line)] bg-white px-3 py-3 text-sm normal-case tracking-normal text-[var(--foreground)]" />
          </label>}

          {isUserKeyMode && <section className="border border-[var(--line)] bg-[var(--paper-muted)] p-5" aria-labelledby="api-key-title">
            <div className="flex items-baseline justify-between gap-4"><p id="api-key-title" className="font-utility text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--ink-muted)]">API Key</p>{settings.hasApiKey && <span className="text-xs font-semibold text-[var(--research)]">已保存</span>}</div>
            <div className="mt-3 flex border border-[var(--line)] bg-white focus-within:border-[var(--research)] focus-within:ring-3 focus-within:ring-[var(--research)]/15">
              <input type={showApiKey ? "text" : "password"} value={apiKey} onChange={(event) => setApiKey(event.target.value)} autoComplete="off" placeholder={settings.hasApiKey ? "已保存；填写可替换现有 Key" : "请输入 API Key"} className="min-w-0 flex-1 bg-transparent px-3 py-3 text-sm text-[var(--foreground)] outline-none" />
              <button type="button" onClick={() => setShowApiKey((current) => !current)} className="border-l border-[var(--line)] px-4 text-xs font-semibold text-[var(--ink-muted)] hover:bg-[var(--paper-muted)]">{showApiKey ? "隐藏" : "显示"}</button>
            </div>
            <p className="mt-2 text-xs leading-5 text-[var(--ink-muted)]">密钥只会在保存或测试时发送到后端，页面不会回显或存入浏览器。</p>
          </section>}

          <div className="border-t border-[var(--line)] pt-6">
            <p role="status" className={`min-h-5 text-sm ${saveState === "error" || testState === "error" ? "text-[#9b3c29]" : "text-[var(--ink-muted)]"}`}>{notice || "保存后，工作台的下一次对话会使用当前账号的模型设置。"}</p>
            <div className="mt-4 flex flex-wrap gap-3">
              <button type="button" onClick={() => void handleTest()} disabled={testState === "loading" || saveState === "loading"} className="border border-[var(--research)] px-5 py-3 text-sm font-semibold text-[var(--research)] transition hover:bg-[var(--paper-muted)] disabled:border-[var(--line)] disabled:text-[var(--ink-muted)]">{testState === "loading" ? "测试中..." : "测试连接"}</button>
              <button type="submit" disabled={saveState === "loading" || testState === "loading"} className="bg-[var(--research)] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[var(--research-dark)] disabled:bg-[var(--line)]">{saveState === "loading" ? "保存中..." : "保存设置"}</button>
            </div>
          </div>
        </div>
      </form>
    </main>
  );
}
