import { describe, expect, it, vi } from "vitest";
import type { KnowledgeBase } from "./types";
import {
  normalizeKnowledgeBaseName,
  renameKnowledgeBaseInList,
  upsertKnowledgeBase,
} from "./use-knowledge-base-lifecycle";

vi.mock("@/lib/frontend-api", () => ({
  authenticatedFetch: vi.fn(),
  authenticatedJson: vi.fn(),
  authenticatedText: vi.fn(),
}));

const knowledgeBases: KnowledgeBase[] = [
  {
    id: "kb-default",
    name: "默认知识库",
    isDefault: true,
    fileCount: 0,
  },
  {
    id: "kb-current",
    name: "当前知识库",
    isDefault: false,
    fileCount: 1,
  },
];

describe("useKnowledgeBaseLifecycle helpers", () => {
  it("trims knowledge base names for create and rename requests", () => {
    expect(normalizeKnowledgeBaseName("  研究资料  ")).toBe("研究资料");
    expect(normalizeKnowledgeBaseName("   ")).toBe("");
  });

  it("upserts a knowledge base without keeping a duplicate ID", () => {
    const replacement = {
      ...knowledgeBases[1],
      name: "替换名称",
    };

    expect(upsertKnowledgeBase(knowledgeBases, replacement)).toEqual([
      knowledgeBases[0],
      replacement,
    ]);
  });

  it("renames only the target knowledge base", () => {
    const renamed = {
      ...knowledgeBases[1],
      name: "新名称",
    };
    const updated = renameKnowledgeBaseInList(knowledgeBases, renamed);

    expect(updated[0]).toBe(knowledgeBases[0]);
    expect(updated[1].name).toBe("新名称");
  });
});
