import { describe, expect, it, vi } from "vitest";
import type {
  ChatSession,
  KnowledgeBase,
} from "./types";
import {
  chooseInitialKnowledgeBaseId,
  chooseVisibleSessionId,
  getWorkspaceAuthUsername,
  getWorkspaceBootstrapError,
} from "./use-workspace-bootstrap";

vi.mock("@/lib/frontend-api", () => ({
  authenticatedFetch: vi.fn(),
  authenticatedJson: vi.fn(),
  authenticatedText: vi.fn(),
  redirectToLogin: vi.fn(),
}));

const knowledgeBases: KnowledgeBase[] = [
  {
    id: "kb-first",
    name: "第一个知识库",
    isDefault: false,
    fileCount: 0,
  },
  {
    id: "kb-default",
    name: "默认知识库",
    isDefault: true,
    fileCount: 1,
  },
];

const sessions: ChatSession[] = [
  {
    id: "session-1",
    knowledgeBaseId: "kb-default",
    title: "会话一",
    messages: [],
    messagesLoaded: true,
  },
  {
    id: "session-2",
    knowledgeBaseId: "kb-default",
    title: "会话二",
    messages: [],
    messagesLoaded: true,
  },
  {
    id: "session-other",
    knowledgeBaseId: "kb-first",
    title: "其他会话",
    messages: [],
    messagesLoaded: true,
  },
];

describe("useWorkspaceBootstrap helpers", () => {
  it("reads a normalized username from a valid auth state", () => {
    expect(
      getWorkspaceAuthUsername(
        JSON.stringify({
          access_token: "token",
          token_type: "bearer",
          user: { username: "  researcher  " },
        }),
      ),
    ).toBe("researcher");
    expect(
      getWorkspaceAuthUsername(
        JSON.stringify({
          access_token: "token",
          token_type: "bearer",
          user: { name: "研究员" },
        }),
      ),
    ).toBe("研究员");
  });

  it("rejects missing, malformed and incomplete auth state", () => {
    expect(getWorkspaceAuthUsername(null)).toBeNull();
    expect(getWorkspaceAuthUsername("{broken")).toBeNull();
    expect(
      getWorkspaceAuthUsername(
        JSON.stringify({ access_token: "token" }),
      ),
    ).toBeNull();
  });

  it("chooses the default, first or empty initial knowledge base", () => {
    expect(chooseInitialKnowledgeBaseId(knowledgeBases)).toBe("kb-default");
    expect(
      chooseInitialKnowledgeBaseId([
        { ...knowledgeBases[0], id: "kb-only" },
      ]),
    ).toBe("kb-only");
    expect(chooseInitialKnowledgeBaseId([])).toBe("");
  });

  it("keeps a visible current session or falls back to the first", () => {
    expect(
      chooseVisibleSessionId(sessions, "kb-default", "session-2"),
    ).toBe("session-2");
    expect(
      chooseVisibleSessionId(sessions, "kb-default", "missing"),
    ).toBe("session-1");
    expect(
      chooseVisibleSessionId(sessions, "kb-missing", "session-1"),
    ).toBe("");
  });

  it("preserves Error messages and falls back for unknown failures", () => {
    expect(getWorkspaceBootstrapError(new Error("请求失败"))).toBe(
      "请求失败",
    );
    expect(getWorkspaceBootstrapError("失败")).toBe(
      "读取知识库列表失败，请稍后再试。",
    );
  });
});
