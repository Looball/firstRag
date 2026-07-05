import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  authenticatedFetch,
  authenticatedJson,
} from "@/lib/frontend-api";
import {
  createConversation,
  exportEvalCaseDraft,
  listAllKnowledgeFiles,
  listConversationMessages,
  listKnowledgeBasesAndSessions,
  loadQualityDashboard,
  loadVectorIndexHealth,
  postChatMessage,
  submitMessageFeedback,
  submitMessageSourceFeedback,
  uploadChatAttachments,
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
          attachment_ids: [],
        }),
      },
      { fallbackMessage: "请求失败了，请稍后再试。" },
    );
  });

  it("uploads chat image attachments through form data", async () => {
    const file = new File(["image"], "chart.png", { type: "image/png" });
    authenticatedJsonMock.mockResolvedValueOnce({
      attachments: [
        {
          id: "attachment-1",
          original_name: "chart.png",
          mime_type: "image/png",
          size_bytes: 5,
          content_url: "/chat/attachments/attachment-1/content",
        },
      ],
    });

    await expect(
      uploadChatAttachments("conversation-1", [file]),
    ).resolves.toEqual([
      expect.objectContaining({
        id: "attachment-1",
        originalName: "chart.png",
        contentUrl: "/api/chat/attachments/attachment-1/content",
      }),
    ]);
    expect(authenticatedJsonMock).toHaveBeenCalledWith(
      "/api/chat/attachments?conversation_id=conversation-1",
      expect.objectContaining({
        method: "POST",
        body: expect.any(FormData),
      }),
      { fallbackMessage: "上传图片失败，请稍后再试。" },
    );
  });

  it("normalizes persisted message feedback from history", async () => {
    authenticatedJsonMock.mockResolvedValueOnce({
      messages: [
        {
          id: "42",
          role: "assistant",
          content: "回答",
          feedback: {
            id: "7",
            rating: "negative",
            reason: "missing_answer",
            note: "没有回答核心问题",
          },
          sources: [
            {
              index: 1,
              file_name: "民事诉讼法.pdf",
              content: "片段",
              feedback: {
                id: "11",
                source_index: 1,
                rating: "useful",
                note: null,
              },
            },
          ],
        },
      ],
    });

    await expect(listConversationMessages("conversation-1")).resolves.toEqual([
      expect.objectContaining({
        id: "42",
        feedback: {
          id: "7",
          rating: "negative",
          reason: "missing_answer",
          note: "没有回答核心问题",
        },
        sources: [
          expect.objectContaining({
            index: 1,
            feedback: {
              id: "11",
              sourceIndex: 1,
              knowledgeFileId: null,
              chunkIndex: null,
              rating: "useful",
              note: null,
            },
          }),
        ],
      }),
    ]);
  });

  it("submits message feedback through the workspace API", async () => {
    authenticatedJsonMock.mockResolvedValueOnce({
      feedback: {
        id: "9",
        rating: "negative",
        reason: "missing_answer",
        note: "没有回答核心问题",
      },
    });

    await expect(
      submitMessageFeedback("42", {
        rating: "negative",
        reason: "missing_answer",
        note: "没有回答核心问题",
      }),
    ).resolves.toEqual({
      id: "9",
      rating: "negative",
      reason: "missing_answer",
      note: "没有回答核心问题",
    });
    expect(authenticatedJsonMock).toHaveBeenCalledWith(
      "/api/chat/messages/42/feedback",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rating: "negative",
          reason: "missing_answer",
          note: "没有回答核心问题",
        }),
      },
      { fallbackMessage: "保存反馈失败，请稍后再试。" },
    );
  });

  it("submits source feedback through the workspace API", async () => {
    authenticatedJsonMock.mockResolvedValueOnce({
      feedback: {
        id: "11",
        source_index: 1,
        rating: "irrelevant",
        note: null,
      },
    });

    await expect(
      submitMessageSourceFeedback("42", 1, {
        rating: "irrelevant",
      }),
    ).resolves.toEqual({
      id: "11",
      sourceIndex: 1,
      knowledgeFileId: null,
      chunkIndex: null,
      rating: "irrelevant",
      note: null,
    });
    expect(authenticatedJsonMock).toHaveBeenCalledWith(
      "/api/chat/messages/42/sources/1/feedback",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rating: "irrelevant",
          note: null,
        }),
      },
      { fallbackMessage: "保存引用反馈失败，请稍后再试。" },
    );
  });

  it("exports eval case drafts through the workspace API", async () => {
    authenticatedJsonMock.mockResolvedValueOnce({
      draft: {
        id: "draft_message_42",
        knowledge_base_name: "默认知识库",
        question: "民事诉讼法的任务是什么",
        expected_keywords: [],
      },
    });

    await expect(exportEvalCaseDraft("42")).resolves.toEqual({
      id: "draft_message_42",
      knowledge_base_name: "默认知识库",
      question: "民事诉讼法的任务是什么",
      expected_keywords: [],
    });
    expect(authenticatedJsonMock).toHaveBeenCalledWith(
      "/api/chat/messages/42/eval-case-draft",
      { method: "GET" },
      { fallbackMessage: "导出 eval case 草稿失败，请稍后再试。" },
    );
  });

  it("normalizes quality dashboard payloads", async () => {
    authenticatedJsonMock.mockResolvedValueOnce({
      success: true,
      window_days: 7,
      has_feedback: true,
      message_feedback: {
        total: 4,
        positive: 1,
        negative: 3,
        negative_rate: 0.75,
        reason_distribution: [
          { reason: "missing_answer", count: 2 },
        ],
      },
      source_feedback: {
        total: 5,
        useful: 2,
        irrelevant: 3,
        irrelevant_rate: 0.6,
        top_irrelevant_files: [
          { file_name: "民事诉讼法.pdf", count: 2 },
        ],
      },
      retrieval: {
        assistant_messages: 8,
        average_sources: 2.5,
        average_first_token_ms: 1234.5,
      },
    });

    await expect(loadQualityDashboard(7)).resolves.toEqual({
      windowDays: 7,
      hasFeedback: true,
      messageFeedback: {
        total: 4,
        positive: 1,
        negative: 3,
        negativeRate: 0.75,
        reasonDistribution: [{ reason: "missing_answer", count: 2 }],
      },
      sourceFeedback: {
        total: 5,
        useful: 2,
        irrelevant: 3,
        irrelevantRate: 0.6,
        topIrrelevantFiles: [{ fileName: "民事诉讼法.pdf", count: 2 }],
      },
      retrieval: {
        assistantMessages: 8,
        averageSources: 2.5,
        averageFirstTokenMs: 1234.5,
      },
    });
    expect(authenticatedJsonMock).toHaveBeenCalledWith(
      "/api/chat/quality-dashboard?days=7",
      { method: "GET" },
      { fallbackMessage: "加载质量看板失败，请稍后再试。" },
    );
  });

  it("rejects malformed quality dashboard payloads", async () => {
    authenticatedJsonMock.mockResolvedValueOnce(null);

    await expect(loadQualityDashboard()).rejects.toThrow(
      "质量看板响应格式异常。",
    );
  });
});
