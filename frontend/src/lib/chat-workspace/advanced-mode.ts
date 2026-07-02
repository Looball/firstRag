export const ADVANCED_MODE_STORAGE_KEY = "firstrag:advanced-mode";

type AdvancedModeStorage = Pick<Storage, "getItem" | "setItem">;

const TRUE_VALUES = new Set(["1", "true", "yes", "on"]);

/**
 * Parses an environment-style value into the default advanced mode state.
 */
export function getAdvancedModeDefault(
  value = process.env.NEXT_PUBLIC_FIRSTRAG_ADVANCED_MODE_DEFAULT,
) {
  return TRUE_VALUES.has(String(value || "").trim().toLowerCase());
}

function getBrowserStorage(): AdvancedModeStorage | null {
  if (typeof window === "undefined") {
    return null;
  }

  return window.localStorage;
}

/**
 * Reads the local advanced mode preference and falls back to the env default.
 */
export function readAdvancedModePreference({
  storage = getBrowserStorage(),
  defaultValue = getAdvancedModeDefault(),
}: {
  storage?: AdvancedModeStorage | null;
  defaultValue?: boolean;
} = {}) {
  try {
    const storedValue = storage?.getItem(ADVANCED_MODE_STORAGE_KEY);

    if (storedValue === undefined || storedValue === null) {
      return defaultValue;
    }

    return TRUE_VALUES.has(storedValue.trim().toLowerCase());
  } catch {
    return defaultValue;
  }
}

/**
 * Persists the browser-local advanced mode preference when storage is usable.
 */
export function writeAdvancedModePreference(
  enabled: boolean,
  storage: AdvancedModeStorage | null = getBrowserStorage(),
) {
  try {
    storage?.setItem(ADVANCED_MODE_STORAGE_KEY, enabled ? "true" : "false");
  } catch {
    // 本地存储不可用时只影响当前会话，不阻断聊天主流程。
  }
}
