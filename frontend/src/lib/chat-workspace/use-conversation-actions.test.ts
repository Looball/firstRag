import { describe, expect, it, vi } from "vitest";
import type { ChatSession } from "./types";
import {
  getConversationActionError,
  getDeleteSessionResult,
  normalizeSessionTitle,
  removeSessionRecord,
  renameSession,
} from "./use-conversation-actions";

vi.mock("@/lib/frontend-api", () => ({
  authenticatedFetch: vi.fn(),
  authenticatedJson: vi.fn(),
  authenticatedText: vi.fn(),
}));

function createSession(
  id: string,
  knowledgeBaseId: string,
  title = id,
): ChatSession {
  return {
    id,
    knowledgeBaseId,
    title,
    messages: [],
    messagesLoaded: false,
  };
}

describe("useConversationActions helpers", () => {
  it("renames only the target session", () => {
    const sessions = [
      createSession("session-1", "kb-1", "旧标题"),
      createSession("session-2", "kb-1", "其他标题"),
    ];

    const updated = renameSession(sessions, "session-1", "新标题");

    expect(updated[0].title).toBe("新标题");
    expect(updated[1]).toBe(sessions[1]);
  });

  it("normalizes rename titles with the existing fallback", () => {
    expect(normalizeSessionTitle("  新标题  ")).toBe("新标题");
    expect(normalizeSessionTitle("   ")).toBe("新对话");
  });

  it("selects the next visible session after deleting the active session", () => {
    const sessions = [
      createSession("session-1", "kb-1"),
      createSession("session-2", "kb-1"),
      createSession("session-3", "kb-2"),
    ];

    expect(
      getDeleteSessionResult(sessions, "session-1", "kb-1", "session-1"),
    ).toEqual({
      knowledgeBaseId: "kb-1",
      nextActiveSessionId: "session-2",
      remainingSessions: [sessions[1], sessions[2]],
      shouldClearComposer: true,
    });
  });

  it("keeps the active selection when deleting a different session", () => {
    const sessions = [
      createSession("session-1", "kb-1"),
      createSession("session-2", "kb-1"),
    ];

    const result = getDeleteSessionResult(
      sessions,
      "session-2",
      "kb-1",
      "session-1",
    );

    expect(result.nextActiveSessionId).toBe("session-1");
    expect(result.shouldClearComposer).toBe(false);
  });

  it("clears the active selection after deleting the last visible session", () => {
    const sessions = [
      createSession("session-1", "kb-1"),
      createSession("session-2", "kb-2"),
    ];

    const result = getDeleteSessionResult(
      sessions,
      "session-1",
      "kb-1",
      "session-1",
    );

    expect(result.nextActiveSessionId).toBe("");
    expect(result.shouldClearComposer).toBe(true);
  });

  it("removes only the target session record", () => {
    expect(
      removeSessionRecord(
        {
          "session-1": "错误",
          "session-2": "",
        },
        "session-1",
      ),
    ).toEqual({ "session-2": "" });
  });

  it("preserves Error messages and falls back for unknown failures", () => {
    expect(
      getConversationActionError(new Error("请求失败"), "默认错误"),
    ).toBe("请求失败");
    expect(getConversationActionError("失败", "默认错误")).toBe("默认错误");
  });
});
