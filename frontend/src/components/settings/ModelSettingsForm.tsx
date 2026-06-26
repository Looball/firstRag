"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  AUTH_STORAGE_KEY,
  buildAuthorizationHeader,
  getAuthUsername,
  parseAuthState,
} from "@/lib/auth";
import {
  DEFAULT_USER_LLM_SETTINGS,
  FALLBACK_PROVIDER_PRESETS,
  getSettingsMessage,
  isSuccessfulResponse,
  parseSettingsTestResult,
  parseProviderModels,
  parseUserLLMSettings,
  parseProviderPresets,
  toUserLLMSettingsPayload,
  type CredentialMode,
  type ModelProviderPreset,
  type UserLLMSettings,
} from "@/lib/user-settings";

type RequestState = "idle" | "loading" | "success" | "error";
const CUSTOM_MODEL_VALUE = "__custom_model__";

function getResponseData(response: Response) {
  return response.json().catch(() => null) as Promise<unknown>;
}

function applyProviderCredentials(
  settings: UserLLMSettings,
  provider: ModelProviderPreset | undefined
) {
  if (!provider) {
    return settings;
  }

  return {
    ...settings,
    hasApiKey: provider.hasApiKey,
    apiKeyHint: provider.apiKeyHint,
  };
}

export function ModelSettingsForm() {
  const [username, setUsername] = useState("");
  const [activeSettings, setActiveSettings] =
    useState<UserLLMSettings | null>(null);
  const [settings, setSettings] = useState<UserLLMSettings>(
    DEFAULT_USER_LLM_SETTINGS
  );
  const [apiKey, setApiKey] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [modelCandidates, setModelCandidates] = useState<string[]>([]);
  const [isCustomModel, setIsCustomModel] = useState(false);
  const [providerPresets, setProviderPresets] = useState<ModelProviderPreset[]>(
    FALLBACK_PROVIDER_PRESETS
  );
  const [isLoading, setIsLoading] = useState(true);
  const [saveState, setSaveState] = useState<RequestState>("idle");
  const [testState, setTestState] = useState<RequestState>("idle");
  const [modelLoadState, setModelLoadState] = useState<RequestState>("idle");
  const [notice, setNotice] = useState("");
  const modelRequestIdRef = useRef(0);
  const modelRequestAbortRef = useRef<AbortController | null>(null);

  const provider = useMemo(
    () => providerPresets.find((item) => item.value === settings.provider),
    [providerPresets, settings.provider]
  );
  const requiresBaseUrl = provider?.requiresBaseUrl === true;
  const isUserKeyMode = settings.credentialMode === "user";
  const hasSavedApiKey = provider?.hasApiKey ?? settings.hasApiKey;
  const apiKeyHint = provider?.apiKeyHint ?? settings.apiKeyHint;

  function redirectToLogin() {
    localStorage.removeItem(AUTH_STORAGE_KEY);
    window.location.href = "/login";
  }

  function invalidateProviderModelRequest() {
    modelRequestIdRef.current += 1;
    modelRequestAbortRef.current?.abort();
    modelRequestAbortRef.current = null;
    setModelLoadState("idle");
  }

  async function loadSavedProviderModels(
    providerPreset: ModelProviderPreset,
    currentActiveSettings: UserLLMSettings | null
  ) {
    if (!providerPreset.hasApiKey) {
      return;
    }

    const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

    if (!authState) {
      redirectToLogin();
      return;
    }

    invalidateProviderModelRequest();
    const requestId = modelRequestIdRef.current;
    const controller = new AbortController();
    modelRequestAbortRef.current = controller;
    setModelLoadState("loading");

    try {
      const response = await fetch(
        `/api/settings/providers/${encodeURIComponent(providerPreset.value)}/models`,
        {
          method: "POST",
          headers: {
            Authorization: buildAuthorizationHeader(authState),
          },
          signal: controller.signal,
        }
      );
      const data = await getResponseData(response);

      if (response.status === 401) {
        redirectToLogin();
        return;
      }

      const models = response.ok ? parseProviderModels(data) : null;

      if (modelRequestIdRef.current !== requestId) {
        return;
      }

      if (!models) {
        throw new Error(getSettingsMessage(data, "模型列表获取失败，请稍后重试。"));
      }

      const activeModel =
        currentActiveSettings?.provider === providerPreset.value &&
        currentActiveSettings.model.trim() &&
        models.includes(currentActiveSettings.model)
          ? currentActiveSettings.model
          : "";

      setModelCandidates(models);
      setIsCustomModel(false);
      setSettings((current) =>
        current.provider === providerPreset.value
          ? { ...current, model: activeModel }
          : current
      );
      setModelLoadState("success");

      setNotice(
        activeModel
          ? `已恢复当前生效模型：${activeModel}`
          : models.length > 0
            ? "模型列表已加载，请选择模型。"
            : "该厂商未返回模型列表，请手动输入模型名。"
      );
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        if (modelRequestIdRef.current === requestId) {
          setModelCandidates([]);
          setIsCustomModel(false);
          setSettings((current) =>
            current.provider === providerPreset.value
              ? { ...current, model: "" }
              : current
          );
          setModelLoadState("error");
          setNotice(
            error instanceof Error
              ? error.message
              : "模型列表获取失败，请检查 API Key 或稍后重试。"
          );
        }
      }
    } finally {
      if (modelRequestIdRef.current === requestId) {
        modelRequestAbortRef.current = null;
      }
    }
  }

  async function refreshSettingsAndProviders(authorization: string) {
    try {
      const [response, providersResponse] = await Promise.all([
        fetch("/api/settings", {
          headers: { Authorization: authorization },
          cache: "no-store",
        }),
        fetch("/api/settings/providers", {
          headers: { Authorization: authorization },
          cache: "no-store",
        }),
      ]);

      if (response.status === 401 || providersResponse.status === 401) {
        redirectToLogin();
        return;
      }

      const [data, providersData] = await Promise.all([
        getResponseData(response),
        getResponseData(providersResponse),
      ]);
      const nextSettings = response.ok ? parseUserLLMSettings(data) : null;
      const presets = providersResponse.ok
        ? parseProviderPresets(providersData)
        : null;

      if (nextSettings) {
        const nextSettingsWithCredentialState = applyProviderCredentials(
          nextSettings,
          presets?.find((item) => item.value === nextSettings.provider)
        );
        setActiveSettings(nextSettingsWithCredentialState);
        setSettings(nextSettingsWithCredentialState);
      }

      if (presets) {
        setProviderPresets(presets);
      }
    } catch {
      // 测试状态提示优先于刷新失败，不额外暴露后端错误信息。
    }
  }

  useEffect(() => {
    let isCancelled = false;
    const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

    if (!authState) {
      redirectToLogin();
      return;
    }

    const authorization = buildAuthorizationHeader(authState);
    const authenticatedUsername = getAuthUsername(authState);

    async function loadSettings() {
      try {
        const [response, providersResponse] = await Promise.all([
          fetch("/api/settings", {
            headers: { Authorization: authorization },
            cache: "no-store",
          }),
          fetch("/api/settings/providers", {
            headers: { Authorization: authorization },
            cache: "no-store",
          }),
        ]);
        const [data, providersData] = await Promise.all([
          getResponseData(response),
          getResponseData(providersResponse),
        ]);

        if (response.status === 401 || providersResponse.status === 401) {
          redirectToLogin();
          return;
        }

        if (!response.ok) {
          throw new Error(getSettingsMessage(data, "读取设置失败，请稍后重试。"));
        }

        const nextSettings = parseUserLLMSettings(data);

        if (!nextSettings) {
          throw new Error("后端设置响应格式无效，请联系管理员。");
        }

        const presets = providersResponse.ok
          ? parseProviderPresets(providersData)
          : null;

        if (!isCancelled) {
          const nextSettingsWithCredentialState = applyProviderCredentials(
            nextSettings,
            presets?.find((item) => item.value === nextSettings.provider)
          );
          setActiveSettings(nextSettingsWithCredentialState);
          setSettings(nextSettingsWithCredentialState);

          if (presets) {
            setProviderPresets(presets);
          }
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
      invalidateProviderModelRequest();
    };
  }, []);

  function updateCredentialMode(credentialMode: CredentialMode) {
    setSettings((current) => ({ ...current, credentialMode }));
    setApiKey("");
    setNotice("");
  }

  function updateProvider(providerValue: string) {
    const nextProvider = providerPresets.find(
      (preset) => preset.value === providerValue
    );

    setSettings((current) => ({
      ...current,
      provider: providerValue,
      model: "",
      baseUrl: nextProvider?.baseUrl || "",
      hasApiKey: nextProvider?.hasApiKey ?? false,
      apiKeyHint: nextProvider?.apiKeyHint ?? null,
    }));
    setApiKey("");
    setShowApiKey(false);
    setModelCandidates([]);
    setIsCustomModel(false);

    invalidateProviderModelRequest();

    if (nextProvider?.hasApiKey) {
      setNotice("正在获取该厂商的模型列表...");
      void loadSavedProviderModels(nextProvider, activeSettings);
    } else {
      setNotice("该厂商尚未保存 API Key，请先输入 API Key。");
    }
  }

  function getPayload(requireModel: boolean) {
    if (requireModel && isUserKeyMode && !settings.model.trim()) {
      throw new Error("请输入模型名称。");
    }

    if (isUserKeyMode && requiresBaseUrl && !settings.baseUrl.trim()) {
      throw new Error("自定义兼容服务需要填写 API 地址。");
    }

    if (isUserKeyMode && !hasSavedApiKey && !apiKey.trim()) {
      throw new Error("请输入 API Key 后再继续。");
    }

    if (
      settings.temperature < 0 ||
      settings.temperature > 2 ||
      settings.maxTokens < 1 ||
      settings.maxTokens > 100000 ||
      settings.timeoutSeconds <= 0 ||
      settings.timeoutSeconds > 600 ||
      settings.maxRetries < 0 ||
      settings.maxRetries > 10
    ) {
      throw new Error("请检查生成参数的取值范围。");
    }

    return toUserLLMSettingsPayload(settings, apiKey, requiresBaseUrl);
  }

  async function handleTest() {
    setTestState("loading");
    setNotice("");

    let authorization = "";

    try {
      invalidateProviderModelRequest();
      const payload = getPayload(false);
      const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

      if (!authState) {
        redirectToLogin();
        return;
      }

      authorization = buildAuthorizationHeader(authState);

      const response = await fetch("/api/settings", {
        method: "POST",
        headers: {
          Authorization: authorization,
          ...(isUserKeyMode ? { "Content-Type": "application/json" } : {}),
        },
        ...(isUserKeyMode ? { body: JSON.stringify(payload) } : {}),
      });
      const data = await getResponseData(response);

      if (response.status === 401) {
        redirectToLogin();
        return;
      }

      const testResult = parseSettingsTestResult(data);

      if (!response.ok || !isSuccessfulResponse(data) || !testResult) {
        throw new Error(getSettingsMessage(data, "连接测试失败，请检查配置。"));
      }

      setModelCandidates(testResult.models);
      setIsCustomModel(
        Boolean(settings.model.trim()) &&
          testResult.models.length > 0 &&
          !testResult.models.includes(settings.model)
      );
      setTestState("success");
      setNotice(
        testResult.modelListAvailable && !settings.model.trim()
          ? `已获取 ${testResult.models.length} 个模型，请选择后再测试连接。`
          : testResult.message
      );
    } catch (error) {
      setTestState("error");
      setNotice(
        isUserKeyMode
          ? "连接测试失败，但 API Key 已安全保存，可修改模型或地址后重试。"
          : error instanceof Error
            ? error.message
            : "连接测试失败，请检查配置。"
      );
    } finally {
      setApiKey("");
      setShowApiKey(false);

      if (authorization) {
        await refreshSettingsAndProviders(authorization);
      }
    }
  }

  function handleModelSelection(model: string) {
    if (model === CUSTOM_MODEL_VALUE) {
      setIsCustomModel(true);
      return;
    }

    setIsCustomModel(false);
    setSettings((current) => ({ ...current, model }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaveState("loading");
    setNotice("");

    try {
      const payload = getPayload(true);
      const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

      if (!authState) {
        redirectToLogin();
        return;
      }

      const authorization = buildAuthorizationHeader(authState);
      const response = await fetch("/api/settings", {
        method: "PATCH",
        headers: {
          Authorization: authorization,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      const data = await getResponseData(response);

      if (response.status === 401) {
        redirectToLogin();
        return;
      }

      if (!response.ok || !isSuccessfulResponse(data)) {
        throw new Error(getSettingsMessage(data, "保存设置失败，请稍后重试。"));
      }

      setSaveState("success");
      setNotice(getSettingsMessage(data, "设置已保存。"));
      await refreshSettingsAndProviders(authorization);
    } catch (error) {
      setSaveState("error");
      setNotice(error instanceof Error ? error.message : "保存设置失败，请稍后重试。");
    } finally {
      setApiKey("");
      setShowApiKey(false);
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

          {isUserKeyMode && <section className="grid gap-5 md:grid-cols-2" aria-label="模型参数">
            <label className="font-utility text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--ink-muted)]">厂商
              <select value={settings.provider} onChange={(event) => updateProvider(event.target.value)} className="research-focus mt-2 w-full border border-[var(--line)] bg-white px-3 py-3 text-sm normal-case tracking-normal text-[var(--foreground)]">
                {providerPresets.map((item) => <option key={item.value} value={item.value} disabled={!item.enabled}>{item.label}{item.enabled ? "" : "（暂不可用）"}</option>)}
              </select>
            </label>
            <label className="font-utility text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--ink-muted)]">模型名
              {modelCandidates.length > 0 ? (
                <>
                  <select value={isCustomModel ? CUSTOM_MODEL_VALUE : settings.model} onChange={(event) => handleModelSelection(event.target.value)} className="research-focus mt-2 w-full border border-[var(--line)] bg-white px-3 py-3 text-sm normal-case tracking-normal text-[var(--foreground)]">
                    <option value="" disabled>请选择模型</option>
                    {modelCandidates.map((model) => <option key={model} value={model}>{model}</option>)}
                    <option value={CUSTOM_MODEL_VALUE}>手动输入模型名</option>
                  </select>
                  {isCustomModel && <input value={settings.model} onChange={(event) => setSettings((current) => ({ ...current, model: event.target.value }))} placeholder="输入模型名称" className="research-focus mt-3 w-full border border-[var(--line)] bg-white px-3 py-3 text-sm normal-case tracking-normal text-[var(--foreground)]" />}
                  <span className="mt-2 block text-xs normal-case tracking-normal text-[var(--research)]">已获取 {modelCandidates.length} 个可选模型，可重新展开选择。</span>
                </>
              ) : (
                <input value={settings.model} onChange={(event) => setSettings((current) => ({ ...current, model: event.target.value }))} placeholder={modelLoadState === "loading" ? "正在获取模型列表..." : "先获取模型列表，或直接输入模型名称"} className="research-focus mt-2 w-full border border-[var(--line)] bg-white px-3 py-3 text-sm normal-case tracking-normal text-[var(--foreground)]" />
              )}
              {modelLoadState === "loading" && <span className="mt-2 block text-xs normal-case tracking-normal text-[var(--ink-muted)]">正在获取模型列表，请稍候。</span>}
            </label>
          </section>}

          {isUserKeyMode && requiresBaseUrl && <label className="font-utility block text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--ink-muted)]">API 地址
            <input type="url" value={settings.baseUrl} onChange={(event) => setSettings((current) => ({ ...current, baseUrl: event.target.value }))} placeholder="https://api.example.com/v1" className="research-focus mt-2 w-full border border-[var(--line)] bg-white px-3 py-3 text-sm normal-case tracking-normal text-[var(--foreground)]" />
          </label>}

          {isUserKeyMode && <section className="border border-[var(--line)] bg-[var(--paper-muted)] p-5" aria-labelledby="api-key-title">
            <div className="flex items-baseline justify-between gap-4"><p id="api-key-title" className="font-utility text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--ink-muted)]">API Key</p>{hasSavedApiKey && <span className="text-xs font-semibold text-[var(--research)]">已保存 · {apiKeyHint ?? "已保存"}</span>}</div>
            <div className="mt-3 flex border border-[var(--line)] bg-white focus-within:border-[var(--research)] focus-within:ring-3 focus-within:ring-[var(--research)]/15">
              <input type={showApiKey ? "text" : "password"} value={apiKey} onChange={(event) => setApiKey(event.target.value)} autoComplete="off" placeholder={hasSavedApiKey ? "已保存；填写可替换现有 Key" : "请输入 API Key"} className="min-w-0 flex-1 bg-transparent px-3 py-3 text-sm text-[var(--foreground)] outline-none" />
              <button type="button" onClick={() => setShowApiKey((current) => !current)} disabled={!apiKey} title={apiKey ? undefined : "已保存的 Key 不可查看"} className="border-l border-[var(--line)] px-4 text-xs font-semibold text-[var(--ink-muted)] hover:bg-[var(--paper-muted)] disabled:cursor-not-allowed disabled:text-[var(--line)]">{apiKey ? (showApiKey ? "隐藏" : "显示") : "不可查看"}</button>
            </div>
            <p className="mt-2 text-xs leading-5 text-[var(--ink-muted)]">密钥只会在保存或测试时发送到后端，页面不会回显或存入浏览器。</p>
          </section>}

          <section className="border-t border-[var(--line)] pt-7" aria-labelledby="generation-title">
            <div className="flex items-baseline justify-between gap-4"><p id="generation-title" className="font-utility text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--ink-muted)]">生成控制</p><span className="text-xs text-[var(--ink-muted)]">平台模式仅调整此区域</span></div>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <label className="font-utility text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--ink-muted)]">Temperature
                <input type="number" min="0" max="2" step="0.1" value={settings.temperature} onChange={(event) => setSettings((current) => ({ ...current, temperature: Number(event.target.value) }))} className="research-focus mt-2 w-full border border-[var(--line)] bg-white px-3 py-3 text-sm normal-case tracking-normal text-[var(--foreground)]" />
              </label>
              <label className="font-utility text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--ink-muted)]">最大输出 Token
                <input type="number" min="1" max="100000" step="1" value={settings.maxTokens} onChange={(event) => setSettings((current) => ({ ...current, maxTokens: Number(event.target.value) }))} className="research-focus mt-2 w-full border border-[var(--line)] bg-white px-3 py-3 text-sm normal-case tracking-normal text-[var(--foreground)]" />
              </label>
              <label className="font-utility text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--ink-muted)]">超时（秒）
                <input type="number" min="1" max="600" step="1" value={settings.timeoutSeconds} onChange={(event) => setSettings((current) => ({ ...current, timeoutSeconds: Number(event.target.value) }))} className="research-focus mt-2 w-full border border-[var(--line)] bg-white px-3 py-3 text-sm normal-case tracking-normal text-[var(--foreground)]" />
              </label>
              <label className="font-utility text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--ink-muted)]">最大重试次数
                <input type="number" min="0" max="10" step="1" value={settings.maxRetries} onChange={(event) => setSettings((current) => ({ ...current, maxRetries: Number(event.target.value) }))} className="research-focus mt-2 w-full border border-[var(--line)] bg-white px-3 py-3 text-sm normal-case tracking-normal text-[var(--foreground)]" />
              </label>
            </div>
          </section>

          <div className="border-t border-[var(--line)] pt-6">
            <p role="status" className={`min-h-5 text-sm ${saveState === "error" || testState === "error" ? "text-[#9b3c29]" : "text-[var(--ink-muted)]"}`}>{notice || "保存后，工作台的下一次对话会使用当前账号的模型设置。"}</p>
            <div className="mt-4 flex flex-wrap gap-3">
              <button type="button" onClick={() => void handleTest()} disabled={testState === "loading" || saveState === "loading"} className="border border-[var(--research)] px-5 py-3 text-sm font-semibold text-[var(--research)] transition hover:bg-[var(--paper-muted)] disabled:border-[var(--line)] disabled:text-[var(--ink-muted)]">{testState === "loading" ? "测试中..." : isUserKeyMode && !settings.model.trim() ? "获取模型列表" : "测试连接"}</button>
              <button type="submit" disabled={saveState === "loading" || testState === "loading"} className="bg-[var(--research)] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[var(--research-dark)] disabled:bg-[var(--line)]">{saveState === "loading" ? "保存中..." : "保存设置"}</button>
            </div>
          </div>
        </div>
      </form>
    </main>
  );
}
