import { describe, expect, it, vi } from "vitest";
import type {
  ChatSession,
  MessageAttachment,
} from "./types";
import {
  appendUserMessageToSessions,
  getChatSubmissionError,
} from "./use-chat-submission";

vi.mock("@/lib/frontend-api", () => ({
  authenticatedFetch: vi.fn(),
  authenticatedJson: vi.fn(),
  authenticatedText: vi.fn(),
}));

const emptySession: ChatSession = {
  id: "session-target",
  knowledgeBaseId: "kb-research",
  title: "新对话",
  messages: [],
  messagesLoaded: true,
};

const otherSession: ChatSession = {
  id: "session-other",
  knowledgeBaseId: "kb-research",
  title: "其他会话",
  messages: [],
  messagesLoaded: true,
};

const sessions = [emptySession, otherSession];

describe("useChatSubmission helpers", () => {
  it("appends a user message, attachments and first-message title", () => {
    const attachment: MessageAttachment = {
      id: "attachment-1",
      originalName: "diagram.png",
      mimeType: "image/png",
      sizeBytes: 128,
      contentUrl: "/api/chat/attachments/attachment-1/content",
    };
    const nextSessions = appendUserMessageToSessions(
      sessions,
      emptySession.id,
      "解释一下注意力机制",
      [attachment],
    );

    expect(nextSessions[0]).toMatchObject({
      title: "解释一下注意力机制",
      messages: [
        {
          role: "user",
          content: "解释一下注意力机制",
          attachments: [attachment],
        },
      ],
    });
    expect(nextSessions[1]).toBe(otherSession);
  });

  it("preserves an existing title and omits empty attachments", () => {
    const session = {
      ...emptySession,
      title: "已有标题",
      messages: [{ role: "user" as const, content: "上一问" }],
    };
    const nextSession = appendUserMessageToSessions(
      [session],
      session.id,
      "下一问",
      [],
    )[0];

    expect(nextSession.title).toBe("已有标题");
    expect(nextSession.messages[1]).toEqual({
      role: "user",
      content: "下一问",
    });
  });

  it("preserves Error messages and falls back for unknown failures", () => {
    expect(getChatSubmissionError(new Error("请求失败"), "默认错误")).toBe(
      "请求失败",
    );
    expect(getChatSubmissionError("失败", "默认错误")).toBe("默认错误");
  });
});
