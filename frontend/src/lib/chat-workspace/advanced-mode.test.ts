import { describe, expect, it } from "vitest";

import {
  ADVANCED_MODE_STORAGE_KEY,
  getAdvancedModeDefault,
  readAdvancedModePreference,
  writeAdvancedModePreference,
} from "./advanced-mode";

function createMemoryStorage(initialValue?: string | null) {
  const values = new Map<string, string>();

  if (initialValue !== undefined && initialValue !== null) {
    values.set(ADVANCED_MODE_STORAGE_KEY, initialValue);
  }

  return {
    getItem(key: string) {
      return values.get(key) ?? null;
    },
    setItem(key: string, value: string) {
      values.set(key, value);
    },
  };
}

describe("advanced mode preference", () => {
  it("parses truthy environment defaults", () => {
    expect(getAdvancedModeDefault("true")).toBe(true);
    expect(getAdvancedModeDefault("1")).toBe(true);
    expect(getAdvancedModeDefault("ON")).toBe(true);
    expect(getAdvancedModeDefault("false")).toBe(false);
    expect(getAdvancedModeDefault("")).toBe(false);
  });

  it("uses browser storage before the environment default", () => {
    expect(
      readAdvancedModePreference({
        storage: createMemoryStorage("false"),
        defaultValue: true,
      }),
    ).toBe(false);
    expect(
      readAdvancedModePreference({
        storage: createMemoryStorage("yes"),
        defaultValue: false,
      }),
    ).toBe(true);
  });

  it("falls back to the default when storage is empty or unavailable", () => {
    expect(
      readAdvancedModePreference({
        storage: createMemoryStorage(),
        defaultValue: true,
      }),
    ).toBe(true);
    expect(
      readAdvancedModePreference({
        storage: null,
        defaultValue: false,
      }),
    ).toBe(false);
  });

  it("persists the local switch without throwing on storage failures", () => {
    const storage = createMemoryStorage();

    writeAdvancedModePreference(true, storage);
    expect(storage.getItem(ADVANCED_MODE_STORAGE_KEY)).toBe("true");

    writeAdvancedModePreference(false, storage);
    expect(storage.getItem(ADVANCED_MODE_STORAGE_KEY)).toBe("false");

    expect(() =>
      writeAdvancedModePreference(true, {
        getItem: () => null,
        setItem: () => {
          throw new Error("storage unavailable");
        },
      }),
    ).not.toThrow();
  });
});
