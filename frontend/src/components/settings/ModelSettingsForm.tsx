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
  DEFAULT_USER_EMBEDDING_SETTINGS,
  DEFAULT_USER_LLM_SETTINGS,
  DEFAULT_USER_RERANK_SETTINGS,
  FALLBACK_EMBEDDING_PROVIDER_PRESETS,
  FALLBACK_PROVIDER_PRESETS,
  FALLBACK_RERANK_PROVIDER_PRESETS,
  getSettingsMessage,
  isSuccessfulResponse,
  parseEmbeddingProviderPresets,
  parseEmbeddingSettingsTestResult,
  parseSettingsTestResult,
  parseProviderModels,
  parseRerankProviderPresets,
  parseRerankSettingsTestResult,
  parseUserRerankSettings,
  parseUserEmbeddingSettings,
  parseUserLLMSettings,
  parseProviderPresets,
  toUserEmbeddingSettingsPayload,
  toUserLLMSettingsPayload,
  toUserLLMModelDiscoveryPayload,
  toUserRerankSettingsPayload,
  type EmbeddingProviderPreset,
  type ModelProviderPreset,
  type RerankProviderPreset,
  type UserEmbeddingSettings,
  type UserLLMSettings,
  type UserRerankSettings,
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

function applyEmbeddingProviderCredentials(
  settings: UserEmbeddingSettings,
  provider: EmbeddingProviderPreset | undefined
) {
  if (!provider) {
    return settings;
  }

  return {
    ...settings,
    model: settings.model || provider.defaultModel,
    baseUrl: settings.baseUrl || provider.baseUrl,
    hasApiKey: provider.hasApiKey,
    apiKeyHint: provider.apiKeyHint,
  };
}

function applyRerankProviderCredentials(
  settings: UserRerankSettings,
  provider: RerankProviderPreset | undefined
) {
  if (!provider) {
    return settings;
  }

  return {
    ...settings,
    model: settings.model || provider.defaultModel,
    baseUrl: settings.baseUrl || provider.baseUrl,
    hasApiKey: provider.hasApiKey,
    apiKeyHint: provider.apiKeyHint,
    requiresApiKey: provider.requiresApiKey,
  };
}

export function ModelSettingsForm() {
  const [username, setUsername] = useState("");
  const [activeSettings, setActiveSettings] =
    useState<UserLLMSettings | null>(null);
  const [settings, setSettings] = useState<UserLLMSettings>(
    DEFAULT_USER_LLM_SETTINGS
  );
  const [activeEmbeddingSettings, setActiveEmbeddingSettings] =
    useState<UserEmbeddingSettings | null>(null);
  const [embeddingSettings, setEmbeddingSettings] =
    useState<UserEmbeddingSettings>(DEFAULT_USER_EMBEDDING_SETTINGS);
  const [activeRerankSettings, setActiveRerankSettings] =
    useState<UserRerankSettings | null>(null);
  const [rerankSettings, setRerankSettings] =
    useState<UserRerankSettings>(DEFAULT_USER_RERANK_SETTINGS);
  const [apiKey, setApiKey] = useState("");
  const [embeddingApiKey, setEmbeddingApiKey] = useState("");
  const [rerankApiKey, setRerankApiKey] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [showEmbeddingApiKey, setShowEmbeddingApiKey] = useState(false);
  const [showRerankApiKey, setShowRerankApiKey] = useState(false);
  const [modelCandidates, setModelCandidates] = useState<string[]>([]);
  const [isCustomModel, setIsCustomModel] = useState(false);
  const [providerPresets, setProviderPresets] = useState<ModelProviderPreset[]>(
    FALLBACK_PROVIDER_PRESETS
  );
  const [embeddingProviderPresets, setEmbeddingProviderPresets] = useState<
    EmbeddingProviderPreset[]
  >(FALLBACK_EMBEDDING_PROVIDER_PRESETS);
  const [rerankProviderPresets, setRerankProviderPresets] = useState<
    RerankProviderPreset[]
  >(FALLBACK_RERANK_PROVIDER_PRESETS);
  const [isLoading, setIsLoading] = useState(true);
  const [saveState, setSaveState] = useState<RequestState>("idle");
  const [testState, setTestState] = useState<RequestState>("idle");
  const [embeddingSaveState, setEmbeddingSaveState] =
    useState<RequestState>("idle");
  const [embeddingTestState, setEmbeddingTestState] =
    useState<RequestState>("idle");
  const [rerankSaveState, setRerankSaveState] =
    useState<RequestState>("idle");
  const [rerankTestState, setRerankTestState] =
    useState<RequestState>("idle");
  const [modelLoadState, setModelLoadState] = useState<RequestState>("idle");
  const [notice, setNotice] = useState("");
  const modelRequestIdRef = useRef(0);
  const modelRequestAbortRef = useRef<AbortController | null>(null);

  const provider = useMemo(
    () => providerPresets.find((item) => item.value === settings.provider),
    [providerPresets, settings.provider]
  );
  const embeddingProvider = useMemo(
    () =>
      embeddingProviderPresets.find(
        (item) => item.value === embeddingSettings.provider
      ),
    [embeddingProviderPresets, embeddingSettings.provider]
  );
  const rerankProvider = useMemo(
    () =>
      rerankProviderPresets.find(
        (item) => item.value === rerankSettings.provider
      ),
    [rerankProviderPresets, rerankSettings.provider]
  );
  const requiresBaseUrl = provider?.requiresBaseUrl === true;
  const hasSavedApiKey = provider?.hasApiKey ?? settings.hasApiKey;
  const apiKeyHint = provider?.apiKeyHint ?? settings.apiKeyHint;
  const embeddingRequiresBaseUrl =
    embeddingProvider?.requiresBaseUrl === true;
  const hasSavedEmbeddingApiKey =
    embeddingProvider?.hasApiKey ?? embeddingSettings.hasApiKey;
  const embeddingApiKeyHint =
    embeddingProvider?.apiKeyHint ?? embeddingSettings.apiKeyHint;
  const rerankRequiresBaseUrl = rerankProvider?.requiresBaseUrl === true;
  const rerankRequiresApiKey =
    rerankProvider?.requiresApiKey ?? rerankSettings.requiresApiKey;
  const hasSavedRerankApiKey =
    !rerankRequiresApiKey ||
    (rerankProvider?.hasApiKey ?? rerankSettings.hasApiKey);
  const rerankApiKeyHint =
    rerankProvider?.apiKeyHint ?? rerankSettings.apiKeyHint;

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
      const [
        response,
        providersResponse,
        embeddingResponse,
        embeddingProvidersResponse,
        rerankResponse,
        rerankProvidersResponse,
      ] = await Promise.all([
        fetch("/api/settings", {
          headers: { Authorization: authorization },
          cache: "no-store",
        }),
        fetch("/api/settings/providers", {
          headers: { Authorization: authorization },
          cache: "no-store",
        }),
        fetch("/api/settings/embedding", {
          headers: { Authorization: authorization },
          cache: "no-store",
        }),
        fetch("/api/settings/embedding-providers", {
          headers: { Authorization: authorization },
          cache: "no-store",
        }),
        fetch("/api/settings/rerank", {
          headers: { Authorization: authorization },
          cache: "no-store",
        }),
        fetch("/api/settings/rerank-providers", {
          headers: { Authorization: authorization },
          cache: "no-store",
        }),
      ]);

      if (
        response.status === 401 ||
        providersResponse.status === 401 ||
        embeddingResponse.status === 401 ||
        embeddingProvidersResponse.status === 401 ||
        rerankResponse.status === 401 ||
        rerankProvidersResponse.status === 401
      ) {
        redirectToLogin();
        return;
      }

      const [
        data,
        providersData,
        embeddingData,
        embeddingProvidersData,
        rerankData,
        rerankProvidersData,
      ] = await Promise.all([
        getResponseData(response),
        getResponseData(providersResponse),
        getResponseData(embeddingResponse),
        getResponseData(embeddingProvidersResponse),
        getResponseData(rerankResponse),
        getResponseData(rerankProvidersResponse),
      ]);
      const nextSettings = response.ok ? parseUserLLMSettings(data) : null;
      const presets = providersResponse.ok
        ? parseProviderPresets(providersData)
        : null;
      const nextEmbeddingSettings = embeddingResponse.ok
        ? parseUserEmbeddingSettings(embeddingData)
        : null;
      const embeddingPresets = embeddingProvidersResponse.ok
        ? parseEmbeddingProviderPresets(embeddingProvidersData)
        : null;
      const nextRerankSettings = rerankResponse.ok
        ? parseUserRerankSettings(rerankData)
        : null;
      const rerankPresets = rerankProvidersResponse.ok
        ? parseRerankProviderPresets(rerankProvidersData)
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
      if (nextEmbeddingSettings) {
        const nextEmbeddingSettingsWithCredentialState =
          applyEmbeddingProviderCredentials(
            nextEmbeddingSettings,
            embeddingPresets?.find(
              (item) => item.value === nextEmbeddingSettings.provider
            )
          );
        setActiveEmbeddingSettings(nextEmbeddingSettingsWithCredentialState);
        setEmbeddingSettings(nextEmbeddingSettingsWithCredentialState);
      }
      if (embeddingPresets) {
        setEmbeddingProviderPresets(embeddingPresets);
      }
      if (nextRerankSettings) {
        const nextRerankSettingsWithCredentialState =
          applyRerankProviderCredentials(
            nextRerankSettings,
            rerankPresets?.find(
              (item) => item.value === nextRerankSettings.provider
            )
          );
        setActiveRerankSettings(nextRerankSettingsWithCredentialState);
        setRerankSettings(nextRerankSettingsWithCredentialState);
      }
      if (rerankPresets) {
        setRerankProviderPresets(rerankPresets);
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
        const [
          response,
          providersResponse,
          embeddingResponse,
          embeddingProvidersResponse,
          rerankResponse,
          rerankProvidersResponse,
        ] = await Promise.all([
          fetch("/api/settings", {
            headers: { Authorization: authorization },
            cache: "no-store",
          }),
          fetch("/api/settings/providers", {
            headers: { Authorization: authorization },
            cache: "no-store",
          }),
          fetch("/api/settings/embedding", {
            headers: { Authorization: authorization },
            cache: "no-store",
          }),
          fetch("/api/settings/embedding-providers", {
            headers: { Authorization: authorization },
            cache: "no-store",
          }),
          fetch("/api/settings/rerank", {
            headers: { Authorization: authorization },
            cache: "no-store",
          }),
          fetch("/api/settings/rerank-providers", {
            headers: { Authorization: authorization },
            cache: "no-store",
          }),
        ]);
        const [
          data,
          providersData,
          embeddingData,
          embeddingProvidersData,
          rerankData,
          rerankProvidersData,
        ] = await Promise.all([
          getResponseData(response),
          getResponseData(providersResponse),
          getResponseData(embeddingResponse),
          getResponseData(embeddingProvidersResponse),
          getResponseData(rerankResponse),
          getResponseData(rerankProvidersResponse),
        ]);

        if (
          response.status === 401 ||
          providersResponse.status === 401 ||
          embeddingResponse.status === 401 ||
          embeddingProvidersResponse.status === 401 ||
          rerankResponse.status === 401 ||
          rerankProvidersResponse.status === 401
        ) {
          redirectToLogin();
          return;
        }

        if (!response.ok) {
          throw new Error(getSettingsMessage(data, "读取设置失败，请稍后重试。"));
        }

        const nextSettings = parseUserLLMSettings(data);
        const nextEmbeddingSettings = embeddingResponse.ok
          ? parseUserEmbeddingSettings(embeddingData)
          : null;
        const nextRerankSettings = rerankResponse.ok
          ? parseUserRerankSettings(rerankData)
          : null;

        if (!nextSettings || !nextEmbeddingSettings || !nextRerankSettings) {
          throw new Error("后端设置响应格式无效，请联系管理员。");
        }

        const presets = providersResponse.ok
          ? parseProviderPresets(providersData)
          : null;
        const embeddingPresets = embeddingProvidersResponse.ok
          ? parseEmbeddingProviderPresets(embeddingProvidersData)
          : null;
        const rerankPresets = rerankProvidersResponse.ok
          ? parseRerankProviderPresets(rerankProvidersData)
          : null;

        if (!isCancelled) {
          const nextSettingsWithCredentialState = applyProviderCredentials(
            nextSettings,
            presets?.find((item) => item.value === nextSettings.provider)
          );
          setActiveSettings(nextSettingsWithCredentialState);
          setSettings(nextSettingsWithCredentialState);
          const nextEmbeddingSettingsWithCredentialState =
            applyEmbeddingProviderCredentials(
              nextEmbeddingSettings,
              embeddingPresets?.find(
                (item) => item.value === nextEmbeddingSettings.provider
              )
            );
          setActiveEmbeddingSettings(nextEmbeddingSettingsWithCredentialState);
          setEmbeddingSettings(nextEmbeddingSettingsWithCredentialState);
          const nextRerankSettingsWithCredentialState =
            applyRerankProviderCredentials(
              nextRerankSettings,
              rerankPresets?.find(
                (item) => item.value === nextRerankSettings.provider
              )
            );
          setActiveRerankSettings(nextRerankSettingsWithCredentialState);
          setRerankSettings(nextRerankSettingsWithCredentialState);

          if (presets) {
            setProviderPresets(presets);
          }
          if (embeddingPresets) {
            setEmbeddingProviderPresets(embeddingPresets);
          }
          if (rerankPresets) {
            setRerankProviderPresets(rerankPresets);
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

  function updateEmbeddingProvider(providerValue: string) {
    const nextProvider = embeddingProviderPresets.find(
      (preset) => preset.value === providerValue
    );

    setEmbeddingSettings((current) => ({
      ...current,
      provider: providerValue,
      model: nextProvider?.defaultModel || "",
      baseUrl: nextProvider?.baseUrl || "",
      hasApiKey: nextProvider?.hasApiKey ?? false,
      apiKeyHint: nextProvider?.apiKeyHint ?? null,
      dimensions: null,
    }));
    setEmbeddingApiKey("");
    setShowEmbeddingApiKey(false);
    setNotice(
      nextProvider?.hasApiKey
        ? "该向量模型厂商已保存 API Key。"
        : "该向量模型厂商尚未保存 API Key，请先输入 API Key。"
    );
  }

  function updateRerankProvider(providerValue: string) {
    const nextProvider = rerankProviderPresets.find(
      (preset) => preset.value === providerValue
    );

    setRerankSettings((current) => ({
      ...current,
      provider: providerValue,
      model: nextProvider?.defaultModel || "",
      baseUrl: nextProvider?.baseUrl || "",
      hasApiKey: nextProvider?.hasApiKey ?? false,
      apiKeyHint: nextProvider?.apiKeyHint ?? null,
      requiresApiKey: nextProvider?.requiresApiKey ?? true,
      instruct: "",
    }));
    setRerankApiKey("");
    setShowRerankApiKey(false);
    setNotice(
      nextProvider?.requiresApiKey === false
        ? "本地 Rerank 不需要 API Key。"
        : nextProvider?.hasApiKey
          ? "该 Rerank 厂商已保存 API Key。"
          : "该 Rerank 厂商尚未保存 API Key，请先输入 API Key。"
    );
  }

  function getPayload(requireModel: boolean) {
    if (requireModel && !settings.model.trim()) {
      throw new Error("请输入模型名称。");
    }

    if (requiresBaseUrl && !settings.baseUrl.trim()) {
      throw new Error("自定义兼容服务需要填写 API 地址。");
    }

    if (!hasSavedApiKey && !apiKey.trim()) {
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

  function getEmbeddingPayload() {
    if (!embeddingSettings.model.trim()) {
      throw new Error("请输入向量模型名称。");
    }

    if (embeddingRequiresBaseUrl && !embeddingSettings.baseUrl.trim()) {
      throw new Error("向量模型 API 地址不能为空。");
    }

    if (!hasSavedEmbeddingApiKey && !embeddingApiKey.trim()) {
      throw new Error("请输入向量模型 API Key 后再继续。");
    }

    if (
      embeddingSettings.timeoutSeconds <= 0 ||
      embeddingSettings.timeoutSeconds > 600 ||
      embeddingSettings.maxRetries < 0 ||
      embeddingSettings.maxRetries > 10
    ) {
      throw new Error("请检查向量模型参数的取值范围。");
    }

    return toUserEmbeddingSettingsPayload(
      embeddingSettings,
      embeddingApiKey,
      embeddingRequiresBaseUrl
    );
  }

  function getRerankPayload() {
    if (!rerankSettings.model.trim()) {
      throw new Error("请输入 Rerank 模型名称。");
    }

    if (rerankRequiresBaseUrl && !rerankSettings.baseUrl.trim()) {
      throw new Error("Rerank API 地址不能为空。");
    }

    if (rerankRequiresApiKey && !hasSavedRerankApiKey && !rerankApiKey.trim()) {
      throw new Error("请输入 Rerank API Key 后再继续。");
    }

    if (
      rerankSettings.timeoutSeconds <= 0 ||
      rerankSettings.timeoutSeconds > 600 ||
      rerankSettings.maxRetries < 0 ||
      rerankSettings.maxRetries > 10
    ) {
      throw new Error("请检查 Rerank 模型参数的取值范围。");
    }

    return toUserRerankSettingsPayload(
      rerankSettings,
      rerankApiKey,
      rerankRequiresBaseUrl,
      rerankRequiresApiKey
    );
  }

  async function requestChatModelTest(discoverModelsOnly: boolean) {
    setTestState("loading");
    setNotice("");

    let authorization = "";

    try {
      invalidateProviderModelRequest();
      if (discoverModelsOnly) {
        // 复用保存/测试校验，但模型发现请求本身必须移除旧模型名。
        getPayload(false);
      }
      const payload = discoverModelsOnly
        ? toUserLLMModelDiscoveryPayload(
            settings,
            apiKey,
            requiresBaseUrl
          )
        : getPayload(true);

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
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
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
        !discoverModelsOnly &&
          Boolean(settings.model.trim()) &&
          testResult.models.length > 0 &&
          !testResult.models.includes(settings.model)
      );
      if (discoverModelsOnly) {
        setSettings((current) => ({ ...current, model: "" }));
      }
      setTestState("success");
      setNotice(
        discoverModelsOnly && testResult.modelListAvailable
          ? `已获取 ${testResult.models.length} 个模型，请选择后再测试连接。`
          : testResult.message
      );
    } catch (error) {
      setTestState("error");
      setNotice(
        error instanceof Error ? error.message : "连接测试失败，请检查配置。"
      );
    } finally {
      setApiKey("");
      setShowApiKey(false);

      if (authorization) {
        await refreshSettingsAndProviders(authorization);
      }
    }
  }

  async function handleModelDiscovery() {
    await requestChatModelTest(true);
  }

  async function handleTest() {
    await requestChatModelTest(false);
  }

  async function handleEmbeddingTest() {
    setEmbeddingTestState("loading");
    setNotice("");

    try {
      const payload = getEmbeddingPayload();
      const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

      if (!authState) {
        redirectToLogin();
        return;
      }

      const authorization = buildAuthorizationHeader(authState);
      const response = await fetch("/api/settings/embedding", {
        method: "POST",
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

      const testResult = parseEmbeddingSettingsTestResult(data);

      if (!response.ok || !isSuccessfulResponse(data) || !testResult) {
        throw new Error(getSettingsMessage(data, "向量模型连接测试失败，请检查配置。"));
      }

      setEmbeddingTestState("success");
      setNotice(
        testResult.dimensions
          ? `${testResult.message}，返回维度 ${testResult.dimensions}。`
          : testResult.message
      );
    } catch (error) {
      setEmbeddingTestState("error");
      setNotice(
        error instanceof Error ? error.message : "向量模型连接测试失败，请检查配置。"
      );
    } finally {
      setShowEmbeddingApiKey(false);
    }
  }

  async function handleEmbeddingSubmit() {
    setEmbeddingSaveState("loading");
    setNotice("");

    try {
      const payload = getEmbeddingPayload();
      const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

      if (!authState) {
        redirectToLogin();
        return;
      }

      const authorization = buildAuthorizationHeader(authState);
      const response = await fetch("/api/settings/embedding", {
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
        throw new Error(getSettingsMessage(data, "保存向量模型设置失败，请稍后重试。"));
      }

      setEmbeddingSaveState("success");
      setNotice(
        getSettingsMessage(
          data,
          "向量模型设置已保存；如果更换了模型或维度，请重新向量化已有文件。"
        )
      );
      await refreshSettingsAndProviders(authorization);
    } catch (error) {
      setEmbeddingSaveState("error");
      setNotice(
        error instanceof Error ? error.message : "保存向量模型设置失败，请稍后重试。"
      );
    } finally {
      setEmbeddingApiKey("");
      setShowEmbeddingApiKey(false);
    }
  }

  async function handleRerankTest() {
    setRerankTestState("loading");
    setNotice("");

    try {
      const payload = getRerankPayload();
      const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

      if (!authState) {
        redirectToLogin();
        return;
      }

      const authorization = buildAuthorizationHeader(authState);
      const response = await fetch("/api/settings/rerank", {
        method: "POST",
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

      const testResult = parseRerankSettingsTestResult(data);

      if (!response.ok || !isSuccessfulResponse(data) || !testResult) {
        throw new Error(getSettingsMessage(data, "Rerank 模型连接测试失败，请检查配置。"));
      }

      setRerankTestState("success");
      setNotice(
        testResult.topScore !== null
          ? `${testResult.message}，测试分数 ${testResult.topScore.toFixed(4)}。`
          : testResult.message
      );
    } catch (error) {
      setRerankTestState("error");
      setNotice(
        error instanceof Error ? error.message : "Rerank 模型连接测试失败，请检查配置。"
      );
    } finally {
      setShowRerankApiKey(false);
    }
  }

  async function handleRerankSubmit() {
    setRerankSaveState("loading");
    setNotice("");

    try {
      const payload = getRerankPayload();
      const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

      if (!authState) {
        redirectToLogin();
        return;
      }

      const authorization = buildAuthorizationHeader(authState);
      const response = await fetch("/api/settings/rerank", {
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
        throw new Error(getSettingsMessage(data, "保存 Rerank 模型设置失败，请稍后重试。"));
      }

      setRerankSaveState("success");
      setNotice(getSettingsMessage(data, "Rerank 模型设置已保存。"));
      await refreshSettingsAndProviders(authorization);
    } catch (error) {
      setRerankSaveState("error");
      setNotice(
        error instanceof Error ? error.message : "保存 Rerank 模型设置失败，请稍后重试。"
      );
    } finally {
      setRerankApiKey("");
      setShowRerankApiKey(false);
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
              <h1 className="font-display mt-3 text-3xl font-semibold text-[var(--foreground)]">模型设置</h1>
              <p className="mt-2 text-sm text-[var(--ink-muted)]">{username ? `${username} 的设置` : "管理当前账号的聊天模型与向量模型。"}</p>
            </div>
            <Link href="/" className="shrink-0 text-sm font-semibold text-[var(--research)] underline decoration-[var(--index)] decoration-2 underline-offset-4">返回工作台</Link>
          </div>
        </header>

        <div className="space-y-9 px-6 py-8 md:px-10 md:py-10">
          <section className="grid gap-5 md:grid-cols-2" aria-label="聊天模型参数">
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
          </section>

          {requiresBaseUrl && <label className="font-utility block text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--ink-muted)]">API 地址
            <input type="url" value={settings.baseUrl} onChange={(event) => setSettings((current) => ({ ...current, baseUrl: event.target.value }))} placeholder="https://api.example.com/v1" className="research-focus mt-2 w-full border border-[var(--line)] bg-white px-3 py-3 text-sm normal-case tracking-normal text-[var(--foreground)]" />
          </label>}

          <section className="border border-[var(--line)] bg-[var(--paper-muted)] p-5" aria-labelledby="api-key-title">
            <div className="flex items-baseline justify-between gap-4"><p id="api-key-title" className="font-utility text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--ink-muted)]">API Key</p>{hasSavedApiKey && <span className="text-xs font-semibold text-[var(--research)]">已保存 · {apiKeyHint ?? "已保存"}</span>}</div>
            <div className="mt-3 flex border border-[var(--line)] bg-white focus-within:border-[var(--research)] focus-within:ring-3 focus-within:ring-[var(--research)]/15">
              <input type={showApiKey ? "text" : "password"} value={apiKey} onChange={(event) => setApiKey(event.target.value)} autoComplete="off" placeholder={hasSavedApiKey ? "已保存；填写可替换现有 Key" : "请输入 API Key"} className="min-w-0 flex-1 bg-transparent px-3 py-3 text-sm text-[var(--foreground)] outline-none" />
              <button type="button" onClick={() => setShowApiKey((current) => !current)} disabled={!apiKey} title={apiKey ? undefined : "已保存的 Key 不可查看"} className="border-l border-[var(--line)] px-4 text-xs font-semibold text-[var(--ink-muted)] hover:bg-[var(--paper-muted)] disabled:cursor-not-allowed disabled:text-[var(--line)]">{apiKey ? (showApiKey ? "隐藏" : "显示") : "不可查看"}</button>
            </div>
            <p className="mt-2 text-xs leading-5 text-[var(--ink-muted)]">密钥只会在保存或测试时发送到后端，页面不会回显或存入浏览器。</p>
            <button type="button" onClick={() => void handleModelDiscovery()} disabled={testState === "loading" || saveState === "loading" || (!hasSavedApiKey && !apiKey.trim())} className="mt-4 border border-[var(--research)] px-5 py-3 text-sm font-semibold text-[var(--research)] transition hover:bg-white disabled:cursor-not-allowed disabled:border-[var(--line)] disabled:text-[var(--ink-muted)]">{testState === "loading" ? "正在获取模型列表..." : modelCandidates.length > 0 ? "重新获取模型列表" : "获取模型列表"}</button>
          </section>

          <section className="border-t border-[var(--line)] pt-7" aria-labelledby="generation-title">
            <div className="flex items-baseline justify-between gap-4"><p id="generation-title" className="font-utility text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--ink-muted)]">生成控制</p></div>
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

          <section className="border-t border-[var(--line)] pt-7" aria-labelledby="embedding-title">
            <div className="flex items-baseline justify-between gap-4"><p id="embedding-title" className="font-utility text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--ink-muted)]">向量模型</p>{activeEmbeddingSettings?.hasApiKey && <span className="text-xs text-[var(--ink-muted)]">当前已配置</span>}</div>
            <div className="mt-4 grid gap-5 md:grid-cols-2">
              <label className="font-utility text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--ink-muted)]">厂商
                <select value={embeddingSettings.provider} onChange={(event) => updateEmbeddingProvider(event.target.value)} className="research-focus mt-2 w-full border border-[var(--line)] bg-white px-3 py-3 text-sm normal-case tracking-normal text-[var(--foreground)]">
                  {embeddingProviderPresets.map((item) => <option key={item.value} value={item.value} disabled={!item.enabled}>{item.label}{item.enabled ? "" : "（暂不可用）"}</option>)}
                </select>
              </label>
              <label className="font-utility text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--ink-muted)]">模型名
                <input value={embeddingSettings.model} onChange={(event) => setEmbeddingSettings((current) => ({ ...current, model: event.target.value }))} placeholder={embeddingProvider?.defaultModel || "输入向量模型名称"} className="research-focus mt-2 w-full border border-[var(--line)] bg-white px-3 py-3 text-sm normal-case tracking-normal text-[var(--foreground)]" />
              </label>
              {embeddingRequiresBaseUrl && <label className="font-utility text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--ink-muted)]">API 地址
                <input type="url" value={embeddingSettings.baseUrl} onChange={(event) => setEmbeddingSettings((current) => ({ ...current, baseUrl: event.target.value }))} placeholder="https://api.example.com/v1" className="research-focus mt-2 w-full border border-[var(--line)] bg-white px-3 py-3 text-sm normal-case tracking-normal text-[var(--foreground)]" />
              </label>}
              <label className="font-utility text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--ink-muted)]">向量维度
                <input type="number" min="1" max="8192" step="1" value={embeddingSettings.dimensions ?? ""} onChange={(event) => setEmbeddingSettings((current) => ({ ...current, dimensions: event.target.value ? Number(event.target.value) : null }))} placeholder="默认维度" className="research-focus mt-2 w-full border border-[var(--line)] bg-white px-3 py-3 text-sm normal-case tracking-normal text-[var(--foreground)]" />
              </label>
              <label className="font-utility text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--ink-muted)]">超时（秒）
                <input type="number" min="1" max="600" step="1" value={embeddingSettings.timeoutSeconds} onChange={(event) => setEmbeddingSettings((current) => ({ ...current, timeoutSeconds: Number(event.target.value) }))} className="research-focus mt-2 w-full border border-[var(--line)] bg-white px-3 py-3 text-sm normal-case tracking-normal text-[var(--foreground)]" />
              </label>
              <label className="font-utility text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--ink-muted)]">最大重试次数
                <input type="number" min="0" max="10" step="1" value={embeddingSettings.maxRetries} onChange={(event) => setEmbeddingSettings((current) => ({ ...current, maxRetries: Number(event.target.value) }))} className="research-focus mt-2 w-full border border-[var(--line)] bg-white px-3 py-3 text-sm normal-case tracking-normal text-[var(--foreground)]" />
              </label>
            </div>
            <div className="mt-5 border border-[var(--line)] bg-[var(--paper-muted)] p-5" aria-labelledby="embedding-api-key-title">
              <div className="flex items-baseline justify-between gap-4"><p id="embedding-api-key-title" className="font-utility text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--ink-muted)]">向量 API Key</p>{hasSavedEmbeddingApiKey && <span className="text-xs font-semibold text-[var(--research)]">已保存 · {embeddingApiKeyHint ?? "已保存"}</span>}</div>
              <div className="mt-3 flex border border-[var(--line)] bg-white focus-within:border-[var(--research)] focus-within:ring-3 focus-within:ring-[var(--research)]/15">
                <input type={showEmbeddingApiKey ? "text" : "password"} value={embeddingApiKey} onChange={(event) => setEmbeddingApiKey(event.target.value)} autoComplete="off" placeholder={hasSavedEmbeddingApiKey ? "已保存；填写可替换现有 Key" : "请输入向量 API Key"} className="min-w-0 flex-1 bg-transparent px-3 py-3 text-sm text-[var(--foreground)] outline-none" />
                <button type="button" onClick={() => setShowEmbeddingApiKey((current) => !current)} disabled={!embeddingApiKey} title={embeddingApiKey ? undefined : "已保存的 Key 不可查看"} className="border-l border-[var(--line)] px-4 text-xs font-semibold text-[var(--ink-muted)] hover:bg-[var(--paper-muted)] disabled:cursor-not-allowed disabled:text-[var(--line)]">{embeddingApiKey ? (showEmbeddingApiKey ? "隐藏" : "显示") : "不可查看"}</button>
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-3">
              <button type="button" onClick={() => void handleEmbeddingTest()} disabled={embeddingTestState === "loading" || embeddingSaveState === "loading"} className="border border-[var(--research)] px-5 py-3 text-sm font-semibold text-[var(--research)] transition hover:bg-[var(--paper-muted)] disabled:border-[var(--line)] disabled:text-[var(--ink-muted)]">{embeddingTestState === "loading" ? "测试中..." : "测试向量模型"}</button>
              <button type="button" onClick={() => void handleEmbeddingSubmit()} disabled={embeddingSaveState === "loading" || embeddingTestState === "loading"} className="bg-[var(--research)] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[var(--research-dark)] disabled:bg-[var(--line)]">{embeddingSaveState === "loading" ? "保存中..." : "保存向量模型"}</button>
            </div>
          </section>

          <section className="border-t border-[var(--line)] pt-7" aria-labelledby="rerank-title">
            <div className="flex items-baseline justify-between gap-4"><p id="rerank-title" className="font-utility text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--ink-muted)]">Rerank 模型</p>{activeRerankSettings && <span className="text-xs text-[var(--ink-muted)]">当前 {activeRerankSettings.provider}</span>}</div>
            <div className="mt-4 grid gap-5 md:grid-cols-2">
              <label className="font-utility text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--ink-muted)]">厂商
                <select value={rerankSettings.provider} onChange={(event) => updateRerankProvider(event.target.value)} className="research-focus mt-2 w-full border border-[var(--line)] bg-white px-3 py-3 text-sm normal-case tracking-normal text-[var(--foreground)]">
                  {rerankProviderPresets.map((item) => <option key={item.value} value={item.value} disabled={!item.enabled}>{item.label}{item.enabled ? "" : "（暂不可用）"}</option>)}
                </select>
              </label>
              <label className="font-utility text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--ink-muted)]">模型名
                <input value={rerankSettings.model} onChange={(event) => setRerankSettings((current) => ({ ...current, model: event.target.value }))} placeholder={rerankProvider?.defaultModel || "输入 Rerank 模型名称"} className="research-focus mt-2 w-full border border-[var(--line)] bg-white px-3 py-3 text-sm normal-case tracking-normal text-[var(--foreground)]" />
              </label>
              {rerankRequiresBaseUrl && <label className="font-utility text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--ink-muted)]">API 地址
                <input type="url" value={rerankSettings.baseUrl} onChange={(event) => setRerankSettings((current) => ({ ...current, baseUrl: event.target.value }))} placeholder="https://api.example.com/v1" className="research-focus mt-2 w-full border border-[var(--line)] bg-white px-3 py-3 text-sm normal-case tracking-normal text-[var(--foreground)]" />
              </label>}
              <label className="font-utility text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--ink-muted)]">超时（秒）
                <input type="number" min="1" max="600" step="1" value={rerankSettings.timeoutSeconds} onChange={(event) => setRerankSettings((current) => ({ ...current, timeoutSeconds: Number(event.target.value) }))} className="research-focus mt-2 w-full border border-[var(--line)] bg-white px-3 py-3 text-sm normal-case tracking-normal text-[var(--foreground)]" />
              </label>
              <label className="font-utility text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--ink-muted)]">最大重试次数
                <input type="number" min="0" max="10" step="1" value={rerankSettings.maxRetries} onChange={(event) => setRerankSettings((current) => ({ ...current, maxRetries: Number(event.target.value) }))} className="research-focus mt-2 w-full border border-[var(--line)] bg-white px-3 py-3 text-sm normal-case tracking-normal text-[var(--foreground)]" />
              </label>
              <label className="font-utility text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--ink-muted)] md:col-span-2">Instruction
                <input value={rerankSettings.instruct} onChange={(event) => setRerankSettings((current) => ({ ...current, instruct: event.target.value }))} placeholder="可选：传给支持 instruct 的 rerank provider" className="research-focus mt-2 w-full border border-[var(--line)] bg-white px-3 py-3 text-sm normal-case tracking-normal text-[var(--foreground)]" />
              </label>
            </div>
            {rerankRequiresApiKey && <div className="mt-5 border border-[var(--line)] bg-[var(--paper-muted)] p-5" aria-labelledby="rerank-api-key-title">
              <div className="flex items-baseline justify-between gap-4"><p id="rerank-api-key-title" className="font-utility text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--ink-muted)]">Rerank API Key</p>{hasSavedRerankApiKey && <span className="text-xs font-semibold text-[var(--research)]">已保存 · {rerankApiKeyHint ?? "已保存"}</span>}</div>
              <div className="mt-3 flex border border-[var(--line)] bg-white focus-within:border-[var(--research)] focus-within:ring-3 focus-within:ring-[var(--research)]/15">
                <input type={showRerankApiKey ? "text" : "password"} value={rerankApiKey} onChange={(event) => setRerankApiKey(event.target.value)} autoComplete="off" placeholder={hasSavedRerankApiKey ? "已保存；填写可替换现有 Key" : "请输入 Rerank API Key"} className="min-w-0 flex-1 bg-transparent px-3 py-3 text-sm text-[var(--foreground)] outline-none" />
                <button type="button" onClick={() => setShowRerankApiKey((current) => !current)} disabled={!rerankApiKey} title={rerankApiKey ? undefined : "已保存的 Key 不可查看"} className="border-l border-[var(--line)] px-4 text-xs font-semibold text-[var(--ink-muted)] hover:bg-[var(--paper-muted)] disabled:cursor-not-allowed disabled:text-[var(--line)]">{rerankApiKey ? (showRerankApiKey ? "隐藏" : "显示") : "不可查看"}</button>
              </div>
            </div>}
            <div className="mt-4 flex flex-wrap gap-3">
              <button type="button" onClick={() => void handleRerankTest()} disabled={rerankTestState === "loading" || rerankSaveState === "loading"} className="border border-[var(--research)] px-5 py-3 text-sm font-semibold text-[var(--research)] transition hover:bg-[var(--paper-muted)] disabled:border-[var(--line)] disabled:text-[var(--ink-muted)]">{rerankTestState === "loading" ? "测试中..." : "测试 Rerank 模型"}</button>
              <button type="button" onClick={() => void handleRerankSubmit()} disabled={rerankSaveState === "loading" || rerankTestState === "loading"} className="bg-[var(--research)] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[var(--research-dark)] disabled:bg-[var(--line)]">{rerankSaveState === "loading" ? "保存中..." : "保存 Rerank 模型"}</button>
            </div>
          </section>

          <div className="border-t border-[var(--line)] pt-6">
            <p role="status" className={`min-h-5 text-sm ${saveState === "error" || testState === "error" || embeddingSaveState === "error" || embeddingTestState === "error" || rerankSaveState === "error" || rerankTestState === "error" ? "text-[#9b3c29]" : "text-[var(--ink-muted)]"}`}>{notice || "保存后，工作台的下一次对话、向量化和检索精排会使用当前账号的模型设置。"}</p>
            <div className="mt-4 flex flex-wrap gap-3">
              <button type="button" onClick={() => void handleTest()} disabled={testState === "loading" || saveState === "loading" || !settings.model.trim()} className="border border-[var(--research)] px-5 py-3 text-sm font-semibold text-[var(--research)] transition hover:bg-[var(--paper-muted)] disabled:border-[var(--line)] disabled:text-[var(--ink-muted)]">{testState === "loading" ? "测试中..." : "测试聊天模型"}</button>
              <button type="submit" disabled={saveState === "loading" || testState === "loading"} className="bg-[var(--research)] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[var(--research-dark)] disabled:bg-[var(--line)]">{saveState === "loading" ? "保存中..." : "保存聊天模型"}</button>
            </div>
          </div>
        </div>
      </form>
    </main>
  );
}
