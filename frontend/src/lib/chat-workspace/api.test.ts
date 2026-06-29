import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  authenticatedFetch,
  authenticatedJson,
} from "@/lib/frontend-api";
import {
  createConversation,
  listAllKnowledgeFiles,
  listKnowledgeBasesAndSessions,
  loadVectorIndexHealth,
  postChatMessage,
} from "./api";

vi.mock("@/lib/frontend-api", () => ({
  authenticatedFetch: vi.fn(),
  authenticatedJson: vi.fn(),
  authenticatedText: vi.fn(),
}));

const authenticatedJsonMock = vi.mocked(authenticatedJson);
const authenticatedFetchMock = vi.mocked(authenticatedFetch);

describe("chat workspace api", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("normalizes knowledge file response envelopes", async () => {
    const fileId = "11111111-1111-4111-8111-111111111111";
    authenticatedJsonMock.mockResolvedValueOnce({
      files: [
        {
          id: fileId,
          original_name: "notes.md",
          mime_type: "text/markdown",
          size_bytes: 7,
          status: "pending",
          usage_count: 2,
          latest_index_job: null,
          created_at: "2026-06-29T00:00:00+08:00",
        },
      ],
    });

    await expect(listAllKnowledgeFiles()).resolves.toEqual([
      expect.objectContaining({
        id: fileId,
        name: "notes.md",
        size: 7,
        status: "pending",
        usageCount: 2,
      }),
    ]);
    expect(authenticatedJsonMock).toHaveBeenCalledWith(
      "/api/chat/knowledge-files",
      { method: "GET" },
      { fallbackMessage: "读取用户文件列表失败，请稍后再试。" },
    );
  });

  it("rejects malformed knowledge file response envelopes", async () => {
    authenticatedJsonMock.mockResolvedValueOnce({ files: "bad" });

    await expect(listAllKnowledgeFiles()).rejects.toThrow(
      "文件列表响应格式异常。",
    );
  });

  it("normalizes knowledge bases and nested sessions", async () => {
    const knowledgeBaseId = "22222222-2222-4222-8222-222222222222";
    const conversationId = "33333333-3333-4333-8333-333333333333";
    authenticatedJsonMock.mockResolvedValueOnce({
      knowledge_bases: [
        {
          id: knowledgeBaseId,
          name: "合同库",
          is_default: false,
          file_count: 3,
          conversations: [
            {
              id: conversationId,
              knowledge_base_id: knowledgeBaseId,
              title: "合同问答",
            },
          ],
        },
      ],
    });

    await expect(listKnowledgeBasesAndSessions()).resolves.toEqual({
      knowledgeBases: [
        expect.objectContaining({
          id: knowledgeBaseId,
          name: "合同库",
          fileCount: 3,
        }),
      ],
      sessions: [
        expect.objectContaining({
          id: conversationId,
          knowledgeBaseId,
          title: "合同问答",
        }),
      ],
    });
  });

  it("rejects malformed knowledge base response envelopes", async () => {
    authenticatedJsonMock.mockResolvedValueOnce({ knowledge_bases: "bad" });

    await expect(listKnowledgeBasesAndSessions()).rejects.toThrow(
      "知识库列表响应格式异常。",
    );
  });

  it("rejects invalid vector health payloads", async () => {
    authenticatedJsonMock.mockResolvedValueOnce({
      success: true,
      worker: { status: "active" },
    });

    await expect(loadVectorIndexHealth()).rejects.toThrow("任务状态暂不可用");
  });

  it("creates conversations with a JSON request body", async () => {
    const knowledgeBaseId = "44444444-4444-4444-8444-444444444444";
    authenticatedJsonMock.mockResolvedValueOnce({
      conversation: {
        id: "55555555-5555-4555-8555-555555555555",
        title: "新问题",
      },
    });

    await expect(createConversation(knowledgeBaseId, "新问题")).resolves.toEqual(
      expect.objectContaining({
        knowledgeBaseId,
        title: "新问题",
        messagesLoaded: true,
      }),
    );
    expect(authenticatedJsonMock).toHaveBeenCalledWith(
      `/api/chat/knowledge-bases/${knowledgeBaseId}/conversations`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "新问题" }),
      },
      { fallbackMessage: "创建对话失败，请稍后再试。" },
    );
  });

  it("keeps chat posting as a native Response for stream handling", async () => {
    const response = new Response("event: done\n\n", {
      headers: { "Content-Type": "text/event-stream" },
    });
    authenticatedFetchMock.mockResolvedValueOnce(response);

    await expect(
      postChatMessage("conversation-1", "knowledge-base-1", "hello"),
    ).resolves.toBe(response);
    expect(authenticatedFetchMock).toHaveBeenCalledWith(
      "/api/chat",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          conversation_id: "conversation-1",
          knowledge_base_id: "knowledge-base-1",
          message: "hello",
        }),
      },
      { fallbackMessage: "请求失败了，请稍后再试。" },
    );
  });
});
