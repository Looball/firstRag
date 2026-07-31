import { describe, expect, it, vi } from "vitest";
import type {
  ChatSession,
  ChatSource,
  RetrievalState,
} from "./types";
import {
  appendAssistantContentToSessions,
  setAssistantFallbackInSessions,
  setAssistantMessageIdInSessions,
  setAssistantRetrievalInSessions,
  setAssistantSourcesInSessions,
} from "./use-chat-response-stream";

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

describe("useChatResponseStream helpers", () => {
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
});
