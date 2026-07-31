import { describe, expect, it, vi } from "vitest";
import type { ChatSession, KnowledgeBase } from "./types";
import {
  buildKnowledgeBaseDeleteConfirmation,
  chooseRefreshedKnowledgeBaseId,
  chooseRefreshedSessionId,
  getKnowledgeBaseLifecycleError,
} from "./use-knowledge-base-trash-actions";

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

const sessions: ChatSession[] = [
  {
    id: "session-1",
    knowledgeBaseId: "kb-current",
    title: "会话一",
    messages: [],
    messagesLoaded: true,
  },
  {
    id: "session-2",
    knowledgeBaseId: "kb-current",
    title: "会话二",
    messages: [],
    messagesLoaded: true,
  },
];

describe("useKnowledgeBaseTrashActions helpers", () => {
  it("prefers restored, current, default, then first knowledge base", () => {
    expect(
      chooseRefreshedKnowledgeBaseId(
        knowledgeBases,
        "kb-default",
        "kb-current",
      ),
    ).toBe("kb-default");
    expect(
      chooseRefreshedKnowledgeBaseId(
        knowledgeBases,
        "missing",
        "kb-current",
      ),
    ).toBe("kb-current");
    expect(
      chooseRefreshedKnowledgeBaseId(
        knowledgeBases,
        undefined,
        "missing",
      ),
    ).toBe("kb-default");
    expect(
      chooseRefreshedKnowledgeBaseId(
        [{ ...knowledgeBases[1], id: "kb-only" }],
        undefined,
        "missing",
      ),
    ).toBe("kb-only");
  });

  it("keeps a visible session or falls back to the first session", () => {
    expect(
      chooseRefreshedSessionId(sessions, "kb-current", "session-2"),
    ).toBe("session-2");
    expect(
      chooseRefreshedSessionId(sessions, "kb-current", "missing"),
    ).toBe("session-1");
    expect(chooseRefreshedSessionId(sessions, "kb-empty", "missing")).toBe("");
  });

  it("includes the affected conversation count in delete confirmation", () => {
    expect(
      buildKnowledgeBaseDeleteConfirmation(knowledgeBases[1], sessions),
    ).toBe(
      "确认删除知识库“当前知识库”吗？2 个会话会暂时隐藏，但文件仍保留在文件库中，可从回收站恢复。",
    );
  });

  it("preserves Error messages and falls back for unknown failures", () => {
    expect(
      getKnowledgeBaseLifecycleError(new Error("请求失败"), "默认错误"),
    ).toBe("请求失败");
    expect(getKnowledgeBaseLifecycleError("失败", "默认错误")).toBe(
      "默认错误",
    );
  });
});
