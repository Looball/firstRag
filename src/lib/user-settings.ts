export type CredentialMode = "platform" | "user";

export type UserLLMSettings = {
  credentialMode: CredentialMode;
  provider: string;
  model: string;
  baseUrl: string;
  hasApiKey: boolean;
};

export const DEFAULT_USER_LLM_SETTINGS: UserLLMSettings = {
  credentialMode: "platform",
  provider: "deepseek",
  model: "deepseek-chat",
  baseUrl: "",
  hasApiKey: false,
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function readString(value: unknown, fallback = "") {
  return typeof value === "string" ? value : fallback;
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
  };
}

export function toUserLLMSettingsPayload(
  settings: UserLLMSettings,
  apiKey: string
) {
  const trimmedApiKey = apiKey.trim();

  return {
    credential_mode: settings.credentialMode,
    provider: settings.provider.trim(),
    model: settings.model.trim(),
    base_url: settings.provider === "custom" ? settings.baseUrl.trim() : null,
    ...(trimmedApiKey ? { api_key: trimmedApiKey } : {}),
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
