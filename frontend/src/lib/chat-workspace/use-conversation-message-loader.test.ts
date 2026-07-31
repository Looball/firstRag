import { describe, expect, it, vi } from "vitest";
import type { ChatSession, Message } from "./types";
import {
  getConversationMessageLoadError,
  updateConversationMessages,
} from "./use-conversation-message-loader";

vi.mock("@/lib/frontend-api", () => ({
  authenticatedFetch: vi.fn(),
  authenticatedJson: vi.fn(),
  authenticatedText: vi.fn(),
}));

/**
 * 构造消息懒加载 helper 使用的最小会话。
 */
function createSession(id: string): ChatSession {
  return {
    id,
    knowledgeBaseId: "kb-1",
    title: id,
    messages: [],
    messagesLoaded: false,
  };
}

describe("useConversationMessageLoader helpers", () => {
  it("writes loaded messages only to the target session", () => {
    const sessions = [createSession("session-1"), createSession("session-2")];
    const messages: Message[] = [{ role: "user", content: "问题" }];

    const updated = updateConversationMessages(
      sessions,
      "session-1",
      messages,
    );

    expect(updated[0]).toMatchObject({
      messages,
      messagesLoaded: true,
    });
    expect(updated[1]).toBe(sessions[1]);
  });

  it("preserves Error messages and falls back for unknown failures", () => {
    expect(getConversationMessageLoadError(new Error("请求失败"))).toBe(
      "请求失败",
    );
    expect(getConversationMessageLoadError("失败")).toBe(
      "读取会话消息失败，请稍后再试。",
    );
  });
});
