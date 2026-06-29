import { describe, expect, it, vi } from "vitest";

import {
  applyJsonChatPayload,
  handleChatSseBlock,
  streamChatResponse,
} from "./chat-stream";
import type {
  ChatSource,
  RetrievalState,
} from "./types";

function createHandlers() {
  return {
    appendAssistantContent: vi.fn(),
    setAssistantFallback: vi.fn(),
    setAssistantMessageId: vi.fn(),
    setAssistantRetrieval: vi.fn<(retrieval: RetrievalState) => void>(),
    setAssistantSources: vi.fn<(sources: ChatSource[]) => void>(),
    onDone: vi.fn(),
  };
}

describe("chat stream SSE block handling", () => {
  it("merges answer, retrieval, sources and done events", () => {
    const handlers = createHandlers();
    let streamedAnswer = "";

    let result = handleChatSseBlock(
      [
        "event: retrieval",
        'data: {"need_retrieval":true,"rewritten_query":"RAG","reason":"hit","retrieved_count":2,"source_count":1}',
      ].join("\n"),
      streamedAnswer,
      handlers,
    );
    streamedAnswer = result.streamedAnswer;

    expect(handlers.setAssistantRetrieval).toHaveBeenCalledWith({
      need_retrieval: true,
      final_need_retrieval: null,
      llm_need_retrieval: null,
      rewritten_query: "RAG",
      reason: "hit",
      llm_reason: "",
      override_applied: false,
      override_reason: "",
      retrieved_count: 2,
      source_count: 1,
    });

    result = handleChatSseBlock(
      [
        "event: sources",
        'data: {"sources":[{"file_name":"guide.md","content":"chunk"}]}',
      ].join("\n"),
      streamedAnswer,
      handlers,
    );
    streamedAnswer = result.streamedAnswer;
    expect(handlers.setAssistantSources).toHaveBeenCalledWith([
      expect.objectContaining({
        content: "chunk",
        fileName: "guide.md",
        title: "guide.md",
      }),
    ]);

    result = handleChatSseBlock(
      ['event: answer', 'data: {"answer":"Hello"}'].join("\n"),
      streamedAnswer,
      handlers,
    );
    streamedAnswer = result.streamedAnswer;
    expect(streamedAnswer).toBe("Hello");
    expect(handlers.appendAssistantContent).toHaveBeenLastCalledWith("Hello");

    result = handleChatSseBlock(
      [
        "event: done",
        'data: {"message_id":"assistant-1","answer":"Hello","sources":[{"file_name":"guide.md","content":"chunk"}]}',
      ].join("\n"),
      streamedAnswer,
      handlers,
    );

    expect(result.isDone).toBe(true);
    expect(handlers.setAssistantMessageId).toHaveBeenCalledWith(
      "assistant-1",
    );
    expect(handlers.onDone).toHaveBeenCalledOnce();
    expect(handlers.setAssistantFallback).not.toHaveBeenCalled();
  });

  it("uses done answer as fallback when stream content differs", () => {
    const handlers = createHandlers();

    const result = handleChatSseBlock(
      ["event: done", 'data: {"answer":"final answer"}'].join("\n"),
      "partial",
      handlers,
    );

    expect(result.isDone).toBe(true);
    expect(handlers.setAssistantFallback).toHaveBeenCalledWith(
      "final answer",
    );
    expect(handlers.appendAssistantContent).not.toHaveBeenCalledWith(
      "final answer",
    );
  });

  it("appends done answer when no answer token streamed", () => {
    const handlers = createHandlers();

    const result = handleChatSseBlock(
      ["event: done", 'data: {"answer":"final answer"}'].join("\n"),
      "",
      handlers,
    );

    expect(result.streamedAnswer).toBe("final answer");
    expect(handlers.appendAssistantContent).toHaveBeenCalledWith(
      "final answer",
    );
    expect(handlers.setAssistantFallback).not.toHaveBeenCalled();
  });
});

describe("chat stream response handling", () => {
  it("applies JSON responses through the same assistant callbacks", () => {
    const handlers = createHandlers();

    applyJsonChatPayload(
      {
        assistant_message_id: "assistant-2",
        answer: "JSON answer",
        retrieval: {
          need_retrieval: false,
          reason: "local",
        },
        sources: [{ file_name: "source.md", content: "chunk" }],
      },
      handlers,
    );

    expect(handlers.setAssistantMessageId).toHaveBeenCalledWith(
      "assistant-2",
    );
    expect(handlers.setAssistantRetrieval).toHaveBeenCalledWith(
      expect.objectContaining({
        need_retrieval: false,
        reason: "local",
      }),
    );
    expect(handlers.setAssistantSources).toHaveBeenCalledWith([
      expect.objectContaining({ fileName: "source.md" }),
    ]);
    expect(handlers.setAssistantFallback).toHaveBeenCalledWith(
      "JSON answer",
    );
  });

  it("streams SSE chunks split across network frames", async () => {
    const handlers = createHandlers();
    const encoder = new TextEncoder();
    const response = new Response(
      new ReadableStream({
        start(controller) {
          controller.enqueue(
            encoder.encode('event: answer\ndata: {"answer":"Hel'),
          );
          controller.enqueue(
            encoder.encode(
              'lo"}\n\nevent: done\ndata: {"message_id":"assistant-3","answer":"Hello"}\n\n',
            ),
          );
          controller.close();
        },
      }),
      {
        headers: {
          "Content-Type": "text/event-stream; charset=utf-8",
        },
      },
    );

    await streamChatResponse(response, handlers, {
      waitForPaint: async () => undefined,
    });

    expect(handlers.appendAssistantContent).toHaveBeenCalledWith("");
    expect(handlers.appendAssistantContent).toHaveBeenCalledWith("Hello");
    expect(handlers.setAssistantMessageId).toHaveBeenCalledWith(
      "assistant-3",
    );
    expect(handlers.setAssistantFallback).not.toHaveBeenCalled();
  });

  it("uses a done-only SSE answer without applying empty fallback", async () => {
    const handlers = createHandlers();
    const encoder = new TextEncoder();
    const response = new Response(
      new ReadableStream({
        start(controller) {
          controller.enqueue(
            encoder.encode(
              'event: done\ndata: {"message_id":"assistant-4","answer":"Final only"}\n\n',
            ),
          );
          controller.close();
        },
      }),
      {
        headers: {
          "Content-Type": "text/event-stream; charset=utf-8",
        },
      },
    );

    await streamChatResponse(response, handlers, {
      waitForPaint: async () => undefined,
    });

    expect(handlers.appendAssistantContent).toHaveBeenCalledWith(
      "Final only",
    );
    expect(handlers.setAssistantFallback).not.toHaveBeenCalled();
  });
});
