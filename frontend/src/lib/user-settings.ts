export type CredentialMode = "platform" | "user";

export type UserLLMSettings = {
  credentialMode: CredentialMode;
  provider: string;
  model: string;
  baseUrl: string;
  hasApiKey: boolean;
  apiKeyHint: string | null;
  temperature: number;
  maxTokens: number;
  timeoutSeconds: number;
  maxRetries: number;
};

export type UserEmbeddingSettings = {
  provider: string;
  model: string;
  baseUrl: string;
  dimensions: number | null;
  hasApiKey: boolean;
  apiKeyHint: string | null;
  timeoutSeconds: number;
  maxRetries: number;
};

export type UserRerankSettings = {
  provider: string;
  model: string;
  baseUrl: string;
  instruct: string;
  hasApiKey: boolean;
  apiKeyHint: string | null;
  requiresApiKey: boolean;
  timeoutSeconds: number;
  maxRetries: number;
};

export type ModelProviderPreset = {
  value: string;
  label: string;
  baseUrl: string;
  requiresBaseUrl: boolean;
  enabled: boolean;
  hasApiKey: boolean;
  apiKeyHint: string | null;
};

export type EmbeddingProviderPreset = {
  value: string;
  label: string;
  baseUrl: string;
  requiresBaseUrl: boolean;
  enabled: boolean;
  defaultModel: string;
  hasApiKey: boolean;
  apiKeyHint: string | null;
};

export type RerankProviderPreset = {
  value: string;
  label: string;
  baseUrl: string;
  requiresBaseUrl: boolean;
  requiresApiKey: boolean;
  enabled: boolean;
  defaultModel: string;
  hasApiKey: boolean;
  apiKeyHint: string | null;
};

export type SettingsTestResult = {
  message: string;
  models: string[];
  modelListAvailable: boolean;
};

export type EmbeddingSettingsTestResult = {
  message: string;
  provider: string;
  model: string;
  dimensions: number | null;
};

export type RerankSettingsTestResult = {
  message: string;
  provider: string;
  model: string;
  topScore: number | null;
};

export const FALLBACK_PROVIDER_PRESETS: ModelProviderPreset[] = [
  { value: "deepseek", label: "DeepSeek", baseUrl: "https://api.deepseek.com/v1", requiresBaseUrl: false, enabled: true, hasApiKey: false, apiKeyHint: null },
  { value: "qwen", label: "通义千问", baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1", requiresBaseUrl: false, enabled: true, hasApiKey: false, apiKeyHint: null },
  { value: "zhipu", label: "智谱", baseUrl: "", requiresBaseUrl: false, enabled: true, hasApiKey: false, apiKeyHint: null },
  { value: "kimi", label: "Kimi", baseUrl: "", requiresBaseUrl: false, enabled: true, hasApiKey: false, apiKeyHint: null },
  { value: "doubao", label: "豆包", baseUrl: "", requiresBaseUrl: false, enabled: true, hasApiKey: false, apiKeyHint: null },
  { value: "minimax", label: "MiniMax", baseUrl: "", requiresBaseUrl: false, enabled: true, hasApiKey: false, apiKeyHint: null },
];

export const DEFAULT_USER_LLM_SETTINGS: UserLLMSettings = {
  credentialMode: "user",
  provider: "deepseek",
  model: "deepseek-chat",
  baseUrl: "",
  hasApiKey: false,
  apiKeyHint: null,
  temperature: 0.2,
  maxTokens: 8000,
  timeoutSeconds: 60,
  maxRetries: 2,
};

export const FALLBACK_EMBEDDING_PROVIDER_PRESETS: EmbeddingProviderPreset[] = [
  { value: "qwen", label: "通义千问向量", baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1", requiresBaseUrl: false, enabled: true, defaultModel: "text-embedding-v4", hasApiKey: false, apiKeyHint: null },
  { value: "zhipuai", label: "智谱 Embedding", baseUrl: "", requiresBaseUrl: false, enabled: true, defaultModel: "embedding-3", hasApiKey: false, apiKeyHint: null },
  { value: "openai", label: "OpenAI Embeddings", baseUrl: "https://api.openai.com/v1", requiresBaseUrl: false, enabled: true, defaultModel: "text-embedding-3-small", hasApiKey: false, apiKeyHint: null },
  { value: "voyage", label: "Voyage AI Embeddings", baseUrl: "https://api.voyageai.com/v1", requiresBaseUrl: false, enabled: true, defaultModel: "voyage-4", hasApiKey: false, apiKeyHint: null },
  { value: "cohere", label: "Cohere Embed", baseUrl: "https://api.cohere.com", requiresBaseUrl: false, enabled: true, defaultModel: "embed-v4.0", hasApiKey: false, apiKeyHint: null },
  { value: "jina", label: "Jina Embeddings", baseUrl: "https://api.jina.ai/v1", requiresBaseUrl: false, enabled: true, defaultModel: "jina-embeddings-v3", hasApiKey: false, apiKeyHint: null },
];

export const DEFAULT_USER_EMBEDDING_SETTINGS: UserEmbeddingSettings = {
  provider: "qwen",
  model: "text-embedding-v4",
  baseUrl: "",
  dimensions: null,
  hasApiKey: false,
  apiKeyHint: null,
  timeoutSeconds: 60,
  maxRetries: 2,
};

export const FALLBACK_RERANK_PROVIDER_PRESETS: RerankProviderPreset[] = [
  { value: "local", label: "本地 BGE Cross-Encoder", baseUrl: "", requiresBaseUrl: false, requiresApiKey: false, enabled: true, defaultModel: "models/rerankers/bge-reranker-base", hasApiKey: true, apiKeyHint: null },
  { value: "qwen", label: "通义千问 Rerank", baseUrl: "", requiresBaseUrl: true, requiresApiKey: true, enabled: true, defaultModel: "qwen3-rerank", hasApiKey: false, apiKeyHint: null },
  { value: "voyage", label: "Voyage AI Rerank", baseUrl: "https://api.voyageai.com/v1", requiresBaseUrl: false, requiresApiKey: true, enabled: true, defaultModel: "rerank-2.5", hasApiKey: false, apiKeyHint: null },
  { value: "cohere", label: "Cohere Rerank", baseUrl: "https://api.cohere.com", requiresBaseUrl: false, requiresApiKey: true, enabled: true, defaultModel: "rerank-v3.5", hasApiKey: false, apiKeyHint: null },
  { value: "jina", label: "Jina Reranker", baseUrl: "https://api.jina.ai/v1", requiresBaseUrl: false, requiresApiKey: true, enabled: true, defaultModel: "jina-reranker-v2-base-multilingual", hasApiKey: false, apiKeyHint: null },
];

export const DEFAULT_USER_RERANK_SETTINGS: UserRerankSettings = {
  provider: "local",
  model: "models/rerankers/bge-reranker-base",
  baseUrl: "",
  instruct: "",
  hasApiKey: true,
  apiKeyHint: null,
  requiresApiKey: false,
  timeoutSeconds: 60,
  maxRetries: 2,
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function readString(value: unknown, fallback = "") {
  return typeof value === "string" ? value : fallback;
}

function readNumber(value: unknown, fallback: number) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function readApiKeyHint(value: unknown) {
  const hint = readString(value).trim();
  return hint || null;
}

function toProviderPreset(value: unknown): ModelProviderPreset | null {
  if (!isRecord(value)) {
    return null;
  }

  const provider = readString(value.value, readString(value.id, readString(value.provider))).trim();

  if (!provider) {
    return null;
  }

  return {
    value: provider,
    label: readString(value.label, readString(value.display_name, readString(value.name, provider))).trim(),
    baseUrl: readString(value.base_url),
    requiresBaseUrl: value.requires_base_url === true,
    enabled: value.enabled !== false,
    hasApiKey: value.has_api_key === true,
    apiKeyHint: readApiKeyHint(value.api_key_hint),
  };
}

function toEmbeddingProviderPreset(value: unknown): EmbeddingProviderPreset | null {
  if (!isRecord(value)) {
    return null;
  }

  const provider = readString(value.value, readString(value.id, readString(value.provider))).trim();

  if (!provider) {
    return null;
  }

  return {
    value: provider,
    label: readString(value.label, readString(value.display_name, readString(value.name, provider))).trim(),
    baseUrl: readString(value.base_url),
    requiresBaseUrl: value.requires_base_url === true,
    enabled: value.enabled !== false,
    defaultModel: readString(value.default_model),
    hasApiKey: value.has_api_key === true,
    apiKeyHint: readApiKeyHint(value.api_key_hint),
  };
}

function toRerankProviderPreset(value: unknown): RerankProviderPreset | null {
  if (!isRecord(value)) {
    return null;
  }

  const provider = readString(value.value, readString(value.id, readString(value.provider))).trim();

  if (!provider) {
    return null;
  }

  return {
    value: provider,
    label: readString(value.label, readString(value.display_name, readString(value.name, provider))).trim(),
    baseUrl: readString(value.base_url),
    requiresBaseUrl: value.requires_base_url === true,
    requiresApiKey: value.requires_api_key === true,
    enabled: value.enabled !== false,
    defaultModel: readString(value.default_model),
    hasApiKey: value.has_api_key === true,
    apiKeyHint: readApiKeyHint(value.api_key_hint),
  };
}

export function parseProviderPresets(value: unknown) {
  if (!isRecord(value)) {
    return null;
  }

  const candidates = Array.isArray(value.providers)
    ? value.providers
    : Array.isArray(value.data)
      ? value.data
      : null;

  if (!candidates) {
    return null;
  }

  const presets = candidates
    .map(toProviderPreset)
    .filter((preset): preset is ModelProviderPreset => preset !== null);

  return presets.length > 0 ? presets : null;
}

export function parseEmbeddingProviderPresets(value: unknown) {
  if (!isRecord(value)) {
    return null;
  }

  const candidates = Array.isArray(value.providers)
    ? value.providers
    : Array.isArray(value.data)
      ? value.data
      : null;

  if (!candidates) {
    return null;
  }

  const presets = candidates
    .map(toEmbeddingProviderPreset)
    .filter((preset): preset is EmbeddingProviderPreset => preset !== null);

  return presets.length > 0 ? presets : null;
}

export function parseRerankProviderPresets(value: unknown) {
  if (!isRecord(value)) {
    return null;
  }

  const candidates = Array.isArray(value.providers)
    ? value.providers
    : Array.isArray(value.data)
      ? value.data
      : null;

  if (!candidates) {
    return null;
  }

  const presets = candidates
    .map(toRerankProviderPreset)
    .filter((preset): preset is RerankProviderPreset => preset !== null);

  return presets.length > 0 ? presets : null;
}

export function parseUserLLMSettings(value: unknown): UserLLMSettings | null {
  if (!isRecord(value)) {
    return null;
  }

  const settings = isRecord(value.settings) ? value.settings : value;
  const credentialMode = settings.credential_mode;

  if (credentialMode !== "platform" && credentialMode !== "user") {
    return null;
  }

  return {
    credentialMode,
    provider: readString(settings.provider, DEFAULT_USER_LLM_SETTINGS.provider),
    model: readString(settings.model, DEFAULT_USER_LLM_SETTINGS.model),
    baseUrl: readString(settings.base_url),
    hasApiKey: settings.has_api_key === true,
    apiKeyHint: readApiKeyHint(settings.api_key_hint),
    temperature: readNumber(settings.temperature, DEFAULT_USER_LLM_SETTINGS.temperature),
    maxTokens: readNumber(settings.max_tokens, DEFAULT_USER_LLM_SETTINGS.maxTokens),
    timeoutSeconds: readNumber(settings.timeout_seconds, DEFAULT_USER_LLM_SETTINGS.timeoutSeconds),
    maxRetries: readNumber(settings.max_retries, DEFAULT_USER_LLM_SETTINGS.maxRetries),
  };
}

export function toUserLLMSettingsPayload(
  settings: UserLLMSettings,
  apiKey: string,
  requiresBaseUrl: boolean
) {
  const trimmedApiKey = apiKey.trim();

  const generationOptions = {
    temperature: settings.temperature,
    max_tokens: settings.maxTokens,
    timeout_seconds: settings.timeoutSeconds,
    max_retries: settings.maxRetries,
  };

  return {
    credential_mode: "user" as const,
    provider: settings.provider.trim(),
    ...(settings.model.trim() ? { model: settings.model.trim() } : {}),
    ...(requiresBaseUrl ? { base_url: settings.baseUrl.trim() } : {}),
    ...(trimmedApiKey ? { api_key: trimmedApiKey } : {}),
    ...generationOptions,
  };
}

export function toUserLLMModelDiscoveryPayload(
  settings: UserLLMSettings,
  apiKey: string,
  requiresBaseUrl: boolean
) {
  // 模型发现不能沿用页面中的旧模型名，否则后端会误执行聊天测试。
  return toUserLLMSettingsPayload(
    { ...settings, model: "" },
    apiKey,
    requiresBaseUrl
  );
}

export function parseUserEmbeddingSettings(value: unknown): UserEmbeddingSettings | null {
  if (!isRecord(value)) {
    return null;
  }

  const settings = isRecord(value.settings) ? value.settings : value;
  return {
    provider: readString(settings.provider, DEFAULT_USER_EMBEDDING_SETTINGS.provider),
    model: readString(settings.model, DEFAULT_USER_EMBEDDING_SETTINGS.model),
    baseUrl: readString(settings.base_url),
    dimensions:
      typeof settings.dimensions === "number" && Number.isFinite(settings.dimensions)
        ? settings.dimensions
        : null,
    hasApiKey: settings.has_api_key === true,
    apiKeyHint: readApiKeyHint(settings.api_key_hint),
    timeoutSeconds: readNumber(settings.timeout_seconds, DEFAULT_USER_EMBEDDING_SETTINGS.timeoutSeconds),
    maxRetries: readNumber(settings.max_retries, DEFAULT_USER_EMBEDDING_SETTINGS.maxRetries),
  };
}

export function toUserEmbeddingSettingsPayload(
  settings: UserEmbeddingSettings,
  apiKey: string,
  requiresBaseUrl: boolean
) {
  const trimmedApiKey = apiKey.trim();

  return {
    provider: settings.provider.trim(),
    model: settings.model.trim(),
    ...(requiresBaseUrl ? { base_url: settings.baseUrl.trim() } : {}),
    dimensions: settings.dimensions,
    ...(trimmedApiKey ? { api_key: trimmedApiKey } : {}),
    timeout_seconds: settings.timeoutSeconds,
    max_retries: settings.maxRetries,
  };
}

export function parseUserRerankSettings(value: unknown): UserRerankSettings | null {
  if (!isRecord(value)) {
    return null;
  }

  const settings = isRecord(value.settings) ? value.settings : value;
  return {
    provider: readString(settings.provider, DEFAULT_USER_RERANK_SETTINGS.provider),
    model: readString(settings.model, DEFAULT_USER_RERANK_SETTINGS.model),
    baseUrl: readString(settings.base_url),
    instruct: readString(settings.instruct),
    hasApiKey: settings.has_api_key === true,
    apiKeyHint: readApiKeyHint(settings.api_key_hint),
    requiresApiKey: settings.requires_api_key === true,
    timeoutSeconds: readNumber(settings.timeout_seconds, DEFAULT_USER_RERANK_SETTINGS.timeoutSeconds),
    maxRetries: readNumber(settings.max_retries, DEFAULT_USER_RERANK_SETTINGS.maxRetries),
  };
}

export function toUserRerankSettingsPayload(
  settings: UserRerankSettings,
  apiKey: string,
  requiresBaseUrl: boolean,
  requiresApiKey: boolean
) {
  const trimmedApiKey = apiKey.trim();

  return {
    provider: settings.provider.trim(),
    model: settings.model.trim(),
    ...(requiresBaseUrl ? { base_url: settings.baseUrl.trim() } : {}),
    ...(settings.instruct.trim() ? { instruct: settings.instruct.trim() } : {}),
    ...(requiresApiKey && trimmedApiKey ? { api_key: trimmedApiKey } : {}),
    timeout_seconds: settings.timeoutSeconds,
    max_retries: settings.maxRetries,
  };
}

export function getSettingsMessage(value: unknown, fallback: string) {
  if (!isRecord(value)) {
    return fallback;
  }

  for (const key of ["detail", "error", "message"] as const) {
    const candidate = value[key];

    if (typeof candidate === "string" && candidate.trim()) {
      return candidate.trim();
    }
  }

  return fallback;
}

export function isSuccessfulResponse(value: unknown) {
  return isRecord(value) && value.success === true;
}

export function parseSettingsTestResult(value: unknown): SettingsTestResult | null {
  if (!isRecord(value) || value.success !== true) {
    return null;
  }

  const models = Array.isArray(value.models)
    ? value.models
        .filter((model): model is string => typeof model === "string")
        .map((model) => model.trim())
        .filter(Boolean)
    : [];

  return {
    message: readString(value.message, "模型连接测试成功"),
    models,
    modelListAvailable: value.model_list_available === true,
  };
}

export function parseEmbeddingSettingsTestResult(value: unknown): EmbeddingSettingsTestResult | null {
  if (!isRecord(value) || value.success !== true) {
    return null;
  }

  return {
    message: readString(value.message, "向量模型连接测试成功"),
    provider: readString(value.provider),
    model: readString(value.model),
    dimensions: readNumber(value.dimensions, 0) || null,
  };
}

export function parseRerankSettingsTestResult(value: unknown): RerankSettingsTestResult | null {
  if (!isRecord(value) || value.success !== true) {
    return null;
  }
  const topScore = readNumber(value.top_score, Number.NaN);

  return {
    message: readString(value.message, "Rerank 模型连接测试成功"),
    provider: readString(value.provider),
    model: readString(value.model),
    topScore: Number.isFinite(topScore) ? topScore : null,
  };
}

export function parseProviderModels(value: unknown) {
  if (!isRecord(value) || value.success !== true || !Array.isArray(value.models)) {
    return null;
  }

  return value.models
    .filter((model): model is string => typeof model === "string")
    .map((model) => model.trim())
    .filter(Boolean);
}
