import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  authenticatedFetch,
  authenticatedJson,
  authenticatedText,
} from "@/lib/frontend-api";
import {
  createConversation,
  deleteKnowledgeBase,
  exportEvalCaseDraft,
  listAllKnowledgeFiles,
  listConversationMessages,
  listKnowledgeBasesAndSessions,
  listDeletedKnowledgeBases,
  loadKnowledgeFileContent,
  loadKnowledgePdfPagePreview,
  loadPdfOcrQualityReport,
  loadKnowledgeSourcePreview,
  loadPdfOcrPageCorrection,
  loadQualityDashboard,
  loadVectorIndexHealth,
  postChatMessage,
  permanentlyDeleteKnowledgeFile,
  deletePdfOcrPageCorrection,
  reindexKnowledgeFileOcrPage,
  reindexKnowledgeFileOcrPages,
  retryKnowledgeFileOcrReindexBatch,
  renameKnowledgeBase,
  restoreKnowledgeBase,
  savePdfOcrPageCorrection,
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
const authenticatedTextMock = vi.mocked(authenticatedText);

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

  it("normalizes source chunk preview payloads", async () => {
    const fileId = "11111111-1111-4111-8111-111111111111";
    authenticatedJsonMock.mockResolvedValueOnce({
      success: true,
      file: {
        id: fileId,
        original_name: "guide.md",
        mime_type: "text/markdown",
        index_version: 3,
      },
      target_chunk_index: 2,
      chunks: [
        {
          chunk_index: 1,
          content: "previous",
          location: { h1: "指南" },
          is_target: false,
        },
        {
          chunk_index: 2,
          content: "target",
          location: { h1: "指南", h2: "安装" },
          is_target: true,
        },
      ],
    });

    await expect(loadKnowledgeSourcePreview(fileId, 2, 1, 3)).resolves.toEqual({
      fileId,
      fileName: "guide.md",
      mimeType: "text/markdown",
      indexVersion: 3,
      targetChunkIndex: 2,
      chunks: [
        {
          chunkIndex: 1,
          content: "previous",
          location: { h1: "指南" },
          isTarget: false,
        },
        {
          chunkIndex: 2,
          content: "target",
          location: { h1: "指南", h2: "安装" },
          isTarget: true,
        },
      ],
    });
    expect(authenticatedJsonMock).toHaveBeenCalledWith(
      `/api/chat/knowledge-files/${fileId}/chunks/2?radius=1&index_version=3`,
      { method: "GET" },
      { fallbackMessage: "读取引用原文失败，请稍后再试。" },
    );
  });

  it("loads original knowledge file content as a blob", async () => {
    const fileId = "11111111-1111-4111-8111-111111111111";
    const expectedBlob = new Blob(["original"], { type: "text/plain" });
    authenticatedFetchMock.mockResolvedValueOnce(
      new Response(expectedBlob, { status: 200 }),
    );

    const blob = await loadKnowledgeFileContent(fileId);

    await expect(blob.text()).resolves.toBe("original");
    expect(authenticatedFetchMock).toHaveBeenCalledWith(
      `/api/chat/knowledge-files/${fileId}/content`,
      { method: "GET" },
      { fallbackMessage: "读取原始文件失败，请稍后再试。" },
    );
  });

  it("loads a rendered PDF page preview as a blob", async () => {
    const expectedBlob = new Blob(["png"], { type: "image/png" });
    authenticatedFetchMock.mockResolvedValueOnce(
      new Response(expectedBlob, {
        status: 200,
        headers: { "Content-Type": "image/png" },
      }),
    );

    const blob = await loadKnowledgePdfPagePreview("file/1", 2);

    expect(blob.type).toBe("image/png");
    expect(authenticatedFetchMock).toHaveBeenCalledWith(
      "/api/chat/knowledge-files/file%2F1/pages/2/preview",
      { method: "GET" },
      { fallbackMessage: "读取 PDF 页面预览失败，请稍后再试。" },
    );
  });

  it("normalizes a PDF OCR quality report", async () => {
    const fileId = "11111111-1111-4111-8111-111111111111";
    authenticatedJsonMock.mockResolvedValueOnce({
      success: true,
      file: {
        id: fileId,
        original_name: "scan.pdf",
        status: "indexed",
        index_version: 4,
      },
      summary: {
        document_page_count: 2,
        ocr_page_count: 2,
        needs_review_count: 1,
        low_confidence_count: 1,
        corrected_count: 0,
        average_confidence: 65.25,
        max_reindex_pages: 20,
      },
      pages: [{
        page_number: 2,
        page_count: 2,
        chunk_index: 1,
        index_version: 4,
        ocr_confidence: 40.5,
        ocr_quality: "low",
        ocr_attempt: 2,
        needs_review: true,
        has_correction: false,
        correction_revision: 0,
        correction_updated_at: null,
        excerpt: "Needs review",
      }],
    });

    await expect(loadPdfOcrQualityReport(fileId)).resolves.toEqual({
      file: {
        id: fileId,
        originalName: "scan.pdf",
        status: "indexed",
        indexVersion: 4,
      },
      summary: {
        documentPageCount: 2,
        ocrPageCount: 2,
        needsReviewCount: 1,
        lowConfidenceCount: 1,
        correctedCount: 0,
        averageConfidence: 65.25,
        maxReindexPages: 20,
      },
      pages: [expect.objectContaining({
        pageNumber: 2,
        chunkIndex: 1,
        needsReview: true,
        ocrAttempt: 2,
        excerpt: "Needs review",
      })],
    });
    expect(authenticatedJsonMock).toHaveBeenCalledWith(
      `/api/chat/knowledge-files/${fileId}/ocr/pages`,
      { method: "GET" },
      { fallbackMessage: "读取 OCR 质量巡检失败，请稍后再试。" },
    );
  });

  it("submits a PDF OCR page reindex job", async () => {
    const fileId = "11111111-1111-4111-8111-111111111111";
    const jobId = "22222222-2222-4222-8222-222222222222";
    authenticatedJsonMock.mockResolvedValueOnce({
      success: true,
      page_number: 2,
      job: {
        id: jobId,
        knowledge_file_id: fileId,
        status: "queued",
      },
    });

    await expect(reindexKnowledgeFileOcrPage(fileId, 2)).resolves.toEqual(
      expect.objectContaining({
        id: jobId,
        knowledgeFileId: fileId,
        status: "queued",
      }),
    );
    expect(authenticatedJsonMock).toHaveBeenCalledWith(
      `/api/chat/knowledge-files/${fileId}/ocr/pages/2/reindex`,
      { method: "POST" },
      { fallbackMessage: "提交 OCR 重新识别失败，请稍后再试。" },
    );
  });

  it("submits one multi-page OCR reindex batch", async () => {
    const fileId = "11111111-1111-4111-8111-111111111111";
    const jobId = "22222222-2222-4222-8222-222222222222";
    authenticatedJsonMock.mockResolvedValueOnce({
      success: true,
      page_numbers: [1, 3],
      job: {
        id: jobId,
        knowledge_file_id: fileId,
        status: "queued",
      },
    });

    await expect(reindexKnowledgeFileOcrPages(fileId, [3, 1])).resolves.toEqual(
      expect.objectContaining({ id: jobId, status: "queued" }),
    );
    expect(authenticatedJsonMock).toHaveBeenCalledWith(
      `/api/chat/knowledge-files/${fileId}/ocr/pages/reindex`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ page_numbers: [3, 1] }),
      },
      { fallbackMessage: "提交批量 OCR 重新识别失败，请稍后再试。" },
    );
  });

  it("retries an OCR batch by failed job id without client page options", async () => {
    const fileId = "11111111-1111-4111-8111-111111111111";
    const failedJobId = "22222222-2222-4222-8222-222222222222";
    const retryJobId = "33333333-3333-4333-8333-333333333333";
    authenticatedJsonMock.mockResolvedValueOnce({
      success: true,
      job: {
        id: retryJobId,
        knowledge_file_id: fileId,
        status: "queued",
      },
    });

    await expect(
      retryKnowledgeFileOcrReindexBatch(fileId, failedJobId),
    ).resolves.toEqual(expect.objectContaining({ id: retryJobId }));
    expect(authenticatedJsonMock).toHaveBeenCalledWith(
      `/api/chat/knowledge-files/${fileId}/ocr/reindex-jobs/${failedJobId}/retry`,
      { method: "POST" },
      { fallbackMessage: "重试 OCR 重新识别失败，请稍后再试。" },
    );
  });

  it("loads a PDF OCR page correction editor payload", async () => {
    const fileId = "11111111-1111-4111-8111-111111111111";
    authenticatedJsonMock.mockResolvedValueOnce({
      success: true,
      correction: {
        file_id: fileId,
        page_number: 2,
        index_version: 4,
        original_text: "OCR ORIGINAL",
        current_text: "HUMAN CORRECTED",
        corrected_text: "HUMAN CORRECTED",
        has_correction: true,
        revision: 2,
        updated_at: "2026-07-21T12:00:00+08:00",
        ocr_confidence: 42.5,
        ocr_quality: "low",
      },
    });

    await expect(loadPdfOcrPageCorrection(fileId, 2)).resolves.toEqual({
      fileId,
      pageNumber: 2,
      indexVersion: 4,
      originalText: "OCR ORIGINAL",
      currentText: "HUMAN CORRECTED",
      correctedText: "HUMAN CORRECTED",
      hasCorrection: true,
      revision: 2,
      updatedAt: "2026-07-21T12:00:00+08:00",
      ocrConfidence: 42.5,
      ocrQuality: "low",
    });
  });

  it("saves and deletes a PDF OCR page correction through vector jobs", async () => {
    const fileId = "11111111-1111-4111-8111-111111111111";
    const saveJobId = "22222222-2222-4222-8222-222222222222";
    const deleteJobId = "33333333-3333-4333-8333-333333333333";
    authenticatedJsonMock
      .mockResolvedValueOnce({
        success: true,
        correction: {
          file_id: fileId,
          page_number: 2,
          index_version: 5,
          original_text: "OCR ORIGINAL",
          current_text: "HUMAN CORRECTED",
          corrected_text: "HUMAN CORRECTED",
          has_correction: true,
          revision: 1,
          updated_at: null,
          ocr_quality: "low",
        },
        job: {
          id: saveJobId,
          knowledge_file_id: fileId,
          status: "queued",
        },
      })
      .mockResolvedValueOnce({
        success: true,
        correction: {
          file_id: fileId,
          page_number: 2,
          previous_index_version: 5,
          index_version: 6,
          has_correction: false,
        },
        job: {
          id: deleteJobId,
          knowledge_file_id: fileId,
          status: "queued",
        },
      });

    await expect(
      savePdfOcrPageCorrection(fileId, 2, "HUMAN CORRECTED"),
    ).resolves.toEqual({
      correction: expect.objectContaining({
        currentText: "HUMAN CORRECTED",
        revision: 1,
      }),
      job: expect.objectContaining({ id: saveJobId, status: "queued" }),
    });
    await expect(deletePdfOcrPageCorrection(fileId, 2)).resolves.toEqual(
      expect.objectContaining({ id: deleteJobId, status: "queued" }),
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

  it("normalizes deleted knowledge bases", async () => {
    const knowledgeBaseId = "22222222-2222-4222-8222-222222222222";
    authenticatedJsonMock.mockResolvedValueOnce({
      knowledge_bases: [
        {
          id: knowledgeBaseId,
          name: "归档资料",
          is_default: false,
          file_count: 2,
          conversation_count: 3,
          deleted_at: "2026-07-21T00:00:00+08:00",
        },
      ],
    });

    await expect(listDeletedKnowledgeBases()).resolves.toEqual([
      {
        id: knowledgeBaseId,
        name: "归档资料",
        isDefault: false,
        fileCount: 2,
        conversationCount: 3,
        deletedAt: "2026-07-21T00:00:00+08:00",
      },
    ]);
  });

  it("renames, deletes and restores knowledge bases", async () => {
    const knowledgeBaseId = "22222222-2222-4222-8222-222222222222";
    authenticatedJsonMock
      .mockResolvedValueOnce({
        knowledge_base: {
          id: knowledgeBaseId,
          name: "新名称",
          is_default: false,
          file_count: 2,
        },
      })
      .mockResolvedValueOnce({
        knowledge_base: {
          id: knowledgeBaseId,
          name: "新名称",
          is_default: false,
          file_count: 2,
        },
      });
    authenticatedTextMock.mockResolvedValueOnce("");

    await expect(renameKnowledgeBase(knowledgeBaseId, "新名称")).resolves.toEqual(
      expect.objectContaining({ id: knowledgeBaseId, name: "新名称" }),
    );
    await expect(deleteKnowledgeBase(knowledgeBaseId)).resolves.toBeUndefined();
    await expect(restoreKnowledgeBase(knowledgeBaseId)).resolves.toEqual(
      expect.objectContaining({ id: knowledgeBaseId, name: "新名称" }),
    );
    expect(authenticatedTextMock).toHaveBeenCalledWith(
      `/api/chat/knowledge-base/${knowledgeBaseId}`,
      { method: "DELETE" },
      { fallbackMessage: "删除知识库失败，请稍后再试。" },
    );
  });

  it("permanently deletes knowledge files", async () => {
    const fileId = "11111111-1111-4111-8111-111111111111";
    authenticatedTextMock.mockResolvedValueOnce("");

    await expect(permanentlyDeleteKnowledgeFile(fileId)).resolves.toBeUndefined();
    expect(authenticatedTextMock).toHaveBeenCalledWith(
      `/api/chat/knowledge-files/${fileId}`,
      { method: "DELETE" },
      { fallbackMessage: "永久删除知识文件失败，请稍后再试。" },
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
