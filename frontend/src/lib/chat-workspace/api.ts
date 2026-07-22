import { z } from "zod";
import {
  authenticatedFetch,
  authenticatedJson,
  authenticatedText,
} from "@/lib/frontend-api";
import type {
  BackendKnowledgeBase,
  ChatSession,
  CreateConversationResponse,
  CreateKnowledgeBaseResponse,
  DeletedKnowledgeBase,
  EvalCaseDraftResponse,
  KnowledgeBase,
  KnowledgeBaseRetrievalSettings,
  KnowledgeFile,
  KnowledgeSourcePreview,
  ListMessagesResponse,
  MessageFeedback,
  MessageFeedbackReason,
  MessageFeedbackResponse,
  MessageFeedbackRating,
  MessageDiagnostic,
  MessageAttachment,
  MessageSourceFeedback,
  MessageSourceFeedbackRating,
  MessageSourceFeedbackResponse,
  PdfOcrPageCorrection,
  QualityDashboard,
  RetrievalSettingsResponse,
  UploadKnowledgeFilesResponse,
  UploadChatAttachmentsResponse,
  VectorIndexHealthResponse,
  VectorIndexJob,
  VectorIndexResponse,
} from "./types";
import {
  getConversationDiagnostics,
  getVectorIndexJobs,
  parseJsonValue,
  parseVectorIndexHealth,
  removeLegacyInitialMessage,
  serializeRetrievalSettings,
  toChatSession,
  toKnowledgeBase,
  toKnowledgeFile,
  toMessageFeedback,
  toMessageAttachment,
  toMessageSourceFeedback,
  toMessages,
  toQualityDashboard,
  toRetrievalSettings,
} from "./utils";

const filesResponseSchema = z
  .object({
    files: z.array(z.unknown()).default([]),
  })
  .passthrough();

const knowledgeBasesResponseSchema = z
  .object({
    knowledge_bases: z.array(z.unknown()).default([]),
  })
  .passthrough();

const retrievalSettingsResponseSchema = z
  .object({
    settings: z.unknown(),
  })
  .passthrough();

const sourcePreviewResponseSchema = z
  .object({
    file: z.object({
      id: z.string().min(1),
      original_name: z.string().min(1),
      mime_type: z.string().min(1),
      index_version: z.number().int().nonnegative(),
    }),
    target_chunk_index: z.number().int().nonnegative(),
    chunks: z.array(
      z.object({
        chunk_index: z.number().int().nonnegative(),
        content: z.string(),
        location: z.record(
          z.string(),
          z.union([z.string(), z.number(), z.boolean()]),
        ).default({}),
        is_target: z.boolean(),
      }),
    ),
  })
  .passthrough();

const pdfOcrCorrectionResponseSchema = z
  .object({
    correction: z.object({
      file_id: z.string().min(1),
      page_number: z.number().int().positive(),
      index_version: z.number().int().nonnegative(),
      original_text: z.string().default(""),
      current_text: z.string().default(""),
      corrected_text: z.string().nullable().default(null),
      has_correction: z.boolean(),
      revision: z.number().int().nonnegative(),
      updated_at: z.string().nullable().default(null),
      ocr_confidence: z.number().optional(),
      ocr_quality: z.string().default("unknown"),
    }),
    job: z.unknown().optional(),
  })
  .passthrough();

function parsePdfOcrCorrection(value: unknown): PdfOcrPageCorrection {
  const parsed = pdfOcrCorrectionResponseSchema.safeParse(value);
  if (!parsed.success) {
    throw new Error("OCR 校对响应格式异常。");
  }
  const correction = parsed.data.correction;
  return {
    fileId: correction.file_id,
    pageNumber: correction.page_number,
    indexVersion: correction.index_version,
    originalText: correction.original_text,
    currentText: correction.current_text,
    correctedText: correction.corrected_text,
    hasCorrection: correction.has_correction,
    revision: correction.revision,
    updatedAt: correction.updated_at,
    ...(correction.ocr_confidence !== undefined
      ? { ocrConfidence: correction.ocr_confidence }
      : {}),
    ocrQuality: correction.ocr_quality,
  };
}

function jsonHeaders() {
  return {
    "Content-Type": "application/json",
  };
}

function parseFilesResponse(data: unknown, sourceFiles?: File[]) {
  const parsed = filesResponseSchema.safeParse(data);

  if (!parsed.success) {
    throw new Error("文件列表响应格式异常。");
  }

  return parsed.data.files
    .map((value, index) => toKnowledgeFile(value, sourceFiles?.[index]))
    .filter((file): file is KnowledgeFile => file !== null);
}

export async function listKnowledgeBaseFiles(knowledgeBaseId: string) {
  const data = await authenticatedJson<unknown>(
    `/api/chat/knowledge-base/${encodeURIComponent(knowledgeBaseId)}/files`,
    { method: "GET" },
    { fallbackMessage: "读取知识库文件失败，请稍后再试。" },
  );

  return parseFilesResponse(data);
}

export async function listAllKnowledgeFiles() {
  const data = await authenticatedJson<unknown>(
    "/api/chat/knowledge-files",
    { method: "GET" },
    { fallbackMessage: "读取用户文件列表失败，请稍后再试。" },
  );

  return parseFilesResponse(data);
}

export async function loadKnowledgeSourcePreview(
  knowledgeFileId: string,
  chunkIndex: number,
  radius = 1,
  indexVersion?: number,
): Promise<KnowledgeSourcePreview> {
  const indexVersionQuery =
    indexVersion === undefined ? "" : `&index_version=${indexVersion}`;
  const data = await authenticatedJson<unknown>(
    `/api/chat/knowledge-files/${encodeURIComponent(
      knowledgeFileId,
    )}/chunks/${chunkIndex}?radius=${radius}${indexVersionQuery}`,
    { method: "GET" },
    { fallbackMessage: "读取引用原文失败，请稍后再试。" },
  );
  const parsed = sourcePreviewResponseSchema.safeParse(data);

  if (!parsed.success) {
    throw new Error("引用原文响应格式异常。");
  }

  return {
    fileId: parsed.data.file.id,
    fileName: parsed.data.file.original_name,
    mimeType: parsed.data.file.mime_type,
    indexVersion: parsed.data.file.index_version,
    targetChunkIndex: parsed.data.target_chunk_index,
    chunks: parsed.data.chunks.map((chunk) => ({
      chunkIndex: chunk.chunk_index,
      content: chunk.content,
      location: chunk.location,
      isTarget: chunk.is_target,
    })),
  };
}

export async function loadKnowledgeFileContent(knowledgeFileId: string) {
  const response = await authenticatedFetch(
    `/api/chat/knowledge-files/${encodeURIComponent(knowledgeFileId)}/content`,
    { method: "GET" },
    { fallbackMessage: "读取原始文件失败，请稍后再试。" },
  );
  return response.blob();
}

export async function loadKnowledgePdfPagePreview(
  knowledgeFileId: string,
  pageNumber: number,
) {
  const response = await authenticatedFetch(
    `/api/chat/knowledge-files/${encodeURIComponent(
      knowledgeFileId,
    )}/pages/${pageNumber}/preview`,
    { method: "GET" },
    { fallbackMessage: "读取 PDF 页面预览失败，请稍后再试。" },
  );
  return response.blob();
}

export async function loadVectorIndexHealth() {
  const data = await authenticatedJson<unknown>(
    "/api/chat/vector-index-jobs/health",
    { method: "GET" },
    { fallbackMessage: "任务状态暂不可用" },
  );
  const health = parseVectorIndexHealth(data);

  if (!health) {
    throw new Error("任务状态暂不可用");
  }

  return health;
}

export async function createKnowledgeBase(name: string) {
  const data = await authenticatedJson<CreateKnowledgeBaseResponse>(
    "/api/chat/knowledge-base",
    {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify({ name }),
    },
    { fallbackMessage: "创建知识库失败，请稍后再试。" },
  );
  const knowledgeBase = toKnowledgeBase(data.knowledge_base);

  if (!knowledgeBase) {
    throw new Error("创建知识库响应缺少有效的 knowledge_base。");
  }

  return knowledgeBase;
}

export async function renameKnowledgeBase(
  knowledgeBaseId: string,
  name: string,
) {
  const data = await authenticatedJson<CreateKnowledgeBaseResponse>(
    `/api/chat/knowledge-base/${encodeURIComponent(knowledgeBaseId)}`,
    {
      method: "PATCH",
      headers: jsonHeaders(),
      body: JSON.stringify({ name }),
    },
    { fallbackMessage: "重命名知识库失败，请稍后再试。" },
  );
  const knowledgeBase = toKnowledgeBase(data.knowledge_base);

  if (!knowledgeBase) {
    throw new Error("重命名响应缺少有效的 knowledge_base。");
  }

  return knowledgeBase;
}

export async function deleteKnowledgeBase(knowledgeBaseId: string) {
  await authenticatedText(
    `/api/chat/knowledge-base/${encodeURIComponent(knowledgeBaseId)}`,
    { method: "DELETE" },
    { fallbackMessage: "删除知识库失败，请稍后再试。" },
  );
}

export async function listDeletedKnowledgeBases() {
  const data = await authenticatedJson<unknown>(
    "/api/chat/knowledge-bases/trash",
    { method: "GET" },
    { fallbackMessage: "读取知识库回收站失败，请稍后再试。" },
  );
  const parsed = knowledgeBasesResponseSchema.safeParse(data);

  if (!parsed.success) {
    throw new Error("知识库回收站响应格式异常。");
  }

  return parsed.data.knowledge_bases
    .map((value): DeletedKnowledgeBase | null => {
      const knowledgeBase = toKnowledgeBase(value);
      const backendKnowledgeBase = value as BackendKnowledgeBase;
      const conversationCount = Number(
        backendKnowledgeBase.conversation_count,
      );

      if (
        !knowledgeBase ||
        typeof backendKnowledgeBase.deleted_at !== "string" ||
        !backendKnowledgeBase.deleted_at
      ) {
        return null;
      }

      return {
        ...knowledgeBase,
        conversationCount: Number.isFinite(conversationCount)
          ? conversationCount
          : 0,
        deletedAt: backendKnowledgeBase.deleted_at,
      };
    })
    .filter(
      (knowledgeBase): knowledgeBase is DeletedKnowledgeBase =>
        knowledgeBase !== null,
    );
}

export async function restoreKnowledgeBase(knowledgeBaseId: string) {
  const data = await authenticatedJson<CreateKnowledgeBaseResponse>(
    `/api/chat/knowledge-base/${encodeURIComponent(knowledgeBaseId)}/restore`,
    { method: "POST" },
    { fallbackMessage: "恢复知识库失败，请稍后再试。" },
  );
  const knowledgeBase = toKnowledgeBase(data.knowledge_base);

  if (!knowledgeBase) {
    throw new Error("恢复响应缺少有效的 knowledge_base。");
  }

  return knowledgeBase;
}

export async function getRetrievalSettings(knowledgeBaseId: string) {
  const data = await authenticatedJson<unknown>(
    `/api/chat/knowledge-base/${encodeURIComponent(
      knowledgeBaseId,
    )}/retrieval-settings`,
    { method: "GET" },
    { fallbackMessage: "读取检索设置失败，请稍后再试。" },
  );
  const parsed = retrievalSettingsResponseSchema.safeParse(data);

  return toRetrievalSettings(parsed.success ? parsed.data.settings : null);
}

export async function saveRetrievalSettings(
  knowledgeBaseId: string,
  settings: KnowledgeBaseRetrievalSettings,
) {
  const data = await authenticatedJson<RetrievalSettingsResponse>(
    `/api/chat/knowledge-base/${encodeURIComponent(
      knowledgeBaseId,
    )}/retrieval-settings`,
    {
      method: "PATCH",
      headers: jsonHeaders(),
      body: JSON.stringify(serializeRetrievalSettings(settings)),
    },
    { fallbackMessage: "保存检索设置失败，请稍后再试。" },
  );

  return toRetrievalSettings(data.settings);
}

export async function uploadKnowledgeFiles(
  knowledgeBaseId: string,
  selectedFiles: File[],
) {
  const formData = new FormData();
  selectedFiles.forEach((file) => formData.append("files", file));
  formData.append("description", "");
  formData.append("auto_index", "false");

  const data = await authenticatedJson<UploadKnowledgeFilesResponse>(
    `/api/chat/knowledge-base/${encodeURIComponent(knowledgeBaseId)}/files`,
    {
      method: "POST",
      body: formData,
    },
    { fallbackMessage: "上传文件失败，请稍后再试。" },
  );
  const uploadedFiles = parseFilesResponse(data, selectedFiles);

  if (uploadedFiles.length === 0) {
    throw new Error("上传响应缺少有效的 files 数据。");
  }

  return uploadedFiles;
}

export async function uploadChatAttachments(
  conversationId: string,
  selectedFiles: File[],
) {
  const formData = new FormData();
  selectedFiles.forEach((file) => formData.append("files", file));

  const data = await authenticatedJson<UploadChatAttachmentsResponse>(
    `/api/chat/attachments?conversation_id=${encodeURIComponent(conversationId)}`,
    {
      method: "POST",
      body: formData,
    },
    { fallbackMessage: "上传图片失败，请稍后再试。" },
  );

  const attachments = Array.isArray(data.attachments)
    ? data.attachments
        .map(toMessageAttachment)
        .filter((attachment): attachment is MessageAttachment => attachment !== null)
    : [];

  if (attachments.length === 0) {
    throw new Error("上传响应缺少有效的图片附件。");
  }

  return attachments;
}

export async function attachKnowledgeFile(knowledgeBaseId: string, fileId: string) {
  await authenticatedText(
    `/api/chat/knowledge-base/${encodeURIComponent(
      knowledgeBaseId,
    )}/files/${encodeURIComponent(fileId)}`,
    { method: "POST" },
    { fallbackMessage: "添加文件关联失败，请稍后再试。" },
  );
}

export async function removeKnowledgeFile(knowledgeBaseId: string, fileId: string) {
  await authenticatedText(
    `/api/chat/knowledge-base/${encodeURIComponent(
      knowledgeBaseId,
    )}/files/${encodeURIComponent(fileId)}`,
    { method: "DELETE" },
    { fallbackMessage: "解除文件关联失败，请稍后再试。" },
  );
}

export async function getVectorIndexJob(jobId: string) {
  const data = await authenticatedJson<VectorIndexResponse>(
    `/api/chat/vector-index-jobs/${encodeURIComponent(jobId)}`,
    { method: "GET" },
    { fallbackMessage: "查询向量化任务失败，请稍后再试。" },
  );

  return getVectorIndexJobs(data)[0] || null;
}

export async function indexKnowledgeFile(fileId: string) {
  const data = await authenticatedJson<VectorIndexResponse>(
    `/api/chat/knowledge-files/${encodeURIComponent(fileId)}/vectors`,
    { method: "POST" },
    { fallbackMessage: "提交文件向量化失败，请稍后再试。" },
  );

  return getVectorIndexJobs(data);
}

export async function reindexKnowledgeFileOcrPage(
  fileId: string,
  pageNumber: number,
) {
  const data = await authenticatedJson<VectorIndexResponse>(
    `/api/chat/knowledge-files/${encodeURIComponent(
      fileId,
    )}/ocr/pages/${pageNumber}/reindex`,
    { method: "POST" },
    { fallbackMessage: "提交 OCR 重新识别失败，请稍后再试。" },
  );
  const job = getVectorIndexJobs(data)[0];
  if (!job) {
    throw new Error("OCR 重新识别响应缺少任务信息。");
  }
  return job;
}

export async function loadPdfOcrPageCorrection(
  fileId: string,
  pageNumber: number,
) {
  const data = await authenticatedJson<unknown>(
    `/api/chat/knowledge-files/${encodeURIComponent(
      fileId,
    )}/ocr/pages/${pageNumber}/correction`,
    { method: "GET" },
    { fallbackMessage: "读取 OCR 校对文本失败，请稍后再试。" },
  );
  return parsePdfOcrCorrection(data);
}

export async function savePdfOcrPageCorrection(
  fileId: string,
  pageNumber: number,
  correctedText: string,
) {
  const data = await authenticatedJson<VectorIndexResponse>(
    `/api/chat/knowledge-files/${encodeURIComponent(
      fileId,
    )}/ocr/pages/${pageNumber}/correction`,
    {
      method: "PATCH",
      headers: jsonHeaders(),
      body: JSON.stringify({ corrected_text: correctedText }),
    },
    { fallbackMessage: "保存 OCR 人工修订失败，请稍后再试。" },
  );
  const job = getVectorIndexJobs(data)[0];
  if (!job) {
    throw new Error("OCR 校对响应缺少任务信息。");
  }
  return { correction: parsePdfOcrCorrection(data), job };
}

export async function deletePdfOcrPageCorrection(
  fileId: string,
  pageNumber: number,
) {
  const data = await authenticatedJson<VectorIndexResponse>(
    `/api/chat/knowledge-files/${encodeURIComponent(
      fileId,
    )}/ocr/pages/${pageNumber}/correction`,
    { method: "DELETE" },
    { fallbackMessage: "撤销 OCR 人工修订失败，请稍后再试。" },
  );
  const job = getVectorIndexJobs(data)[0];
  if (!job) {
    throw new Error("OCR 校对撤销响应缺少任务信息。");
  }
  return job;
}

export async function deleteKnowledgeFileVectors(fileId: string) {
  await authenticatedText(
    `/api/chat/knowledge-files/${encodeURIComponent(fileId)}/vectors`,
    { method: "DELETE" },
    { fallbackMessage: "删除文件向量失败，请稍后再试。" },
  );
}

export async function permanentlyDeleteKnowledgeFile(fileId: string) {
  await authenticatedText(
    `/api/chat/knowledge-files/${encodeURIComponent(fileId)}`,
    { method: "DELETE" },
    { fallbackMessage: "永久删除知识文件失败，请稍后再试。" },
  );
}

export async function indexKnowledgeBase(knowledgeBaseId: string) {
  const data = await authenticatedJson<VectorIndexResponse>(
    `/api/chat/knowledge-base/${encodeURIComponent(knowledgeBaseId)}/vectors`,
    { method: "POST" },
    { fallbackMessage: "提交知识库向量化失败，请稍后再试。" },
  );

  return getVectorIndexJobs(data);
}

export async function createConversation(
  knowledgeBaseId: string,
  title = "新对话",
) {
  const data = await authenticatedJson<CreateConversationResponse>(
    `/api/chat/knowledge-bases/${encodeURIComponent(
      knowledgeBaseId,
    )}/conversations`,
    {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify({ title }),
    },
    { fallbackMessage: "创建对话失败，请稍后再试。" },
  );
  const conversation = data.conversation || data;
  const conversationId = conversation.id;

  if (typeof conversationId !== "string" || !conversationId.trim()) {
    throw new Error("创建对话响应缺少 conversation.id。");
  }

  return {
    id: conversationId,
    knowledgeBaseId,
    title:
      typeof conversation.title === "string" && conversation.title.trim()
        ? conversation.title.trim()
        : title,
    messages: [],
    messagesLoaded: true,
  } satisfies ChatSession;
}

export async function listConversationMessages(conversationId: string) {
  const data = await authenticatedJson<ListMessagesResponse>(
    `/api/chat/conversations/${encodeURIComponent(conversationId)}/messages`,
    { method: "GET" },
    { fallbackMessage: "读取会话消息失败，请稍后再试。" },
  );

  return Array.isArray(data.messages)
    ? removeLegacyInitialMessage(toMessages(data.messages))
    : [];
}

export async function submitMessageFeedback(
  messageId: string,
  feedback: {
    rating: MessageFeedbackRating;
    reason?: MessageFeedbackReason | null;
    note?: string | null;
  },
) {
  const data = await authenticatedJson<MessageFeedbackResponse>(
    `/api/chat/messages/${encodeURIComponent(messageId)}/feedback`,
    {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify({
        rating: feedback.rating,
        reason: feedback.reason || null,
        note: feedback.note || null,
      }),
    },
    { fallbackMessage: "保存反馈失败，请稍后再试。" },
  );
  const parsedFeedback = toMessageFeedback(data.feedback);

  if (!parsedFeedback) {
    throw new Error("反馈响应格式异常。");
  }

  return parsedFeedback satisfies MessageFeedback;
}

export async function submitMessageSourceFeedback(
  messageId: string,
  sourceIndex: number,
  feedback: {
    rating: MessageSourceFeedbackRating;
    note?: string | null;
  },
) {
  const data = await authenticatedJson<MessageSourceFeedbackResponse>(
    `/api/chat/messages/${encodeURIComponent(
      messageId,
    )}/sources/${encodeURIComponent(String(sourceIndex))}/feedback`,
    {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify({
        rating: feedback.rating,
        note: feedback.note || null,
      }),
    },
    { fallbackMessage: "保存引用反馈失败，请稍后再试。" },
  );
  const parsedFeedback = toMessageSourceFeedback(data.feedback);

  if (!parsedFeedback) {
    throw new Error("引用反馈响应格式异常。");
  }

  return parsedFeedback satisfies MessageSourceFeedback;
}

export async function exportEvalCaseDraft(messageId: string) {
  const data = await authenticatedJson<EvalCaseDraftResponse>(
    `/api/chat/messages/${encodeURIComponent(messageId)}/eval-case-draft`,
    { method: "GET" },
    { fallbackMessage: "导出 eval case 草稿失败，请稍后再试。" },
  );

  if (typeof data.draft !== "object" || data.draft === null) {
    throw new Error("eval case 草稿响应格式异常。");
  }

  return data.draft as Record<string, unknown>;
}

export async function loadQualityDashboard(days = 7) {
  const data = await authenticatedJson<unknown>(
    `/api/chat/quality-dashboard?days=${encodeURIComponent(String(days))}`,
    { method: "GET" },
    { fallbackMessage: "加载质量看板失败，请稍后再试。" },
  );
  const dashboard = toQualityDashboard(data);

  if (!dashboard) {
    throw new Error("质量看板响应格式异常。");
  }

  return dashboard satisfies QualityDashboard;
}

export async function listKnowledgeBasesAndSessions() {
  const data = await authenticatedJson<unknown>(
    "/api/chat/knowledge-bases",
    { method: "GET" },
    { fallbackMessage: "读取知识库列表失败，请稍后再试。" },
  );
  const parsed = knowledgeBasesResponseSchema.safeParse(data);

  if (!parsed.success) {
    throw new Error("知识库列表响应格式异常。");
  }

  const knowledgeBases: KnowledgeBase[] = [];
  const sessionMap = new Map<string, ChatSession>();

  for (const value of parsed.data.knowledge_bases) {
    const knowledgeBase = toKnowledgeBase(value);

    if (!knowledgeBase) {
      continue;
    }

    knowledgeBases.push(knowledgeBase);

    const backendKnowledgeBase = value as BackendKnowledgeBase;
    const conversations = Array.isArray(backendKnowledgeBase.conversations)
      ? backendKnowledgeBase.conversations
      : [];

    for (const conversation of conversations) {
      const session = toChatSession(conversation, knowledgeBase.id);

      if (session) {
        sessionMap.set(session.id, session);
      }
    }
  }

  return {
    knowledgeBases,
    sessions: Array.from(sessionMap.values()),
  };
}

export async function deleteConversation(
  knowledgeBaseId: string,
  conversationId: string,
) {
  await authenticatedText(
    `/api/chat/knowledge-bases/${encodeURIComponent(
      knowledgeBaseId,
    )}/conversations/${encodeURIComponent(conversationId)}`,
    { method: "DELETE" },
    { fallbackMessage: "删除会话失败，请稍后再试。" },
  );
}

export async function renameConversation(
  knowledgeBaseId: string,
  conversationId: string,
  title: string,
) {
  await authenticatedText(
    `/api/chat/knowledge-bases/${encodeURIComponent(
      knowledgeBaseId,
    )}/conversations/${encodeURIComponent(conversationId)}`,
    {
      method: "PATCH",
      headers: jsonHeaders(),
      body: JSON.stringify({ title }),
    },
    { fallbackMessage: "重命名失败，请稍后再试。" },
  );
}

export async function loadConversationDiagnostics(conversationId: string) {
  const responseText = await authenticatedText(
    `/api/chat/conversations/${encodeURIComponent(conversationId)}/diagnostics`,
    { method: "GET" },
    { fallbackMessage: "加载诊断信息失败，请稍后再试。" },
  );
  const data = parseJsonValue(responseText);

  return getConversationDiagnostics(data) satisfies MessageDiagnostic[];
}

export async function postChatMessage(
  conversationId: string,
  knowledgeBaseId: string,
  message: string,
  attachmentIds: string[] = [],
) {
  return authenticatedFetch(
    "/api/chat",
    {
      method: "POST",
      headers: jsonHeaders(),
      body: JSON.stringify({
        conversation_id: conversationId,
        knowledge_base_id: knowledgeBaseId,
        message,
        attachment_ids: attachmentIds,
      }),
    },
    { fallbackMessage: "请求失败了，请稍后再试。" },
  );
}

export type { VectorIndexHealthResponse, VectorIndexJob };
