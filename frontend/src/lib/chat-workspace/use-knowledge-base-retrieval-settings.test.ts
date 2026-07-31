import { describe, expect, it, vi } from "vitest";
import {
  DEFAULT_KNOWLEDGE_BASE_ID,
  DEFAULT_RETRIEVAL_SETTINGS,
} from "./constants";
import {
  cacheRetrievalSettings,
  getCachedRetrievalSettings,
  getRetrievalSettingsError,
  shouldLoadKnowledgeBaseRetrievalSettings,
  updateCachedRetrievalSettings,
} from "./use-knowledge-base-retrieval-settings";

vi.mock("@/lib/frontend-api", () => ({
  authenticatedFetch: vi.fn(),
  authenticatedJson: vi.fn(),
  authenticatedText: vi.fn(),
}));

describe("useKnowledgeBaseRetrievalSettings helpers", () => {
  it("loads only for an authenticated advanced-mode knowledge base dialog", () => {
    const validOptions = {
      hasCheckedAuth: true,
      isAdvancedMode: true,
      isKnowledgeBaseManagerOpen: true,
      knowledgeBaseId: "kb-research",
    };

    expect(shouldLoadKnowledgeBaseRetrievalSettings(validOptions)).toBe(true);
    expect(
      shouldLoadKnowledgeBaseRetrievalSettings({
        ...validOptions,
        hasCheckedAuth: false,
      }),
    ).toBe(false);
    expect(
      shouldLoadKnowledgeBaseRetrievalSettings({
        ...validOptions,
        isAdvancedMode: false,
      }),
    ).toBe(false);
    expect(
      shouldLoadKnowledgeBaseRetrievalSettings({
        ...validOptions,
        isKnowledgeBaseManagerOpen: false,
      }),
    ).toBe(false);
    expect(
      shouldLoadKnowledgeBaseRetrievalSettings({
        ...validOptions,
        knowledgeBaseId: DEFAULT_KNOWLEDGE_BASE_ID,
      }),
    ).toBe(false);
  });

  it("falls back to a copy of the default settings for an uncached knowledge base", () => {
    const settings = getCachedRetrievalSettings({}, "kb-new");

    expect(settings).toEqual(DEFAULT_RETRIEVAL_SETTINGS);
    expect(settings).not.toBe(DEFAULT_RETRIEVAL_SETTINGS);
  });

  it("caches complete settings without changing other knowledge bases", () => {
    const otherSettings = {
      ...DEFAULT_RETRIEVAL_SETTINGS,
      topK: 2,
    };
    const nextSettings = {
      ...DEFAULT_RETRIEVAL_SETTINGS,
      topK: 6,
    };

    expect(
      cacheRetrievalSettings(
        { "kb-other": otherSettings },
        "kb-research",
        nextSettings,
      ),
    ).toEqual({
      "kb-other": otherSettings,
      "kb-research": nextSettings,
    });
  });

  it("merges a patch into cached or default settings", () => {
    const cache = updateCachedRetrievalSettings({}, "kb-research", {
      enableRerank: false,
      topK: 7,
    });

    expect(cache["kb-research"]).toEqual({
      ...DEFAULT_RETRIEVAL_SETTINGS,
      enableRerank: false,
      topK: 7,
    });
    expect(
      updateCachedRetrievalSettings(cache, "kb-research", {
        vectorTopK: 24,
      })["kb-research"],
    ).toEqual({
      ...DEFAULT_RETRIEVAL_SETTINGS,
      enableRerank: false,
      topK: 7,
      vectorTopK: 24,
    });
  });

  it("preserves Error messages and falls back for unknown failures", () => {
    expect(
      getRetrievalSettingsError(new Error("请求失败"), "默认错误"),
    ).toBe("请求失败");
    expect(getRetrievalSettingsError("失败", "默认错误")).toBe("默认错误");
  });
});
