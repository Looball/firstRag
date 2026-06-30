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
  KnowledgeBase,
  KnowledgeBaseRetrievalSettings,
  KnowledgeFile,
  ListMessagesResponse,
  MessageFeedback,
  MessageFeedbackReason,
  MessageFeedbackResponse,
  MessageFeedbackRating,
  MessageDiagnostic,
  RetrievalSettingsResponse,
  UploadKnowledgeFilesResponse,
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
  toMessages,
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

export async function deleteKnowledgeFileVectors(fileId: string) {
  await authenticatedText(
    `/api/chat/knowledge-files/${encodeURIComponent(fileId)}/vectors`,
    { method: "DELETE" },
    { fallbackMessage: "删除文件向量失败，请稍后再试。" },
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
      }),
    },
    { fallbackMessage: "请求失败了，请稍后再试。" },
  );
}

export type { VectorIndexHealthResponse, VectorIndexJob };
