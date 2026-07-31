import { describe, expect, it, vi } from "vitest";
import type {
  ChatSession,
  ChatSource,
  MessageAttachment,
  RetrievalState,
} from "./types";
import {
  appendAssistantContentToSessions,
  appendUserMessageToSessions,
  getChatSubmissionError,
  setAssistantFallbackInSessions,
  setAssistantMessageIdInSessions,
  setAssistantRetrievalInSessions,
  setAssistantSourcesInSessions,
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

  it("creates and then appends streamed assistant content", () => {
    const withAssistant = appendAssistantContentToSessions(
      sessions,
      emptySession.id,
      "第一段",
    );
    const appended = appendAssistantContentToSessions(
      withAssistant,
      emptySession.id,
      "第二段",
    );

    expect(appended[0].messages).toEqual([
      { role: "assistant", content: "第一段第二段" },
    ]);
  });

  it("writes sources without replacing existing assistant content", () => {
    const source: ChatSource = {
      title: "资料",
      content: "引用内容",
      metadata: "metadata",
    };
    const withAssistant = appendAssistantContentToSessions(
      sessions,
      emptySession.id,
      "回答",
    );
    const withSources = setAssistantSourcesInSessions(
      withAssistant,
      emptySession.id,
      [source],
    );

    expect(withSources[0].messages[0]).toEqual({
      role: "assistant",
      content: "回答",
      sources: [source],
    });
    expect(
      setAssistantSourcesInSessions(withSources, emptySession.id, []),
    ).toBe(withSources);
  });

  it("creates an assistant placeholder for retrieval state", () => {
    const retrieval: RetrievalState = {
      need_retrieval: true,
      rewritten_query: "attention mechanism",
      reason: "需要知识库",
      retrieved_count: 4,
      source_count: 2,
    };
    const nextSessions = setAssistantRetrievalInSessions(
      sessions,
      emptySession.id,
      retrieval,
    );

    expect(nextSessions[0].messages).toEqual([
      {
        role: "assistant",
        content: "",
        retrieval,
      },
    ]);
  });

  it("sets a message ID only on an existing assistant message", () => {
    expect(
      setAssistantMessageIdInSessions(
        sessions,
        emptySession.id,
        "message-1",
      ),
    ).toBe(sessions);

    const withAssistant = appendAssistantContentToSessions(
      sessions,
      emptySession.id,
      "回答",
    );
    const withMessageId = setAssistantMessageIdInSessions(
      withAssistant,
      emptySession.id,
      "message-1",
    );

    expect(withMessageId[0].messages[0]).toEqual({
      id: "message-1",
      role: "assistant",
      content: "回答",
    });
    expect(
      setAssistantMessageIdInSessions(
        withMessageId,
        emptySession.id,
        "",
      ),
    ).toBe(withMessageId);
  });

  it("replaces assistant content with a final fallback or creates it", () => {
    const created = setAssistantFallbackInSessions(
      sessions,
      emptySession.id,
      "模型暂时没有返回内容。",
    );
    const replaced = setAssistantFallbackInSessions(
      created,
      emptySession.id,
      "最终回答",
    );

    expect(replaced[0].messages).toEqual([
      { role: "assistant", content: "最终回答" },
    ]);
  });

  it("preserves Error messages and falls back for unknown failures", () => {
    expect(getChatSubmissionError(new Error("请求失败"), "默认错误")).toBe(
      "请求失败",
    );
    expect(getChatSubmissionError("失败", "默认错误")).toBe("默认错误");
  });
});
