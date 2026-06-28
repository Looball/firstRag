"use client";

import Link from "next/link";
import {
  type ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  AUTH_STORAGE_KEY,
  buildAuthorizationHeader,
  getAuthUsername,
  parseAuthState,
} from "@/lib/auth";

type Message = {
  id?: string;
  role: "user" | "assistant";
  content: string;
  status?: string;
  errorMessage?: string | null;
  sources?: ChatSource[];
  retrieval?: RetrievalState;
};

type ChatSource = {
  title: string;
  content: string;
  metadata: string;
  index?: number;
  fileId?: string;
  fileName?: string;
  fileType?: string;
  chunkIndex?: number;
  vectorScore?: number;
  fulltextScore?: number;
  rerankScore?: number;
  rrfScore?: number;
  retrievalSources?: string[];
};

type RetrievalState = {
  need_retrieval: boolean;
  final_need_retrieval?: boolean | null;
  llm_need_retrieval?: boolean | null;
  rewritten_query: string;
  reason: string;
  llm_reason?: string;
  override_applied?: boolean;
  override_reason?: string;
  retrieved_count: number;
  source_count: number;
};

type MessageDiagnostic = {
  messageId: string;
  status: string;
  errorMessage: string | null;
  createdAt: string;
  needRetrieval: boolean | null;
  finalNeedRetrieval: boolean | null;
  llmNeedRetrieval: boolean | null;
  rewrittenQuery: string;
  reason: string;
  llmReason: string;
  overrideApplied: boolean;
  overrideReason: string;
  retrievedCount: number;
  sourceCount: number;
  retrievalSources: string[];
  vectorDegraded: boolean;
  diagnostics: RetrievalDiagnostics;
  sourcesPreview: SourcePreview[];
};

type RetrievalDiagnostics = {
  vectorDegraded?: boolean;
  vectorErrors: string[];
  vectorCount: number | null;
  fulltextCount: number | null;
  fusedCount: number | null;
  rerankedCount: number | null;
  retrievalSources: string[];
  llm: RetrievalLlmDiagnostics;
  timing: RetrievalTiming;
};

type RetrievalLlmDiagnostics = {
  provider: string;
  model: string;
  credentialMode: string;
  baseUrl: string;
  temperature: number | null;
  maxTokens: number | null;
  timeoutSeconds: number | null;
  maxRetries: number | null;
  promptTokens: number | null;
  completionTokens: number | null;
  totalTokens: number | null;
};

type RetrievalTiming = {
  standaloneQuestionMs: number | null;
  retrievalSettingsMs: number | null;
  knowledgeProfileMs: number | null;
  queryRouterMs: number | null;
  finalizeDecisionMs: number | null;
  retrieveDocumentsMs: number | null;
  embeddingMs: number | null;
  vectorMs: number | null;
  fulltextMs: number | null;
  rrfMs: number | null;
  rerankMs: number | null;
  retrievalTotalMs: number | null;
  preAnswerTotalMs: number | null;
  firstAnswerTokenMs: number | null;
  answerStreamMs: number | null;
  chatStreamTotalMs: number | null;
};

type SourcePreview = {
  index: number | null;
  fileId: string | null;
  fileName: string | null;
  chunkIndex: number | null;
  retrievalSources: string[];
  vectorScore: number | null;
  fulltextScore: number | null;
  rrfScore: number | null;
  rerankScore: number | null;
};

type ChatSession = {
  id: string;
  knowledgeBaseId: string;
  title: string;
  messages: Message[];
  messagesLoaded: boolean;
};

type KnowledgeBase = {
  id: string;
  name: string;
  isDefault: boolean;
  fileCount: number;
};

type RetrievalMode = "auto" | "always" | "never";

type KnowledgeBaseRetrievalSettings = {
  retrievalMode: RetrievalMode;
  enableQueryRouter: boolean;
  enableRerank: boolean;
  topK: number;
  vectorTopK: number;
  fulltextTopK: number;
  rrfK: number;
  rerankScoreThreshold: number;
};

type BackendKnowledgeBase = {
  id?: unknown;
  name?: unknown;
  is_default?: unknown;
  file_count?: unknown;
  conversations?: unknown;
};

type KnowledgeFile = {
  id: string;
  name: string;
  size: number;
  fingerprint: string;
  status: KnowledgeFileStatus;
  latestIndexJob: LatestIndexJob | null;
  usageCount: number | null;
};

type KnowledgeFileStatus =
  | "pending"
  | "queued"
  | "processing"
  | "indexed"
  | "failed";

type VectorIndexJobStatus =
  | "queued"
  | "processing"
  | "succeeded"
  | "failed";

type LatestIndexJobStatus =
  | "queued"
  | "processing"
  | "completed"
  | "failed"
  | "unknown";

type LatestIndexJob = {
  id: string;
  userId: number | null;
  knowledgeFileId: string;
  knowledgeBaseId: string | null;
  indexVersion: number | null;
  status: LatestIndexJobStatus;
  attempts: number | null;
  maxAttempts: number | null;
  errorMessage: string | null;
  createdAt: string;
  updatedAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  activeSeconds: number | null;
  isStale: boolean;
  workerHint: string | null;
  failureType: string | null;
  failureHint: string | null;
  canRetry: boolean;
};

type VectorStatus = {
  label: string;
  type:
    | "idle"
    | "pending"
    | "processing"
    | "completed"
    | "failed"
    | "unknown";
  canVectorize: boolean;
  canDeleteVector: boolean;
  canPoll: boolean;
  errorMessage?: string;
  workerHint?: string;
  failureHint?: string;
  canRetry?: boolean;
};

type VectorIndexHealthResponse = {
  worker: {
    status: "idle" | "waiting" | "active" | "attention_needed" | "unknown";
    isHealthy: boolean;
    hasRecentActivity: boolean;
    hint: string | null;
    lastJobUpdatedAt: string | null;
    lastProcessingHeartbeatAt: string | null;
    oldestActiveSeconds: number | null;
    oldestQueuedSeconds: number | null;
    oldestProcessingSeconds: number | null;
    staleQueued: number;
    staleProcessing: number;
    checkedAt: string;
  };
  queue: {
    status: "idle" | "waiting" | "processing" | "stuck" | "unknown";
    total: number;
    active: number;
    queued: number;
    processing: number;
    succeeded: number;
    failed: number;
    cancelled: number;
  };
};

type WorkerHealthTone = "muted" | "warning" | "success" | "danger";

type VectorIndexJob = {
  id: string;
  status: VectorIndexJobStatus;
  errorMessage: string;
  failureHint: string;
};

type VectorIndexQueueItem = VectorIndexJob & {
  targetName: string;
  targetType: "file" | "knowledge-base";
};

type BackendKnowledgeFile = {
  id?: unknown;
  original_name?: unknown;
  size_bytes?: unknown;
  status?: unknown;
  usage_count?: unknown;
  latest_index_job?: unknown;
};

type KnowledgeBaseFile = {
  knowledgeBaseId: string;
  knowledgeFileId: string;
};

type BackendConversation = {
  id?: unknown;
  knowledge_base_id?: unknown;
  title?: unknown;
  messages?: unknown;
};

type CreateConversationResponse = {
  conversation?: BackendConversation;
  id?: unknown;
  title?: unknown;
  answer?: string;
  detail?: string;
  error?: string;
  message?: string;
};

type ListMessagesResponse = {
  messages?: unknown;
  detail?: string;
  error?: string;
  message?: string;
};

type ListKnowledgeBasesResponse = {
  knowledge_bases?: unknown;
  detail?: string;
  error?: string;
  message?: string;
};

type CreateKnowledgeBaseResponse = {
  knowledge_base?: BackendKnowledgeBase;
  detail?: string;
  error?: string;
  message?: string;
};

type RetrievalSettingsResponse = {
  settings?: unknown;
  detail?: string;
  error?: string;
  message?: string;
};

type UploadKnowledgeFilesResponse = {
  files?: unknown;
  detail?: string;
  error?: string;
  message?: string;
};

type ListKnowledgeFilesResponse = UploadKnowledgeFilesResponse;

type VectorIndexResponse = {
  id?: unknown;
  job_id?: unknown;
  status?: unknown;
  error_message?: unknown;
  job?: unknown;
  jobs?: unknown;
  vector_index_job?: unknown;
  vector_index_jobs?: unknown;
  detail?: string;
  error?: string;
  message?: string;
};

const STORAGE_KEY = "ai-learning-assistant-sessions";
const CURRENT_SESSION_KEY = "ai-learning-assistant-current-session";
const DEFAULT_KNOWLEDGE_BASE_ID = "default";
const DEFAULT_RETRIEVAL_SETTINGS: KnowledgeBaseRetrievalSettings = {
  retrievalMode: "auto",
  enableQueryRouter: true,
  enableRerank: true,
  topK: 5,
  vectorTopK: 20,
  fulltextTopK: 20,
  rrfK: 20,
  rerankScoreThreshold: 0,
};
const LEGACY_INITIAL_MESSAGE =
  "你好，我是你的 AI 学习助手。你可以问我任何关于 AI 的问题。";

function redirectToLogin() {
  localStorage.removeItem(AUTH_STORAGE_KEY);
  localStorage.removeItem(STORAGE_KEY);
  localStorage.removeItem(CURRENT_SESSION_KEY);

  if (window.location.pathname !== "/login") {
    window.location.href = "/login";
  }
}

function isAuthExpiredMessage(message: string) {
  const normalizedMessage = message.toLowerCase();

  return (
    message.includes("登录已过期") ||
    message.includes("登录过期") ||
    message.includes("登录已失效") ||
    message.includes("请重新登录") ||
    normalizedMessage.includes("unauthorized") ||
    normalizedMessage.includes("not authenticated") ||
    normalizedMessage.includes("could not validate credentials") ||
    normalizedMessage.includes("invalid token") ||
    normalizedMessage.includes("token expired")
  );
}

function formatFileSize(size: number) {
  if (size < 1024) {
    return `${size} B`;
  }

  if (size < 1024 * 1024) {
    return `${Math.round(size / 1024)} KB`;
  }

  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDurationSeconds(seconds: number | null) {
  if (seconds === null || !Number.isFinite(seconds) || seconds < 0) {
    return "";
  }

  if (seconds < 60) {
    return `${Math.round(seconds)} 秒`;
  }

  const minutes = seconds / 60;
  if (minutes < 60) {
    return `${minutes.toFixed(minutes >= 10 ? 0 : 1)} 分钟`;
  }

  const hours = minutes / 60;
  return `${hours.toFixed(hours >= 10 ? 0 : 1)} 小时`;
}

function getFileFingerprint(file: File) {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

function buildSessionTitle(input: string) {
  const normalized = input.replace(/\s+/g, " ").trim();

  if (!normalized) {
    return "新对话";
  }

  return normalized.length > 24 ? `${normalized.slice(0, 24)}...` : normalized;
}

function toMessage(value: unknown): Message | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }

  const candidate = value as Record<string, unknown>;
  const role = candidate.role;

  if (
    (role !== "user" && role !== "assistant") ||
    typeof candidate.content !== "string"
  ) {
    return null;
  }

  const sourceContainer = Array.isArray(candidate.sources)
    ? { sources: candidate.sources }
    : Array.isArray(candidate.documents)
      ? { documents: candidate.documents }
      : Array.isArray(candidate.refs)
        ? { refs: candidate.refs }
        : null;
  const sources = sourceContainer ? getChatSources(sourceContainer) : [];
  const retrieval = getRetrievalState(candidate);
  const id = typeof candidate.id === "string" ? candidate.id : undefined;
  const status =
    typeof candidate.status === "string" ? candidate.status : undefined;
  const errorMessage =
    typeof candidate.error_message === "string"
      ? candidate.error_message
      : candidate.error_message === null
        ? null
        : undefined;

  return {
    ...(id ? { id } : {}),
    role,
    content: candidate.content,
    ...(status ? { status } : {}),
    ...(errorMessage !== undefined ? { errorMessage } : {}),
    ...(sources.length > 0 ? { sources } : {}),
    ...(retrieval ? { retrieval } : {}),
  };
}

function toMessages(values: unknown[]) {
  return values
    .map(toMessage)
    .filter((message): message is Message => message !== null);
}

function getResponseErrorMessage(
  errorText: string,
  fallback: string,
  status?: number
) {
  const getStringValue = (value: unknown) =>
    typeof value === "string" && value.trim() ? value.trim() : "";

  if (status === 401 || status === 403 || isAuthExpiredMessage(errorText)) {
    redirectToLogin();
  }

  try {
    const errorData = JSON.parse(errorText) as {
      answer?: unknown;
      detail?: unknown;
      error?: unknown;
      message?: unknown;
    };
    const directMessage =
      getStringValue(errorData.answer) ||
      getStringValue(errorData.detail) ||
      getStringValue(errorData.error) ||
      getStringValue(errorData.message);

    if (directMessage) {
      if (isAuthExpiredMessage(directMessage)) {
        redirectToLogin();
      }

      return directMessage;
    }

    if (Array.isArray(errorData.detail)) {
      const detailMessages = errorData.detail
        .map((detail) => {
          if (typeof detail === "string") {
            return detail;
          }

          if (typeof detail !== "object" || detail === null) {
            return "";
          }

          const candidate = detail as {
            loc?: unknown;
            msg?: unknown;
            type?: unknown;
          };
          const location = Array.isArray(candidate.loc)
            ? candidate.loc.join(".")
            : getStringValue(candidate.loc);
          const message = getStringValue(candidate.msg);
          const type = getStringValue(candidate.type);

          if (location && message) {
            return `${location}: ${message}`;
          }

          return message || type;
        })
        .filter(Boolean);

      if (detailMessages.length > 0) {
        const detailMessage = detailMessages.join("；");

        if (isAuthExpiredMessage(detailMessage)) {
          redirectToLogin();
        }

        return detailMessage;
      }
    }

    return fallback;
  } catch {
    const message = errorText.trim() || fallback;

    if (isAuthExpiredMessage(message)) {
      redirectToLogin();
    }

    return message;
  }
}

function getAssistantContent(value: unknown) {
  if (typeof value === "string") {
    return value;
  }

  if (typeof value !== "object" || value === null) {
    return "";
  }

  const candidate = value as {
    answer?: unknown;
    content?: unknown;
    assistant_message?: { content?: unknown };
    message?: { content?: unknown } | unknown;
    messages?: Array<{ role?: unknown; content?: unknown }>;
  };

  if (typeof candidate.assistant_message?.content === "string") {
    return candidate.assistant_message.content;
  }

  if (typeof candidate.answer === "string") {
    return candidate.answer;
  }

  if (typeof candidate.content === "string") {
    return candidate.content;
  }

  if (
    typeof candidate.message === "object" &&
    candidate.message !== null &&
    "content" in candidate.message &&
    typeof candidate.message.content === "string"
  ) {
    return candidate.message.content;
  }

  const assistantMessage = candidate.messages?.find(
    (message) =>
      message.role === "assistant" && typeof message.content === "string"
  );

  return typeof assistantMessage?.content === "string"
    ? assistantMessage.content
    : "";
}

function getAssistantMessageId(value: unknown) {
  if (typeof value !== "object" || value === null) {
    return "";
  }

  const candidate = value as Record<string, unknown>;
  const nestedMessage =
    typeof candidate.message === "object" && candidate.message !== null
      ? (candidate.message as Record<string, unknown>)
      : null;

  return (
    getStringField(candidate, ["message_id", "assistant_message_id", "id"]) ||
    (nestedMessage ? getStringField(nestedMessage, ["id"]) : "")
  );
}

function parseJsonValue(value: string) {
  try {
    return JSON.parse(value) as unknown;
  } catch {
    return value;
  }
}

function getNumberField(value: Record<string, unknown>, fieldName: string) {
  const fieldValue = value[fieldName];

  if (typeof fieldValue === "number" && Number.isFinite(fieldValue)) {
    return fieldValue;
  }

  if (typeof fieldValue === "string" && fieldValue.trim()) {
    const parsedValue = Number(fieldValue);

    return Number.isFinite(parsedValue) ? parsedValue : 0;
  }

  return 0;
}

function getOptionalNumberField(
  value: Record<string, unknown>,
  fieldNames: string[]
) {
  for (const fieldName of fieldNames) {
    const fieldValue = value[fieldName];

    if (typeof fieldValue === "number" && Number.isFinite(fieldValue)) {
      return fieldValue;
    }

    if (typeof fieldValue === "string" && fieldValue.trim()) {
      const parsedValue = Number(fieldValue);

      if (Number.isFinite(parsedValue)) {
        return parsedValue;
      }
    }
  }

  return undefined;
}

function getNullableNumberField(
  value: Record<string, unknown>,
  fieldNames: string[]
) {
  const numberValue = getOptionalNumberField(value, fieldNames);

  return numberValue === undefined ? null : numberValue;
}

function getNullableStringField(
  value: Record<string, unknown>,
  fieldNames: string[]
) {
  const stringValue = getStringField(value, fieldNames);

  return stringValue || null;
}

function getNullableBooleanField(
  value: Record<string, unknown>,
  fieldNames: string[]
) {
  for (const fieldName of fieldNames) {
    const fieldValue = value[fieldName];

    if (typeof fieldValue === "boolean") {
      return fieldValue;
    }

    if (typeof fieldValue === "string" && fieldValue.trim()) {
      const normalizedValue = fieldValue.trim().toLowerCase();

      if (["true", "1", "yes", "是"].includes(normalizedValue)) {
        return true;
      }

      if (["false", "0", "no", "否"].includes(normalizedValue)) {
        return false;
      }
    }
  }

  return null;
}

function getRetrievalState(value: unknown): RetrievalState | undefined {
  const parsedValue = typeof value === "string" ? parseJsonValue(value) : value;

  if (typeof parsedValue !== "object" || parsedValue === null) {
    return undefined;
  }

  const candidate = parsedValue as Record<string, unknown>;
  const retrievalValue =
    typeof candidate.retrieval === "object" && candidate.retrieval !== null
      ? candidate.retrieval
      : candidate;

  if (typeof retrievalValue !== "object" || retrievalValue === null) {
    return undefined;
  }

  const retrieval = retrievalValue as Record<string, unknown>;

  if (typeof retrieval.need_retrieval !== "boolean") {
    return undefined;
  }

  return {
    need_retrieval: retrieval.need_retrieval,
    final_need_retrieval: getNullableBooleanField(retrieval, [
      "final_need_retrieval",
    ]),
    llm_need_retrieval: getNullableBooleanField(retrieval, [
      "llm_need_retrieval",
    ]),
    rewritten_query:
      typeof retrieval.rewritten_query === "string"
        ? retrieval.rewritten_query
        : "",
    reason: typeof retrieval.reason === "string" ? retrieval.reason : "",
    llm_reason:
      typeof retrieval.llm_reason === "string" ? retrieval.llm_reason : "",
    override_applied: getNullableBooleanField(retrieval, [
      "override_applied",
    ]) === true,
    override_reason:
      typeof retrieval.override_reason === "string"
        ? retrieval.override_reason
        : "",
    retrieved_count: getNumberField(retrieval, "retrieved_count"),
    source_count: getNumberField(retrieval, "source_count"),
  };
}

function getStringField(
  value: Record<string, unknown>,
  fieldNames: string[]
) {
  for (const fieldName of fieldNames) {
    const fieldValue = value[fieldName];

    if (typeof fieldValue === "string" && fieldValue.trim()) {
      return fieldValue.trim();
    }

    if (typeof fieldValue === "number" && Number.isFinite(fieldValue)) {
      return String(fieldValue);
    }
  }

  return "";
}

function getRecordField(
  value: Record<string, unknown>,
  fieldName: string
): Record<string, unknown> | null {
  const fieldValue = value[fieldName];

  return typeof fieldValue === "object" && fieldValue !== null
    ? (fieldValue as Record<string, unknown>)
    : null;
}

function getStringArrayField(value: Record<string, unknown>, fieldName: string) {
  const fieldValue = value[fieldName];

  return Array.isArray(fieldValue)
    ? fieldValue
        .filter((item): item is string => typeof item === "string")
        .map((item) => item.trim())
        .filter(Boolean)
    : [];
}

function toSourcePreview(value: unknown): SourcePreview | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }

  const source = value as Record<string, unknown>;

  return {
    index: getNullableNumberField(source, ["index"]),
    fileId: getNullableStringField(source, ["file_id"]),
    fileName: getNullableStringField(source, ["file_name"]),
    chunkIndex: getNullableNumberField(source, ["chunk_index"]),
    retrievalSources: getStringArrayField(source, "retrieval_sources"),
    vectorScore: getNullableNumberField(source, ["vector_score"]),
    fulltextScore: getNullableNumberField(source, ["fulltext_score"]),
    rrfScore: getNullableNumberField(source, ["rrf_score"]),
    rerankScore: getNullableNumberField(source, ["rerank_score"]),
  };
}

function getSourcesPreview(value: Record<string, unknown>) {
  const sourcesPreview = value.sources_preview;

  return Array.isArray(sourcesPreview)
    ? sourcesPreview
        .map(toSourcePreview)
        .filter((source): source is SourcePreview => source !== null)
    : [];
}

function getRetrievalDiagnostics(
  value: Record<string, unknown>
): RetrievalDiagnostics {
  const diagnostics = getRecordField(value, "diagnostics") || {};
  const vectorDegraded = diagnostics.vector_degraded;
  const timing = getRecordField(diagnostics, "timing") || {};
  const llm = getRecordField(diagnostics, "llm") || {};

  return {
    ...(typeof vectorDegraded === "boolean"
      ? { vectorDegraded }
      : {}),
    vectorErrors: getStringArrayField(diagnostics, "vector_errors"),
    vectorCount: getNullableNumberField(diagnostics, ["vector_count"]),
    fulltextCount: getNullableNumberField(diagnostics, ["fulltext_count"]),
    fusedCount: getNullableNumberField(diagnostics, ["fused_count"]),
    rerankedCount: getNullableNumberField(diagnostics, ["reranked_count"]),
    retrievalSources: getStringArrayField(diagnostics, "retrieval_sources"),
    llm: {
      provider: getStringField(llm, ["provider"]),
      model: getStringField(llm, ["model"]),
      credentialMode: getStringField(llm, ["credential_mode"]),
      baseUrl: getStringField(llm, ["base_url"]),
      temperature: getNullableNumberField(llm, ["temperature"]),
      maxTokens: getNullableNumberField(llm, ["max_tokens"]),
      timeoutSeconds: getNullableNumberField(llm, ["timeout_seconds"]),
      maxRetries: getNullableNumberField(llm, ["max_retries"]),
      promptTokens: getNullableNumberField(llm, ["prompt_tokens"]),
      completionTokens: getNullableNumberField(llm, ["completion_tokens"]),
      totalTokens: getNullableNumberField(llm, ["total_tokens"]),
    },
    timing: {
      standaloneQuestionMs: getNullableNumberField(timing, [
        "standalone_question_ms",
      ]),
      retrievalSettingsMs: getNullableNumberField(timing, [
        "retrieval_settings_ms",
      ]),
      knowledgeProfileMs: getNullableNumberField(timing, [
        "knowledge_profile_ms",
      ]),
      queryRouterMs: getNullableNumberField(timing, ["query_router_ms"]),
      finalizeDecisionMs: getNullableNumberField(timing, [
        "finalize_decision_ms",
      ]),
      retrieveDocumentsMs: getNullableNumberField(timing, [
        "retrieve_documents_ms",
      ]),
      embeddingMs: getNullableNumberField(timing, ["embedding_ms"]),
      vectorMs: getNullableNumberField(timing, ["vector_ms"]),
      fulltextMs: getNullableNumberField(timing, ["fulltext_ms"]),
      rrfMs: getNullableNumberField(timing, ["rrf_ms"]),
      rerankMs: getNullableNumberField(timing, ["rerank_ms"]),
      retrievalTotalMs: getNullableNumberField(timing, [
        "retrieval_total_ms",
      ]),
      preAnswerTotalMs: getNullableNumberField(timing, [
        "pre_answer_total_ms",
      ]),
      firstAnswerTokenMs: getNullableNumberField(timing, [
        "first_answer_token_ms",
      ]),
      answerStreamMs: getNullableNumberField(timing, ["answer_stream_ms"]),
      chatStreamTotalMs: getNullableNumberField(timing, [
        "chat_stream_total_ms",
      ]),
    },
  };
}

function toMessageDiagnostic(value: unknown): MessageDiagnostic | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }

  const diagnostic = value as Record<string, unknown>;
  const messageId = getStringField(diagnostic, ["message_id"]);

  if (!messageId) {
    return null;
  }

  const needRetrievalValue = diagnostic.need_retrieval;

  return {
    messageId,
    status: getStringField(diagnostic, ["status"]),
    errorMessage:
      typeof diagnostic.error_message === "string"
        ? diagnostic.error_message
        : diagnostic.error_message === null
          ? null
          : null,
    createdAt: getStringField(diagnostic, ["created_at"]),
    needRetrieval:
      typeof needRetrievalValue === "boolean" ? needRetrievalValue : null,
    finalNeedRetrieval: getNullableBooleanField(diagnostic, [
      "final_need_retrieval",
      "need_retrieval",
    ]),
    llmNeedRetrieval: getNullableBooleanField(diagnostic, [
      "llm_need_retrieval",
    ]),
    rewrittenQuery: getStringField(diagnostic, ["rewritten_query"]),
    reason: getStringField(diagnostic, ["reason"]),
    llmReason: getStringField(diagnostic, ["llm_reason"]),
    overrideApplied:
      getNullableBooleanField(diagnostic, ["override_applied"]) === true,
    overrideReason: getStringField(diagnostic, ["override_reason"]),
    retrievedCount: getNumberField(diagnostic, "retrieved_count"),
    sourceCount: getNumberField(diagnostic, "source_count"),
    retrievalSources: getStringArrayField(diagnostic, "retrieval_sources"),
    vectorDegraded: diagnostic.vector_degraded === true,
    diagnostics: getRetrievalDiagnostics(diagnostic),
    sourcesPreview: getSourcesPreview(diagnostic),
  };
}

function getConversationDiagnostics(value: unknown) {
  if (typeof value !== "object" || value === null) {
    return [];
  }

  const candidate = value as Record<string, unknown>;
  const diagnostics = candidate.diagnostics;

  return Array.isArray(diagnostics)
    ? diagnostics
        .map(toMessageDiagnostic)
        .filter(
          (diagnostic): diagnostic is MessageDiagnostic => diagnostic !== null
        )
    : [];
}

function formatDiagnosticScore(value?: number | null) {
  return typeof value === "number" && Number.isFinite(value)
    ? value.toFixed(4)
    : "—";
}

function formatDiagnosticCount(value: number | null) {
  return value === null ? "—" : String(value);
}

function formatDiagnosticValue(value?: string | number | null) {
  if (typeof value === "number") {
    return Number.isFinite(value) ? String(value) : "—";
  }

  return value ? value : "—";
}

function formatDiagnosticTiming(value?: number | null) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "—";
  }

  if (value >= 1000) {
    return `${(value / 1000).toFixed(2)}s`;
  }

  return `${value.toFixed(value >= 10 ? 0 : 2)}ms`;
}

function formatRetrievalDecision(value?: boolean | null) {
  if (value === null || value === undefined) {
    return "未知";
  }

  return value ? "检索" : "不检索";
}

function toChatSource(value: unknown, index: number): ChatSource | null {
  if (typeof value === "string") {
    const normalized = value.trim();

    return normalized
      ? {
          title: `参考文档 ${index + 1}`,
          content: normalized,
          metadata: "",
        }
      : null;
  }

  if (typeof value !== "object" || value === null) {
    return null;
  }

  const source = value as Record<string, unknown>;
  const metadataRecord = getRecordField(source, "metadata");
  const sourceIndex = getOptionalNumberField(source, ["index"]);
  const chunkIndex = getOptionalNumberField(source, [
    "chunk_index",
    "chunk_id",
  ]);
  const rerankScore = getOptionalNumberField(source, [
    "rerank_score",
    "score",
  ]);
  const rrfScore = getOptionalNumberField(source, ["rrf_score"]);
  const vectorScore = getOptionalNumberField(source, ["vector_score"]);
  const fulltextScore = getOptionalNumberField(source, ["fulltext_score"]);
  const fileId =
    getStringField(source, ["file_id", "knowledge_file_id", "document_id"]) ||
    (metadataRecord
      ? getStringField(metadataRecord, [
          "file_id",
          "knowledge_file_id",
          "document_id",
        ])
      : "");
  const fileName =
    getStringField(source, [
      "file_name",
      "filename",
      "original_name",
      "document_name",
      "knowledge_file_name",
    ]) ||
    (metadataRecord
      ? getStringField(metadataRecord, [
          "file_name",
          "filename",
          "original_name",
          "document_name",
          "knowledge_file_name",
        ])
      : "");
  const fileType =
    getStringField(source, ["file_type", "type"]) ||
    (metadataRecord
      ? getStringField(metadataRecord, ["file_type", "type"])
      : "");
  const retrievalSources = getStringArrayField(source, "retrieval_sources");
  const title =
    getStringField(source, [
      "title",
      "name",
      "file_name",
      "filename",
      "original_name",
      "document_name",
      "knowledge_file_name",
      "source",
      "document",
    ]) ||
    fileName ||
    (metadataRecord
      ? getStringField(metadataRecord, [
          "title",
          "name",
          "file_name",
          "filename",
          "original_name",
          "document_name",
          "knowledge_file_name",
          "source",
          "document",
        ])
      : "") ||
    `参考文档 ${index + 1}`;
  const content =
    getStringField(source, [
      "content",
      "text",
      "chunk",
      "chunk_text",
      "snippet",
      "excerpt",
      "quote",
      "page_content",
    ]) ||
    (metadataRecord
      ? getStringField(metadataRecord, [
          "content",
          "text",
          "chunk",
          "chunk_text",
          "snippet",
          "excerpt",
          "quote",
          "page_content",
        ])
      : "");

  const metadataParts: string[] = [];
  const createdAt = source["created_at"];
  const pageNumber =
    source["page"] ??
    source["page_number"] ??
    source["page_index"] ??
    metadataRecord?.page ??
    metadataRecord?.page_number ??
    metadataRecord?.page_index;

  if (
    (typeof pageNumber === "number" && Number.isFinite(pageNumber)) ||
    (typeof pageNumber === "string" && pageNumber.trim())
  ) {
    metadataParts.push(`页码 ${pageNumber}`);
  }

  if (typeof createdAt === "string" && createdAt.trim()) {
    metadataParts.push(createdAt.trim());
  }

  if (
    retrievalSources.length > 0 &&
    !metadataParts.length
  ) {
    metadataParts.push(retrievalSources.join(" / "));
  }

  const legacyMetadata = fileId;

  const metadata =
    metadataParts.length > 0
      ? metadataParts.join(" · ")
      : legacyMetadata;

  return {
    title,
    content,
    metadata,
    ...(sourceIndex !== undefined ? { index: sourceIndex } : {}),
    ...(fileId ? { fileId } : {}),
    ...(fileName ? { fileName } : {}),
    ...(fileType ? { fileType } : {}),
    ...(chunkIndex !== undefined ? { chunkIndex } : {}),
    ...(vectorScore !== undefined ? { vectorScore } : {}),
    ...(fulltextScore !== undefined ? { fulltextScore } : {}),
    ...(rerankScore !== undefined ? { rerankScore } : {}),
    ...(rrfScore !== undefined ? { rrfScore } : {}),
    ...(retrievalSources.length > 0 ? { retrievalSources } : {}),
  };
}

function hasSourceShape(value: Record<string, unknown>) {
  return [
    "title",
    "file_name",
    "filename",
    "original_name",
    "file_id",
    "file_type",
    "knowledge_file_id",
    "document_id",
    "document_name",
    "knowledge_file_name",
    "source",
    "document",
    "index",
    "chunk_index",
    "vector_score",
    "fulltext_score",
    "rerank_score",
    "rrf_score",
    "retrieval_sources",
    "metadata",
    "content",
    "text",
    "chunk",
    "chunk_text",
    "snippet",
    "excerpt",
    "quote",
    "page_content",
  ].some((fieldName) => fieldName in value);
}

function getChatSources(value: unknown) {
  const parsedValue = typeof value === "string" ? parseJsonValue(value) : value;
  const sourceValues = Array.isArray(parsedValue)
    ? parsedValue
    : typeof parsedValue === "object" && parsedValue !== null
      ? Array.isArray((parsedValue as { sources?: unknown }).sources)
        ? (parsedValue as { sources: unknown[] }).sources
        : Array.isArray((parsedValue as { documents?: unknown }).documents)
          ? (parsedValue as { documents: unknown[] }).documents
          : Array.isArray((parsedValue as { refs?: unknown }).refs)
            ? (parsedValue as { refs: unknown[] }).refs
            : hasSourceShape(parsedValue as Record<string, unknown>)
              ? [parsedValue]
              : []
      : [];

  return sourceValues
    .map(toChatSource)
    .filter((source): source is ChatSource => source !== null);
}

function parseSseBlock(block: string) {
  let event = "message";
  const dataLines: string[] = [];

  block.split(/\r?\n/).forEach((line) => {
    if (!line || line.startsWith(":")) {
      return;
    }

    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim() || event;
      return;
    }

    if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).replace(/^ /, ""));
    }
  });

  return {
    event,
    data: dataLines.join("\n"),
  };
}

function getSseAnswerContent(data: string) {
  const parsedData = parseJsonValue(data);
  const answer = getAssistantContent(parsedData);

  return answer || (typeof parsedData === "string" ? parsedData : "");
}

function removeLegacyInitialMessage(messages: Message[]) {
  if (
    messages[0]?.role === "assistant" &&
    messages[0].content === LEGACY_INITIAL_MESSAGE
  ) {
    return messages.slice(1);
  }

  return messages;
}

function toChatSession(
  value: unknown,
  fallbackKnowledgeBaseId = ""
): ChatSession | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }

  const conversation = value as BackendConversation;

  if (typeof conversation.id !== "string" || !conversation.id.trim()) {
    return null;
  }

  const messages = Array.isArray(conversation.messages)
    ? removeLegacyInitialMessage(toMessages(conversation.messages))
    : [];
  const knowledgeBaseId =
    typeof conversation.knowledge_base_id === "string" &&
    conversation.knowledge_base_id.trim()
      ? conversation.knowledge_base_id.trim()
      : fallbackKnowledgeBaseId;

  return {
    id: conversation.id,
    knowledgeBaseId,
    title:
      typeof conversation.title === "string" && conversation.title.trim()
        ? conversation.title.trim()
        : "新对话",
    messages,
    messagesLoaded: Array.isArray(conversation.messages),
  };
}

function toKnowledgeBase(value: unknown): KnowledgeBase | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }

  const knowledgeBase = value as BackendKnowledgeBase;

  if (
    typeof knowledgeBase.id !== "string" ||
    !knowledgeBase.id.trim() ||
    typeof knowledgeBase.name !== "string" ||
    !knowledgeBase.name.trim()
  ) {
    return null;
  }

  const fileCount = Number(knowledgeBase.file_count);

  return {
    id: knowledgeBase.id,
    name: knowledgeBase.name.trim(),
    isDefault: knowledgeBase.is_default === true,
    fileCount: Number.isFinite(fileCount) ? fileCount : 0,
  };
}

function getRetrievalMode(value: unknown): RetrievalMode {
  return value === "always" || value === "never" || value === "auto"
    ? value
    : DEFAULT_RETRIEVAL_SETTINGS.retrievalMode;
}

function getBoundedNumber(
  value: Record<string, unknown>,
  fieldNames: string[],
  fallback: number,
  minValue: number,
  maxValue: number
) {
  const parsedValue = getNullableNumberField(value, fieldNames);

  if (parsedValue === null) {
    return fallback;
  }

  return Math.min(maxValue, Math.max(minValue, parsedValue));
}

function toRetrievalSettings(
  value: unknown
): KnowledgeBaseRetrievalSettings {
  if (typeof value !== "object" || value === null) {
    return DEFAULT_RETRIEVAL_SETTINGS;
  }

  const settings = value as Record<string, unknown>;

  return {
    retrievalMode: getRetrievalMode(settings.retrieval_mode),
    enableQueryRouter:
      getNullableBooleanField(settings, ["enable_query_router"]) ??
      DEFAULT_RETRIEVAL_SETTINGS.enableQueryRouter,
    enableRerank:
      getNullableBooleanField(settings, ["enable_rerank"]) ??
      DEFAULT_RETRIEVAL_SETTINGS.enableRerank,
    topK: getBoundedNumber(
      settings,
      ["top_k"],
      DEFAULT_RETRIEVAL_SETTINGS.topK,
      1,
      20
    ),
    vectorTopK: getBoundedNumber(
      settings,
      ["vector_top_k"],
      DEFAULT_RETRIEVAL_SETTINGS.vectorTopK,
      1,
      100
    ),
    fulltextTopK: getBoundedNumber(
      settings,
      ["fulltext_top_k"],
      DEFAULT_RETRIEVAL_SETTINGS.fulltextTopK,
      1,
      100
    ),
    rrfK: getBoundedNumber(
      settings,
      ["rrf_k"],
      DEFAULT_RETRIEVAL_SETTINGS.rrfK,
      1,
      100
    ),
    rerankScoreThreshold: getBoundedNumber(
      settings,
      ["rerank_score_threshold"],
      DEFAULT_RETRIEVAL_SETTINGS.rerankScoreThreshold,
      -20,
      20
    ),
  };
}

function serializeRetrievalSettings(
  settings: KnowledgeBaseRetrievalSettings
) {
  return {
    retrieval_mode: settings.retrievalMode,
    enable_query_router: settings.enableQueryRouter,
    enable_rerank: settings.enableRerank,
    top_k: settings.topK,
    vector_top_k: settings.vectorTopK,
    fulltext_top_k: settings.fulltextTopK,
    rrf_k: settings.rrfK,
    rerank_score_threshold: settings.rerankScoreThreshold,
  };
}

function toKnowledgeFile(
  value: unknown,
  sourceFile?: File
): KnowledgeFile | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }

  const knowledgeFile = value as BackendKnowledgeFile;

  if (
    typeof knowledgeFile.id !== "string" ||
    !knowledgeFile.id.trim() ||
    typeof knowledgeFile.original_name !== "string" ||
    !knowledgeFile.original_name.trim()
  ) {
    return null;
  }

  const size = Number(knowledgeFile.size_bytes);
  const usageCount = Number(knowledgeFile.usage_count);
  const status = getKnowledgeFileStatus(knowledgeFile.status);
  const latestIndexJob = toLatestIndexJob(knowledgeFile.latest_index_job);

  return {
    id: knowledgeFile.id,
    name: knowledgeFile.original_name.trim(),
    size: Number.isFinite(size) ? size : sourceFile?.size || 0,
    fingerprint: sourceFile
      ? getFileFingerprint(sourceFile)
      : knowledgeFile.id,
    status,
    latestIndexJob,
    usageCount: Number.isFinite(usageCount) ? usageCount : null,
  };
}

function toLatestIndexJob(value: unknown): LatestIndexJob | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }

  const job = value as Record<string, unknown>;
  const id = typeof job.id === "string" ? job.id : "";
  const status = getLatestIndexJobStatus(job.status);
  const userId = Number(job.user_id);
  const indexVersion = Number(job.index_version);
  const attempts = Number(job.attempts);
  const maxAttempts = Number(job.max_attempts);
  const activeSeconds = getNullableNumberField(job, ["active_seconds"]);

  return {
    id,
    userId: Number.isFinite(userId) ? userId : null,
    knowledgeFileId:
      typeof job.knowledge_file_id === "string" ? job.knowledge_file_id : "",
    knowledgeBaseId:
      typeof job.knowledge_base_id === "string" ? job.knowledge_base_id : null,
    indexVersion: Number.isFinite(indexVersion) ? indexVersion : null,
    status,
    attempts: Number.isFinite(attempts) ? attempts : null,
    maxAttempts: Number.isFinite(maxAttempts) ? maxAttempts : null,
    errorMessage:
      typeof job.error_message === "string" && job.error_message.trim()
        ? job.error_message.trim()
        : null,
    createdAt: typeof job.created_at === "string" ? job.created_at : "",
    updatedAt: typeof job.updated_at === "string" ? job.updated_at : "",
    startedAt: typeof job.started_at === "string" ? job.started_at : null,
    finishedAt: typeof job.finished_at === "string" ? job.finished_at : null,
    activeSeconds,
    isStale: job.is_stale === true,
    workerHint: getNullableStringField(job, ["worker_hint"]),
    failureType: getNullableStringField(job, ["failure_type"]),
    failureHint: getNullableStringField(job, ["failure_hint"]),
    canRetry: job.can_retry !== false,
  };
}

function getLatestIndexJobStatus(value: unknown): LatestIndexJobStatus {
  if (
    value === "queued" ||
    value === "processing" ||
    value === "completed" ||
    value === "failed"
  ) {
    return value;
  }

  return "unknown";
}

function getKnowledgeFileStatus(value: unknown): KnowledgeFileStatus {
  if (value === "queued") {
    return "queued";
  }

  if (value === "processing") {
    return "processing";
  }

  if (value === "indexed" || value === "ready") {
    return "indexed";
  }

  if (value === "failed") {
    return "failed";
  }

  return "pending";
}

function getVectorStatus(file: KnowledgeFile): VectorStatus {
  const job = file.latestIndexJob;

  if (!job) {
    return {
      label: "未向量化",
      type: "idle",
      canVectorize: true,
      canDeleteVector: false,
      canPoll: false,
    };
  }

  if (job.status === "queued") {
    return {
      label: "排队中",
      type: "pending",
      canVectorize: false,
      canDeleteVector: false,
      canPoll: true,
      ...(job.workerHint ? { workerHint: job.workerHint } : {}),
    };
  }

  if (job.status === "processing") {
    return {
      label: "处理中",
      type: "processing",
      canVectorize: false,
      canDeleteVector: false,
      canPoll: true,
      ...(job.workerHint ? { workerHint: job.workerHint } : {}),
    };
  }

  if (job.status === "completed") {
    return {
      label: "已向量化",
      type: "completed",
      canVectorize: true,
      canDeleteVector: true,
      canPoll: false,
    };
  }

  if (job.status === "failed") {
    return {
      label: "向量化失败",
      type: "failed",
      canVectorize: job.canRetry,
      canDeleteVector: false,
      canPoll: false,
      ...(job.errorMessage ? { errorMessage: job.errorMessage } : {}),
      ...(job.failureHint ? { failureHint: job.failureHint } : {}),
      canRetry: job.canRetry,
    };
  }

  return {
    label: "未知状态",
    type: "unknown",
    canVectorize: true,
    canDeleteVector: false,
    canPoll: false,
  };
}

function getWorkerStatus(value: unknown): VectorIndexHealthResponse["worker"]["status"] {
  if (
    value === "idle" ||
    value === "waiting" ||
    value === "active" ||
    value === "attention_needed"
  ) {
    return value;
  }

  return "unknown";
}

function getQueueStatus(value: unknown): VectorIndexHealthResponse["queue"]["status"] {
  if (
    value === "idle" ||
    value === "waiting" ||
    value === "processing" ||
    value === "stuck"
  ) {
    return value;
  }

  return "unknown";
}

function getQueueStatusLabel(
  status: VectorIndexHealthResponse["queue"]["status"]
) {
  if (status === "idle") {
    return "空闲";
  }

  if (status === "waiting") {
    return "等待中";
  }

  if (status === "processing") {
    return "处理中";
  }

  if (status === "stuck") {
    return "可能卡住";
  }

  return "未知";
}

function parseVectorIndexHealth(value: unknown): VectorIndexHealthResponse | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }

  const candidate = value as Record<string, unknown>;

  if (candidate.success !== true) {
    return null;
  }

  const worker = getRecordField(candidate, "worker");
  const queue = getRecordField(candidate, "queue");

  if (!worker || !queue) {
    return null;
  }

  return {
    worker: {
      status: getWorkerStatus(worker.status),
      isHealthy: worker.is_healthy === true,
      hasRecentActivity: worker.has_recent_activity === true,
      hint: getNullableStringField(worker, ["hint"]),
      lastJobUpdatedAt:
        typeof worker.last_job_updated_at === "string"
          ? worker.last_job_updated_at
          : null,
      lastProcessingHeartbeatAt:
        typeof worker.last_processing_heartbeat_at === "string"
          ? worker.last_processing_heartbeat_at
          : null,
      oldestActiveSeconds: getNullableNumberField(worker, [
        "oldest_active_seconds",
      ]),
      oldestQueuedSeconds: getNullableNumberField(worker, [
        "oldest_queued_seconds",
      ]),
      oldestProcessingSeconds: getNullableNumberField(worker, [
        "oldest_processing_seconds",
      ]),
      staleQueued: getNumberField(worker, "stale_queued"),
      staleProcessing: getNumberField(worker, "stale_processing"),
      checkedAt: typeof worker.checked_at === "string" ? worker.checked_at : "",
    },
    queue: {
      status: getQueueStatus(queue.status),
      total: getNumberField(queue, "total"),
      active: getNumberField(queue, "active"),
      queued: getNumberField(queue, "queued"),
      processing: getNumberField(queue, "processing"),
      succeeded: getNumberField(queue, "succeeded"),
      failed: getNumberField(queue, "failed"),
      cancelled: getNumberField(queue, "cancelled"),
    },
  };
}

function getWorkerHealthLabel(
  health: VectorIndexHealthResponse | null,
  errorMessage: string
): { label: string; tone: WorkerHealthTone } {
  if (errorMessage) {
    return {
      label: "任务状态暂不可用",
      tone: "muted",
    };
  }

  if (!health) {
    return {
      label: "任务状态加载中",
      tone: "muted",
    };
  }

  if (health.worker.status === "idle") {
    return {
      label: "暂无向量化任务",
      tone: "muted",
    };
  }

  if (health.worker.status === "waiting") {
    return {
      label: `任务排队中：${health.queue.queued} 个`,
      tone: "warning",
    };
  }

  if (health.worker.status === "active") {
    return {
      label: `Worker 正在处理：${health.queue.processing} 个`,
      tone: "success",
    };
  }

  if (health.worker.status === "attention_needed") {
    return {
      label: `任务可能卡住：排队 ${health.worker.staleQueued} 个，处理中 ${health.worker.staleProcessing} 个`,
      tone: "danger",
    };
  }

  return {
    label: "任务状态未知",
    tone: "muted",
  };
}

function getWorkerHealthToneClass(tone: WorkerHealthTone) {
  if (tone === "danger") {
    return "border-[#e36b4f] bg-[#fff1ed] text-[#9b3c29]";
  }

  if (tone === "warning") {
    return "border-[#d9aa2f] bg-[#fff7df] text-[#7a5a12]";
  }

  if (tone === "success") {
    return "border-[#176b62] bg-[#edf7f3] text-[#176b62]";
  }

  return "border-[#d5ded9] bg-[#f7faf8] text-[#64716d]";
}

function toVectorIndexJob(value: unknown): VectorIndexJob | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }

  const job = value as {
    id?: unknown;
    job_id?: unknown;
    status?: unknown;
    error_message?: unknown;
    failure_hint?: unknown;
  };
  const id =
    typeof job.id === "string" && job.id.trim()
      ? job.id.trim()
      : typeof job.job_id === "string" && job.job_id.trim()
        ? job.job_id.trim()
        : "";

  if (!id) {
    return null;
  }

  const status =
    job.status === "completed"
      ? "succeeded"
      : job.status === "processing" ||
          job.status === "succeeded" ||
          job.status === "failed"
        ? job.status
        : "queued";

  return {
    id,
    status,
    errorMessage:
      typeof job.error_message === "string" ? job.error_message : "",
    failureHint:
      typeof job.failure_hint === "string" ? job.failure_hint.trim() : "",
  };
}

function getVectorIndexJobs(value: unknown) {
  if (typeof value !== "object" || value === null) {
    return [];
  }

  const data = value as VectorIndexResponse;
  const candidates = [
    data.job,
    data.vector_index_job,
    data,
    ...(Array.isArray(data.jobs) ? data.jobs : []),
    ...(Array.isArray(data.vector_index_jobs) ? data.vector_index_jobs : []),
  ];

  const jobsById = new Map<string, VectorIndexJob>();

  candidates.forEach((candidate) => {
    const job = toVectorIndexJob(candidate);

    if (job) {
      jobsById.set(job.id, job);
    }
  });

  return Array.from(jobsById.values());
}

function isVectorIndexJobDone(job: VectorIndexJob) {
  return job.status === "succeeded" || job.status === "failed";
}

function getVectorIndexStatusText(status: VectorIndexJobStatus) {
  if (status === "queued") {
    return "排队中";
  }

  if (status === "processing") {
    return "处理中";
  }

  if (status === "succeeded") {
    return "已完成";
  }

  return "失败";
}

function wait(ms: number) {
  return new Promise<void>((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function waitForNextPaint() {
  return new Promise<void>((resolve) => {
    requestAnimationFrame(() => resolve());
  });
}

function renderInlineMarkdown(
  text: string,
  keyPrefix: string,
  isUserMessage: boolean
) {
  const nodes: ReactNode[] = [];
  const pattern = /(`[^`]*`|\*\*[^*]+\*\*)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let partIndex = 0;

  while ((match = pattern.exec(text))) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }

    const token = match[0];

    if (token.startsWith("`")) {
      nodes.push(
        <code
          key={`${keyPrefix}-code-${partIndex}`}
          className={`rounded px-1.5 py-0.5 font-mono text-[0.92em] ${
            isUserMessage
              ? "bg-white/15 text-white"
              : "bg-[#dfe9e5] text-[#105149]"
          }`}
        >
          {token.slice(1, -1)}
        </code>
      );
    } else {
      nodes.push(
        <strong key={`${keyPrefix}-strong-${partIndex}`} className="font-semibold">
          {token.slice(2, -2)}
        </strong>
      );
    }

    partIndex += 1;
    lastIndex = pattern.lastIndex;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes;
}

function isMarkdownBlockStart(line: string) {
  return (
    /^```/.test(line) ||
    /^#{1,6}\s+/.test(line) ||
    /^\s*\d+\.\s+/.test(line) ||
    /^\s*[-*]\s+/.test(line)
  );
}

function MarkdownContent({
  content,
  isUserMessage,
}: {
  content: string;
  isUserMessage: boolean;
}) {
  const lines = content.split("\n");
  const blocks: ReactNode[] = [];
  let index = 0;
  let blockIndex = 0;

  const inline = (text: string, suffix: string) =>
    renderInlineMarkdown(text, `md-${blockIndex}-${suffix}`, isUserMessage);

  while (index < lines.length) {
    const line = lines[index];

    if (!line.trim()) {
      index += 1;
      continue;
    }

    const codeFenceMatch = line.match(/^```(\w+)?\s*$/);

    if (codeFenceMatch) {
      const codeLines: string[] = [];
      index += 1;

      while (index < lines.length && !/^```\s*$/.test(lines[index])) {
        codeLines.push(lines[index]);
        index += 1;
      }

      if (index < lines.length) {
        index += 1;
      }

      blocks.push(
        <pre
          key={`code-${blockIndex}`}
          className={`overflow-x-auto rounded-xl px-4 py-3 text-sm ${
            isUserMessage
              ? "bg-black/25 text-white"
              : "bg-[#17201f] text-[#eef5f2]"
          }`}
        >
          <code>{codeLines.join("\n")}</code>
        </pre>
      );
      blockIndex += 1;
      continue;
    }

    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);

    if (headingMatch) {
      const level = headingMatch[1].length;
      const text = headingMatch[2];
      const headingClass =
        level <= 1
          ? "text-2xl font-semibold leading-8"
          : level === 2
            ? "text-xl font-semibold leading-8"
            : "text-lg font-semibold leading-7";

      if (level <= 1) {
        blocks.push(
          <h2 key={`heading-${blockIndex}`} className={headingClass}>
            {inline(text, "heading")}
          </h2>
        );
      } else if (level === 2) {
        blocks.push(
          <h3 key={`heading-${blockIndex}`} className={headingClass}>
            {inline(text, "heading")}
          </h3>
        );
      } else {
        blocks.push(
          <h4 key={`heading-${blockIndex}`} className={headingClass}>
            {inline(text, "heading")}
          </h4>
        );
      }

      index += 1;
      blockIndex += 1;
      continue;
    }

    const orderedMatch = line.match(/^\s*\d+\.\s+(.+)$/);

    if (orderedMatch) {
      const items: string[] = [];

      while (index < lines.length) {
        const itemMatch = lines[index].match(/^\s*\d+\.\s+(.+)$/);

        if (!itemMatch) {
          break;
        }

        const itemLines = [itemMatch[1]];
        index += 1;

        while (
          index < lines.length &&
          lines[index].trim() &&
          !isMarkdownBlockStart(lines[index])
        ) {
          itemLines.push(lines[index].trim());
          index += 1;
        }

        items.push(itemLines.join("\n"));
      }

      blocks.push(
        <ol key={`ol-${blockIndex}`} className="list-decimal space-y-2 pl-6">
          {items.map((item, itemIndex) => (
            <li
              key={`ol-${blockIndex}-${itemIndex}`}
              className="whitespace-pre-wrap pl-1"
            >
              {renderInlineMarkdown(
                item,
                `md-${blockIndex}-ol-${itemIndex}`,
                isUserMessage
              )}
            </li>
          ))}
        </ol>
      );
      blockIndex += 1;
      continue;
    }

    const unorderedMatch = line.match(/^\s*[-*]\s+(.+)$/);

    if (unorderedMatch) {
      const items: string[] = [];

      while (index < lines.length) {
        const itemMatch = lines[index].match(/^\s*[-*]\s+(.+)$/);

        if (!itemMatch) {
          break;
        }

        const itemLines = [itemMatch[1]];
        index += 1;

        while (
          index < lines.length &&
          lines[index].trim() &&
          !isMarkdownBlockStart(lines[index])
        ) {
          itemLines.push(lines[index].trim());
          index += 1;
        }

        items.push(itemLines.join("\n"));
      }

      blocks.push(
        <ul key={`ul-${blockIndex}`} className="list-disc space-y-2 pl-6">
          {items.map((item, itemIndex) => (
            <li
              key={`ul-${blockIndex}-${itemIndex}`}
              className="whitespace-pre-wrap pl-1"
            >
              {renderInlineMarkdown(
                item,
                `md-${blockIndex}-ul-${itemIndex}`,
                isUserMessage
              )}
            </li>
          ))}
        </ul>
      );
      blockIndex += 1;
      continue;
    }

    const paragraphLines: string[] = [];

    while (
      index < lines.length &&
      lines[index].trim() &&
      !isMarkdownBlockStart(lines[index])
    ) {
      paragraphLines.push(lines[index]);
      index += 1;
    }

    blocks.push(
      <p key={`p-${blockIndex}`} className="whitespace-pre-wrap">
        {inline(paragraphLines.join("\n"), "paragraph")}
      </p>
    );
    blockIndex += 1;
  }

  return <div className="space-y-3 leading-7 break-words">{blocks}</div>;
}

export default function Home() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState("");
  const [input, setInput] = useState("");
  const [editingSessionId, setEditingSessionId] = useState("");
  const [editingTitle, setEditingTitle] = useState("");
  const [renamingSessionId, setRenamingSessionId] = useState("");
  const [deletingSessionId, setDeletingSessionId] = useState("");
  const [copiedMessageKey, setCopiedMessageKey] = useState("");
  const [loadingSessions, setLoadingSessions] = useState<Record<string, boolean>>(
    {}
  );
  const [sessionErrors, setSessionErrors] = useState<Record<string, string>>({});
  const [conversationDiagnostics, setConversationDiagnostics] = useState<
    Record<string, MessageDiagnostic[]>
  >({});
  const [expandedDiagnosticPanels, setExpandedDiagnosticPanels] = useState<
    Record<string, boolean>
  >({});
  const [loadingDiagnostics, setLoadingDiagnostics] = useState<
    Record<string, boolean>
  >({});
  const [diagnosticErrors, setDiagnosticErrors] = useState<
    Record<string, string>
  >({});
  const [hasCheckedAuth, setHasCheckedAuth] = useState(false);
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const [isCreatingKnowledgeBase, setIsCreatingKnowledgeBase] =
    useState(false);
  const [isUploadingKnowledgeFiles, setIsUploadingKnowledgeFiles] =
    useState(false);
  const [knowledgeFileUploadError, setKnowledgeFileUploadError] =
    useState("");
  const [detachingKnowledgeFileId, setDetachingKnowledgeFileId] =
    useState("");
  const [knowledgeFileDetachError, setKnowledgeFileDetachError] =
    useState("");
  const [attachingKnowledgeFileId, setAttachingKnowledgeFileId] =
    useState("");
  const [deletingVectorFileId, setDeletingVectorFileId] = useState("");
  const [knowledgeFileAttachError, setKnowledgeFileAttachError] =
    useState("");
  const [isLoadingKnowledgeFiles, setIsLoadingKnowledgeFiles] =
    useState(false);
  const [knowledgeFileLoadError, setKnowledgeFileLoadError] = useState("");
  const [isLoadingReusableFiles, setIsLoadingReusableFiles] =
    useState(false);
  const [reusableFileLoadError, setReusableFileLoadError] = useState("");
  const [vectorIndexingFileIds, setVectorIndexingFileIds] = useState<
    Record<string, boolean>
  >({});
  const [vectorIndexQueue, setVectorIndexQueue] = useState<
    VectorIndexQueueItem[]
  >([]);
  const [isIndexingKnowledgeBase, setIsIndexingKnowledgeBase] =
    useState(false);
  const [vectorIndexMessage, setVectorIndexMessage] = useState("");
  const [vectorIndexError, setVectorIndexError] = useState("");
  const [vectorIndexHealth, setVectorIndexHealth] =
    useState<VectorIndexHealthResponse | null>(null);
  const [vectorIndexHealthError, setVectorIndexHealthError] = useState("");
  const [isLoadingVectorIndexHealth, setIsLoadingVectorIndexHealth] =
    useState(false);
  const [pageError, setPageError] = useState("");
  const [currentUsername, setCurrentUsername] = useState("");
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([
    {
      id: DEFAULT_KNOWLEDGE_BASE_ID,
      name: "默认知识库",
      isDefault: true,
      fileCount: 0,
    },
  ]);
  const [selectedKnowledgeBaseId, setSelectedKnowledgeBaseId] = useState(
    DEFAULT_KNOWLEDGE_BASE_ID
  );
  const [knowledgeFiles, setKnowledgeFiles] = useState<KnowledgeFile[]>([]);
  const [knowledgeBaseFiles, setKnowledgeBaseFiles] = useState<
    KnowledgeBaseFile[]
  >([]);
  const [
    retrievalSettingsByKnowledgeBaseId,
    setRetrievalSettingsByKnowledgeBaseId,
  ] = useState<Record<string, KnowledgeBaseRetrievalSettings>>({});
  const [isLoadingRetrievalSettings, setIsLoadingRetrievalSettings] =
    useState(false);
  const [isSavingRetrievalSettings, setIsSavingRetrievalSettings] =
    useState(false);
  const [retrievalSettingsMessage, setRetrievalSettingsMessage] =
    useState("");
  const [retrievalSettingsError, setRetrievalSettingsError] = useState("");
  const [isKnowledgeBaseManagerOpen, setIsKnowledgeBaseManagerOpen] =
    useState(false);
  const [isFileManagerOpen, setIsFileManagerOpen] = useState(false);
  const [newKnowledgeBaseName, setNewKnowledgeBaseName] = useState("");

  const bottomRef = useRef<HTMLDivElement | null>(null);
  const messagesContainerRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const previousSessionIdRef = useRef("");
  const previousMessageCountRef = useRef(0);
  const previousLoadingRef = useRef(false);

  const visibleSessions = sessions.filter(
    (session) => session.knowledgeBaseId === selectedKnowledgeBaseId
  );
  const currentSession =
    visibleSessions.find((session) => session.id === currentSessionId) ||
    visibleSessions[0] ||
    null;
  const currentSessionMessageId = currentSession?.id || "";
  const areCurrentSessionMessagesLoaded =
    currentSession?.messagesLoaded ?? true;
  const isCurrentSessionLoading = currentSession
    ? Boolean(loadingSessions[currentSession.id])
    : false;
  const currentSessionError = currentSession
    ? sessionErrors[currentSession.id] || ""
    : "";
  const currentSessionLastMessage = currentSession
    ? currentSession.messages[currentSession.messages.length - 1]
    : null;
  const shouldShowThinkingIndicator =
    isCurrentSessionLoading && currentSessionLastMessage?.role !== "assistant";
  const selectedKnowledgeBase =
    knowledgeBases.find(
      (knowledgeBase) => knowledgeBase.id === selectedKnowledgeBaseId
    ) || knowledgeBases[0];
  const selectedRetrievalSettings =
    retrievalSettingsByKnowledgeBaseId[selectedKnowledgeBaseId] ||
    DEFAULT_RETRIEVAL_SETTINGS;
  const selectedKnowledgeFileIds = new Set(
    knowledgeBaseFiles
      .filter(
        (association) =>
          association.knowledgeBaseId === selectedKnowledgeBaseId
      )
      .map((association) => association.knowledgeFileId)
  );
  const selectedKnowledgeFiles = knowledgeFiles.filter((file) =>
    selectedKnowledgeFileIds.has(file.id)
  );
  const reusableKnowledgeFiles = knowledgeFiles.filter(
    (file) => !selectedKnowledgeFileIds.has(file.id)
  );
  const hasPollingIndexJobs = knowledgeFiles.some(
    (file) => getVectorStatus(file).canPoll
  );
  const selectedKnowledgeBaseFileCount =
    selectedKnowledgeFiles.length || selectedKnowledgeBase?.fileCount || 0;
  const workerHealthLabel = getWorkerHealthLabel(
    vectorIndexHealth,
    vectorIndexHealthError
  );
  const vectorQueueCount = vectorIndexHealth?.queue.total ?? vectorIndexQueue.length;

  const loadKnowledgeBaseFiles = useCallback(
    async (knowledgeBaseId: string, options?: { showLoading?: boolean }) => {
      if (!knowledgeBaseId || knowledgeBaseId === DEFAULT_KNOWLEDGE_BASE_ID) {
        return;
      }

      const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

      if (!authState) {
        localStorage.removeItem(AUTH_STORAGE_KEY);
        window.location.href = "/login";
        return;
      }

      const shouldShowLoading = options?.showLoading !== false;

      if (shouldShowLoading) {
        setIsLoadingKnowledgeFiles(true);
      }

      setKnowledgeFileLoadError("");

      try {
        const response = await fetch(
          `/api/chat/knowledge-base/${encodeURIComponent(
            knowledgeBaseId
          )}/files`,
          {
            method: "GET",
            headers: {
              Authorization: buildAuthorizationHeader(authState),
            },
            cache: "no-store",
          }
        );

        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(
            getResponseErrorMessage(
              errorText,
              "读取知识库文件失败，请稍后再试。",
              response.status
            )
          );
        }

        const data = (await response.json()) as ListKnowledgeFilesResponse;
        const fileValues = Array.isArray(data.files) ? data.files : [];
        const loadedFiles = fileValues
          .map((value) => toKnowledgeFile(value))
          .filter(
            (knowledgeFile): knowledgeFile is KnowledgeFile =>
              knowledgeFile !== null
          );
        const loadedFileIds = new Set(loadedFiles.map((file) => file.id));

        setKnowledgeFiles((prev) => {
          const previousFilesById = new Map(
            prev.map((file) => [file.id, file])
          );
          const mergedLoadedFiles = loadedFiles.map((file) => ({
            ...file,
            usageCount:
              file.usageCount ??
              previousFilesById.get(file.id)?.usageCount ??
              null,
          }));

          return [
            ...mergedLoadedFiles,
            ...prev.filter((file) => !loadedFileIds.has(file.id)),
          ];
        });
        setKnowledgeBaseFiles((prev) => [
          ...prev.filter(
            (association) =>
              association.knowledgeBaseId !== knowledgeBaseId
          ),
          ...loadedFiles.map((file) => ({
            knowledgeBaseId,
            knowledgeFileId: file.id,
          })),
        ]);
        setKnowledgeBases((prev) =>
          prev.map((knowledgeBase) =>
            knowledgeBase.id === knowledgeBaseId
              ? {
                  ...knowledgeBase,
                  fileCount: loadedFiles.length,
                }
              : knowledgeBase
          )
        );
      } catch (error) {
        setKnowledgeFileLoadError(
          error instanceof Error
            ? error.message
            : "读取知识库文件失败，请稍后再试。"
        );
      } finally {
        if (shouldShowLoading) {
          setIsLoadingKnowledgeFiles(false);
        }
      }
    },
    []
  );

  const loadAllKnowledgeFiles = useCallback(async (options?: { showLoading?: boolean }) => {
    const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

    if (!authState) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      window.location.href = "/login";
      return;
    }

    const shouldShowLoading = options?.showLoading !== false;

    if (shouldShowLoading) {
      setIsLoadingReusableFiles(true);
    }

    setReusableFileLoadError("");

    try {
      const response = await fetch("/api/chat/knowledge-files", {
        method: "GET",
        headers: {
          Authorization: buildAuthorizationHeader(authState),
        },
        cache: "no-store",
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(
          getResponseErrorMessage(
            errorText,
            "读取用户文件列表失败，请稍后再试。",
            response.status
          )
        );
      }

      const data = (await response.json()) as ListKnowledgeFilesResponse;
      const fileValues = Array.isArray(data.files) ? data.files : [];
      const loadedFiles = fileValues
        .map((value) => toKnowledgeFile(value))
        .filter(
          (knowledgeFile): knowledgeFile is KnowledgeFile =>
            knowledgeFile !== null
        );

      setKnowledgeFiles(loadedFiles);
    } catch (error) {
      setReusableFileLoadError(
        error instanceof Error
          ? error.message
          : "读取用户文件列表失败，请稍后再试。"
      );
    } finally {
      if (shouldShowLoading) {
        setIsLoadingReusableFiles(false);
      }
    }
  }, []);

  const loadVectorIndexHealth = useCallback(
    async (options?: { showLoading?: boolean }) => {
      const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

      if (!authState) {
        localStorage.removeItem(AUTH_STORAGE_KEY);
        window.location.href = "/login";
        return;
      }

      const shouldShowLoading = options?.showLoading !== false;

      if (shouldShowLoading) {
        setIsLoadingVectorIndexHealth(true);
      }

      try {
        const response = await fetch("/api/chat/vector-index-jobs/health", {
          method: "GET",
          headers: {
            Authorization: buildAuthorizationHeader(authState),
          },
          cache: "no-store",
        });
        const data = (await response.json().catch(() => null)) as unknown;

        if (!response.ok) {
          throw new Error(
            getResponseErrorMessage(
              JSON.stringify(data),
              "任务状态暂不可用",
              response.status
            )
          );
        }

        const health = parseVectorIndexHealth(data);

        if (!health) {
          throw new Error("任务状态暂不可用");
        }

        setVectorIndexHealth(health);
        setVectorIndexHealthError("");
      } catch {
        setVectorIndexHealth(null);
        setVectorIndexHealthError("任务状态暂不可用");
      } finally {
        if (shouldShowLoading) {
          setIsLoadingVectorIndexHealth(false);
        }
      }
    },
    []
  );

  async function handleOpenFileManager() {
    setIsFileManagerOpen(true);
    await Promise.all([
      loadKnowledgeBaseFiles(selectedKnowledgeBaseId),
      loadAllKnowledgeFiles(),
      loadVectorIndexHealth(),
    ]);
  }

  async function handleCreateKnowledgeBase() {
    const normalizedName = newKnowledgeBaseName.trim();

    if (!normalizedName || isCreatingKnowledgeBase) {
      return;
    }

    const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

    if (!authState) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      window.location.href = "/login";
      return;
    }

    setIsCreatingKnowledgeBase(true);
    setPageError("");

    try {
      const response = await fetch("/api/chat/knowledge-base", {
        method: "POST",
        headers: {
          Authorization: buildAuthorizationHeader(authState),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: normalizedName,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(
          getResponseErrorMessage(
            errorText,
            "创建知识库失败，请稍后再试。",
            response.status
          )
        );
      }

      const data = (await response.json()) as CreateKnowledgeBaseResponse;
      const knowledgeBase = toKnowledgeBase(data.knowledge_base);

      if (!knowledgeBase) {
        throw new Error("创建知识库响应缺少有效的 knowledge_base。");
      }

      setKnowledgeBases((prev) => [
        ...prev.filter((candidate) => candidate.id !== knowledgeBase.id),
        knowledgeBase,
      ]);
      setSelectedKnowledgeBaseId(knowledgeBase.id);
      setNewKnowledgeBaseName("");
    } catch (error) {
      setPageError(
        error instanceof Error
          ? error.message
          : "创建知识库失败，请稍后再试。"
      );
    } finally {
      setIsCreatingKnowledgeBase(false);
    }
  }

  function updateSelectedRetrievalSettings(
    patch: Partial<KnowledgeBaseRetrievalSettings>
  ) {
    if (!selectedKnowledgeBaseId) {
      return;
    }

    setRetrievalSettingsByKnowledgeBaseId((prev) => ({
      ...prev,
      [selectedKnowledgeBaseId]: {
        ...(prev[selectedKnowledgeBaseId] || DEFAULT_RETRIEVAL_SETTINGS),
        ...patch,
      },
    }));
    setRetrievalSettingsMessage("");
    setRetrievalSettingsError("");
  }

  async function loadRetrievalSettings(knowledgeBaseId: string) {
    if (!knowledgeBaseId || knowledgeBaseId === DEFAULT_KNOWLEDGE_BASE_ID) {
      return;
    }

    const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

    if (!authState) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      window.location.href = "/login";
      return;
    }

    setIsLoadingRetrievalSettings(true);
    setRetrievalSettingsError("");

    try {
      const response = await fetch(
        `/api/chat/knowledge-base/${encodeURIComponent(
          knowledgeBaseId
        )}/retrieval-settings`,
        {
          method: "GET",
          headers: {
            Authorization: buildAuthorizationHeader(authState),
          },
          cache: "no-store",
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(
          getResponseErrorMessage(
            errorText,
            "读取检索设置失败，请稍后再试。",
            response.status
          )
        );
      }

      const data = (await response.json()) as RetrievalSettingsResponse;
      const settings = toRetrievalSettings(data.settings);

      setRetrievalSettingsByKnowledgeBaseId((prev) => ({
        ...prev,
        [knowledgeBaseId]: settings,
      }));
    } catch (error) {
      setRetrievalSettingsError(
        error instanceof Error
          ? error.message
          : "读取检索设置失败，请稍后再试。"
      );
    } finally {
      setIsLoadingRetrievalSettings(false);
    }
  }

  async function handleSaveRetrievalSettings() {
    if (
      !selectedKnowledgeBaseId ||
      selectedKnowledgeBaseId === DEFAULT_KNOWLEDGE_BASE_ID ||
      isSavingRetrievalSettings
    ) {
      return;
    }

    const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

    if (!authState) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      window.location.href = "/login";
      return;
    }

    setIsSavingRetrievalSettings(true);
    setRetrievalSettingsMessage("");
    setRetrievalSettingsError("");

    try {
      const response = await fetch(
        `/api/chat/knowledge-base/${encodeURIComponent(
          selectedKnowledgeBaseId
        )}/retrieval-settings`,
        {
          method: "PATCH",
          headers: {
            Authorization: buildAuthorizationHeader(authState),
            "Content-Type": "application/json",
          },
          body: JSON.stringify(
            serializeRetrievalSettings(selectedRetrievalSettings)
          ),
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(
          getResponseErrorMessage(
            errorText,
            "保存检索设置失败，请稍后再试。",
            response.status
          )
        );
      }

      const data = (await response.json()) as RetrievalSettingsResponse;
      const settings = toRetrievalSettings(data.settings);

      setRetrievalSettingsByKnowledgeBaseId((prev) => ({
        ...prev,
        [selectedKnowledgeBaseId]: settings,
      }));
      setRetrievalSettingsMessage("检索设置已保存，下一次提问生效。");
    } catch (error) {
      setRetrievalSettingsError(
        error instanceof Error
          ? error.message
          : "保存检索设置失败，请稍后再试。"
      );
    } finally {
      setIsSavingRetrievalSettings(false);
    }
  }

  async function handleSelectFiles(files: FileList | null) {
    if (
      !files?.length ||
      !selectedKnowledgeBaseId ||
      isUploadingKnowledgeFiles
    ) {
      return;
    }

    const MAX_FILE_SIZE = 200 * 1024 * 1024;
    const selectedFiles = Array.from(files);
    const oversizedFiles = selectedFiles.filter(
      (file) => file.size > MAX_FILE_SIZE
    );

    if (oversizedFiles.length > 0) {
      const names = oversizedFiles
        .map((file) => file.name)
        .join("、");
      setKnowledgeFileUploadError(
        `以下文件超过 200MB 限制，请压缩后重新上传：${names}。`
      );
      return;
    }

    const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

    if (!authState) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      window.location.href = "/login";
      return;
    }

    const formData = new FormData();
    selectedFiles.forEach((file) => formData.append("files", file));
    formData.append("description", "");
    formData.append("auto_index", "false");

    setIsUploadingKnowledgeFiles(true);
    setKnowledgeFileUploadError("");
    setIsFileManagerOpen(true);

    try {
      const response = await fetch(
        `/api/chat/knowledge-base/${encodeURIComponent(
          selectedKnowledgeBaseId
        )}/files`,
        {
          method: "POST",
          headers: {
            Authorization: buildAuthorizationHeader(authState),
          },
          body: formData,
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(
          getResponseErrorMessage(
            errorText,
            "上传文件失败，请稍后再试。",
            response.status
          )
        );
      }

      const data = (await response.json()) as UploadKnowledgeFilesResponse;
      const uploadedValues = Array.isArray(data.files) ? data.files : [];
      const uploadedFiles = uploadedValues
        .map((value, index) => toKnowledgeFile(value, selectedFiles[index]))
        .filter(
          (knowledgeFile): knowledgeFile is KnowledgeFile =>
            knowledgeFile !== null
        );

      if (uploadedFiles.length === 0) {
        throw new Error("上传响应缺少有效的 files 数据。");
      }

      await Promise.all([
        loadKnowledgeBaseFiles(selectedKnowledgeBaseId),
        loadAllKnowledgeFiles(),
      ]);
    } catch (error) {
      setKnowledgeFileUploadError(
        error instanceof Error
          ? error.message
          : "上传文件失败，请稍后再试。"
      );
    } finally {
      setIsUploadingKnowledgeFiles(false);

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  async function handleAttachKnowledgeFile(fileId: string) {
    if (
      !selectedKnowledgeBaseId ||
      !fileId ||
      attachingKnowledgeFileId
    ) {
      return;
    }

    const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

    if (!authState) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      window.location.href = "/login";
      return;
    }

    setAttachingKnowledgeFileId(fileId);
    setKnowledgeFileAttachError("");

    try {
      const response = await fetch(
        `/api/chat/knowledge-base/${encodeURIComponent(
          selectedKnowledgeBaseId
        )}/files/${encodeURIComponent(fileId)}`,
        {
          method: "POST",
          headers: {
            Authorization: buildAuthorizationHeader(authState),
          },
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(
          getResponseErrorMessage(
            errorText,
            "添加文件关联失败，请稍后再试。",
            response.status
          )
        );
      }

      await Promise.all([
        loadKnowledgeBaseFiles(selectedKnowledgeBaseId),
        loadAllKnowledgeFiles(),
      ]);
    } catch (error) {
      setKnowledgeFileAttachError(
        error instanceof Error
          ? error.message
          : "添加文件关联失败，请稍后再试。"
      );
    } finally {
      setAttachingKnowledgeFileId("");
    }
  }

  async function handleRemoveKnowledgeFile(fileId: string) {
    if (
      !selectedKnowledgeBaseId ||
      !fileId ||
      detachingKnowledgeFileId
    ) {
      return;
    }

    const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

    if (!authState) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      window.location.href = "/login";
      return;
    }

    setDetachingKnowledgeFileId(fileId);
    setKnowledgeFileDetachError("");

    try {
      const response = await fetch(
        `/api/chat/knowledge-base/${encodeURIComponent(
          selectedKnowledgeBaseId
        )}/files/${encodeURIComponent(fileId)}`,
        {
          method: "DELETE",
          headers: {
            Authorization: buildAuthorizationHeader(authState),
          },
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(
          getResponseErrorMessage(
            errorText,
            "解除文件关联失败，请稍后再试。",
            response.status
          )
        );
      }

      await Promise.all([
        loadKnowledgeBaseFiles(selectedKnowledgeBaseId),
        loadAllKnowledgeFiles(),
      ]);
    } catch (error) {
      setKnowledgeFileDetachError(
        error instanceof Error
          ? error.message
          : "解除文件关联失败，请稍后再试。"
      );
    } finally {
      setDetachingKnowledgeFileId("");
    }
  }

  async function loadVectorIndexJob(
    jobId: string,
    authState: NonNullable<ReturnType<typeof parseAuthState>>
  ) {
    const response = await fetch(
      `/api/chat/vector-index-jobs/${encodeURIComponent(jobId)}`,
      {
        method: "GET",
        headers: {
          Authorization: buildAuthorizationHeader(authState),
        },
        cache: "no-store",
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(
        getResponseErrorMessage(
          errorText,
          "查询向量化任务失败，请稍后再试。",
          response.status
        )
      );
    }

    const data = (await response.json()) as VectorIndexResponse;
    return getVectorIndexJobs(data)[0] || null;
  }

  function updateVectorIndexQueue(
    jobs: VectorIndexJob[],
    target: Pick<VectorIndexQueueItem, "targetName" | "targetType">
  ) {
    if (jobs.length === 0) {
      return;
    }

    setVectorIndexQueue((prev) => {
      const nextJobs = new Map<string, VectorIndexQueueItem>(
        prev.map((job) => [job.id, job])
      );

      jobs.forEach((job) => {
        const previousJob = nextJobs.get(job.id);

        nextJobs.set(job.id, {
          ...(previousJob || {}),
          ...job,
          targetName: previousJob?.targetName || target.targetName,
          targetType: previousJob?.targetType || target.targetType,
        });
      });

      return Array.from(nextJobs.values());
    });
  }

  async function waitForVectorIndexJobs(
    jobs: VectorIndexJob[],
    authState: NonNullable<ReturnType<typeof parseAuthState>>,
    onJobsUpdated?: (jobs: VectorIndexJob[]) => void
  ) {
    if (jobs.length === 0) {
      return [];
    }

    let latestJobs = jobs;
    onJobsUpdated?.(latestJobs);

    for (let attempt = 0; attempt < 45; attempt += 1) {
      if (latestJobs.every(isVectorIndexJobDone)) {
        return latestJobs;
      }

      await wait(2000);

      const nextJobs = await Promise.all(
        latestJobs.map(async (job) => {
          if (isVectorIndexJobDone(job)) {
            return job;
          }

          return (await loadVectorIndexJob(job.id, authState)) || job;
        })
      );

      latestJobs = nextJobs;
      onJobsUpdated?.(latestJobs);
    }

    return latestJobs;
  }

  async function refreshKnowledgeFiles(options?: { showLoading?: boolean }) {
    await Promise.all([
      loadKnowledgeBaseFiles(selectedKnowledgeBaseId, options),
      loadAllKnowledgeFiles(options),
    ]);
  }

  async function handleIndexKnowledgeFile(fileId: string) {
    if (!fileId || vectorIndexingFileIds[fileId]) {
      return;
    }

    const targetFile = knowledgeFiles.find((file) => file.id === fileId);
    const target = {
      targetName: targetFile?.name || "知识库文件",
      targetType: "file" as const,
    };
    const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

    if (!authState) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      window.location.href = "/login";
      return;
    }

    setVectorIndexingFileIds((prev) => ({ ...prev, [fileId]: true }));
    setVectorIndexError("");
    setVectorIndexMessage("");

    try {
      const response = await fetch(
        `/api/chat/knowledge-files/${encodeURIComponent(fileId)}/vectors`,
        {
          method: "POST",
          headers: {
            Authorization: buildAuthorizationHeader(authState),
          },
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(
          getResponseErrorMessage(
            errorText,
            "提交文件向量化失败，请稍后再试。",
            response.status
          )
        );
      }

      const data = (await response.json()) as VectorIndexResponse;
      const jobs = getVectorIndexJobs(data);
      updateVectorIndexQueue(jobs, target);

      setVectorIndexMessage("文件向量化任务已提交。");
      await refreshKnowledgeFiles();
    } catch (error) {
      setVectorIndexError(
        error instanceof Error ? error.message : "文件向量化失败，请稍后再试。"
      );
    } finally {
      setVectorIndexingFileIds((prev) => {
        const next = { ...prev };
        delete next[fileId];
        return next;
      });
    }
  }

  async function handleDeleteKnowledgeFileVectors(fileId: string) {
    if (!fileId || deletingVectorFileId) {
      return;
    }

    const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

    if (!authState) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      window.location.href = "/login";
      return;
    }

    setDeletingVectorFileId(fileId);
    setVectorIndexError("");
    setVectorIndexMessage("");

    try {
      const response = await fetch(
        `/api/chat/knowledge-files/${encodeURIComponent(fileId)}/vectors`,
        {
          method: "DELETE",
          headers: {
            Authorization: buildAuthorizationHeader(authState),
          },
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(
          getResponseErrorMessage(
            errorText,
            "删除文件向量失败，请稍后再试。",
            response.status
          )
        );
      }

      setVectorIndexMessage("文件向量已删除，可重新向量化。");
      await refreshKnowledgeFiles();
    } catch (error) {
      setVectorIndexError(
        error instanceof Error
          ? error.message
          : "删除文件向量失败，请稍后再试。"
      );
    } finally {
      setDeletingVectorFileId("");
    }
  }

  async function handleIndexKnowledgeBase() {
    if (
      !selectedKnowledgeBaseId ||
      selectedKnowledgeBaseId === DEFAULT_KNOWLEDGE_BASE_ID ||
      isIndexingKnowledgeBase
    ) {
      return;
    }

    const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

    if (!authState) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      window.location.href = "/login";
      return;
    }

    setIsIndexingKnowledgeBase(true);
    setVectorIndexError("");
    setVectorIndexMessage("");

    try {
      const target = {
        targetName: selectedKnowledgeBase?.name || "当前知识库",
        targetType: "knowledge-base" as const,
      };
      const response = await fetch(
        `/api/chat/knowledge-base/${encodeURIComponent(
          selectedKnowledgeBaseId
        )}/vectors`,
        {
          method: "POST",
          headers: {
            Authorization: buildAuthorizationHeader(authState),
          },
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(
          getResponseErrorMessage(
            errorText,
            "提交知识库向量化失败，请稍后再试。",
            response.status
          )
        );
      }

      const data = (await response.json()) as VectorIndexResponse;
      const jobs = getVectorIndexJobs(data);
      updateVectorIndexQueue(jobs, target);

      setVectorIndexMessage("知识库向量化任务已提交。");

      const finishedJobs = await waitForVectorIndexJobs(
        jobs,
        authState,
        (latestJobs) => updateVectorIndexQueue(latestJobs, target)
      );
      const failedJob = finishedJobs.find((job) => job.status === "failed");

      if (failedJob) {
        throw new Error(failedJob.errorMessage || "知识库向量化失败。");
      }

      if (finishedJobs.length > 0) {
        setVectorIndexMessage("知识库向量化完成。");
      }

      await refreshKnowledgeFiles();
    } catch (error) {
      setVectorIndexError(
        error instanceof Error ? error.message : "知识库向量化失败，请稍后再试。"
      );
    } finally {
      setIsIndexingKnowledgeBase(false);
    }
  }

  async function createBackendSession(
    knowledgeBaseId: string,
    title = "新对话"
  ) {
    const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

    if (!authState) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      window.location.href = "/login";
      throw new Error("登录已失效，请重新登录。");
    }

    const response = await fetch(
      `/api/chat/knowledge-bases/${encodeURIComponent(
        knowledgeBaseId
      )}/conversations`,
      {
        method: "POST",
        headers: {
          Authorization: buildAuthorizationHeader(authState),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ title }),
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(
        getResponseErrorMessage(
          errorText,
          "创建对话失败，请稍后再试。",
          response.status
        )
      );
    }

    const data = (await response.json()) as CreateConversationResponse;
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
    };
  }

  async function loadBackendMessages(conversationId: string) {
    const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

    if (!authState) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      window.location.href = "/login";
      throw new Error("登录已失效，请重新登录。");
    }

    const response = await fetch(
      `/api/chat/conversations/${encodeURIComponent(conversationId)}/messages`,
      {
        method: "GET",
        headers: {
          Authorization: buildAuthorizationHeader(authState),
        },
        cache: "no-store",
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(
        getResponseErrorMessage(
          errorText,
          "读取会话消息失败，请稍后再试。",
          response.status
        )
      );
    }

    const data = (await response.json()) as ListMessagesResponse;
    return Array.isArray(data.messages)
      ? removeLegacyInitialMessage(toMessages(data.messages))
      : [];
  }

  async function handleSelectSession(session: ChatSession) {
    setCurrentSessionId(session.id);

    if (session.messagesLoaded) {
      return;
    }

    setSessionErrors((prev) => ({ ...prev, [session.id]: "" }));

    try {
      const messages = await loadBackendMessages(session.id);
      setSessions((prev) =>
        prev.map((candidate) =>
          candidate.id === session.id
            ? { ...candidate, messages, messagesLoaded: true }
            : candidate
        )
      );
    } catch (error) {
      setSessionErrors((prev) => ({
        ...prev,
        [session.id]:
          error instanceof Error
            ? error.message
            : "读取会话消息失败，请稍后再试。",
      }));
    }
  }

  async function loadBackendKnowledgeBases() {
    const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

    if (!authState) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      window.location.href = "/login";
      throw new Error("登录已失效，请重新登录。");
    }

    const response = await fetch("/api/chat/knowledge-bases", {
      method: "GET",
      headers: {
        Authorization: buildAuthorizationHeader(authState),
      },
      cache: "no-store",
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(
        getResponseErrorMessage(
          errorText,
          "读取知识库列表失败，请稍后再试。",
          response.status
        )
      );
    }

    const data = (await response.json()) as ListKnowledgeBasesResponse;
    const knowledgeBaseValues = Array.isArray(data.knowledge_bases)
      ? data.knowledge_bases
      : [];

    const nextKnowledgeBases: KnowledgeBase[] = [];
    const sessionMap = new Map<string, ChatSession>();

    for (const value of knowledgeBaseValues) {
      const knowledgeBase = toKnowledgeBase(value);

      if (!knowledgeBase) {
        continue;
      }

      nextKnowledgeBases.push(knowledgeBase);

      const backendKnowledgeBase = value as BackendKnowledgeBase;
      const conversations = Array.isArray(
        backendKnowledgeBase.conversations
      )
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
      knowledgeBases: nextKnowledgeBases,
      sessions: Array.from(sessionMap.values()),
    };
  }

  useEffect(() => {
    try {
      const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

      if (!authState) {
        localStorage.removeItem(AUTH_STORAGE_KEY);
        window.location.href = "/login";
        return;
      }

      setCurrentUsername(getAuthUsername(authState));
    } catch (error) {
      console.error("Failed to read auth state:", error);
      window.location.href = "/login";
      return;
    }

    setHasCheckedAuth(true);
  }, []);

  useEffect(() => {
    if (!hasCheckedAuth || !selectedKnowledgeBaseId) {
      return;
    }

    void loadKnowledgeBaseFiles(selectedKnowledgeBaseId);
  }, [
    hasCheckedAuth,
    loadKnowledgeBaseFiles,
    selectedKnowledgeBaseId,
  ]);

  useEffect(() => {
    if (
      !hasCheckedAuth ||
      !isKnowledgeBaseManagerOpen ||
      !selectedKnowledgeBaseId ||
      selectedKnowledgeBaseId === DEFAULT_KNOWLEDGE_BASE_ID
    ) {
      return;
    }

    void loadRetrievalSettings(selectedKnowledgeBaseId);
  }, [
    hasCheckedAuth,
    isKnowledgeBaseManagerOpen,
    selectedKnowledgeBaseId,
  ]);

  useEffect(() => {
    if (!hasCheckedAuth || !hasPollingIndexJobs) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void Promise.all([
        loadKnowledgeBaseFiles(selectedKnowledgeBaseId, {
          showLoading: false,
        }),
        loadAllKnowledgeFiles({ showLoading: false }),
        loadVectorIndexHealth({ showLoading: false }),
      ]);
    }, 2500);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [
    hasCheckedAuth,
    hasPollingIndexJobs,
    loadAllKnowledgeFiles,
    loadKnowledgeBaseFiles,
    loadVectorIndexHealth,
    selectedKnowledgeBaseId,
  ]);

  useEffect(() => {
    let isCancelled = false;

    async function restoreKnowledgeBases() {
      try {
        const {
          knowledgeBases: nextKnowledgeBases,
          sessions: nextSessions,
        } = await loadBackendKnowledgeBases();

        if (isCancelled) {
          return;
        }

        const defaultKnowledgeBaseId =
          nextKnowledgeBases.find(
            (knowledgeBase) => knowledgeBase.isDefault
          )?.id ||
          nextKnowledgeBases[0]?.id ||
          "";

        setKnowledgeBases(nextKnowledgeBases);
        setSessions(nextSessions);
        setSelectedKnowledgeBaseId(defaultKnowledgeBaseId);
        setCurrentSessionId(
          nextSessions.find(
            (session) =>
              session.knowledgeBaseId === defaultKnowledgeBaseId
          )?.id || ""
        );
        setPageError("");
      } catch (error) {
        console.error("Failed to load knowledge bases:", error);

        if (!isCancelled) {
          setPageError(
            error instanceof Error
              ? error.message
              : "读取知识库列表失败，请稍后再试。"
          );
        }
      }
    }

    if (hasCheckedAuth) {
      void restoreKnowledgeBases();
    }

    return () => {
      isCancelled = true;
    };
  }, [hasCheckedAuth]);

  useEffect(() => {
    const selectedSessions = sessions.filter(
      (session) => session.knowledgeBaseId === selectedKnowledgeBaseId
    );
    setCurrentSessionId((previousSessionId) =>
      selectedSessions.some(
        (session) => session.id === previousSessionId
      )
        ? previousSessionId
        : selectedSessions[0]?.id || ""
    );
  }, [selectedKnowledgeBaseId, sessions]);

  useEffect(() => {
    let isCancelled = false;

    if (currentSessionMessageId && !areCurrentSessionMessagesLoaded) {
      const sessionId = currentSessionMessageId;

      void loadBackendMessages(sessionId)
        .then((messages) => {
          if (isCancelled) {
            return;
          }

          setSessions((previousSessions) =>
            previousSessions.map((session) =>
              session.id === sessionId
                ? { ...session, messages, messagesLoaded: true }
                : session
            )
          );
        })
        .catch((error) => {
          if (isCancelled) {
            return;
          }

          setSessionErrors((previousErrors) => ({
            ...previousErrors,
            [sessionId]:
              error instanceof Error
                ? error.message
                : "读取会话消息失败，请稍后再试。",
          }));
        });
    }

    return () => {
      isCancelled = true;
    };
  }, [areCurrentSessionMessagesLoaded, currentSessionMessageId]);

  useEffect(() => {
    const currentMessageCount = currentSession?.messages.length ?? 0;
    const sessionChanged = previousSessionIdRef.current !== currentSession?.id;
    const messageCountIncreased =
      currentMessageCount > previousMessageCountRef.current;
    const loadingStarted = isCurrentSessionLoading && !previousLoadingRef.current;

    if (sessionChanged || messageCountIncreased || loadingStarted) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }

    previousSessionIdRef.current = currentSession?.id ?? "";
    previousMessageCountRef.current = currentMessageCount;
    previousLoadingRef.current = isCurrentSessionLoading;
  }, [currentSession?.id, currentSession?.messages.length, isCurrentSessionLoading]);

  function handleLogout() {
    localStorage.removeItem(AUTH_STORAGE_KEY);
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(CURRENT_SESSION_KEY);
    window.location.href = "/login";
  }

  async function handleCreateSession() {
    if (
      !selectedKnowledgeBaseId ||
      selectedKnowledgeBaseId === DEFAULT_KNOWLEDGE_BASE_ID
    ) {
      setPageError("请先选择一个知识库。");
      return;
    }

    setIsCreatingSession(true);
    setPageError("");

    try {
      const newSession = await createBackendSession(selectedKnowledgeBaseId);

      setSessions((prev) => [newSession, ...prev]);
      setCurrentSessionId(newSession.id);
      setInput("");
    } catch (error) {
      setPageError(
        error instanceof Error ? error.message : "创建对话失败，请稍后再试。"
      );
    } finally {
      setIsCreatingSession(false);
    }
  }

  async function handleDeleteSession(sessionId: string) {
    if (deletingSessionId) {
      return;
    }

    const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

    if (!authState) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      window.location.href = "/login";
      return;
    }

    setDeletingSessionId(sessionId);
    setPageError("");

    try {
      const session = sessions.find(
        (candidate) => candidate.id === sessionId
      );
      const knowledgeBaseId =
        session?.knowledgeBaseId || selectedKnowledgeBaseId;
      const response = await fetch(
        `/api/chat/knowledge-bases/${encodeURIComponent(
          knowledgeBaseId
        )}/conversations/${encodeURIComponent(sessionId)}`,
        {
          method: "DELETE",
          headers: {
            Authorization: buildAuthorizationHeader(authState),
          },
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(
          getResponseErrorMessage(
            errorText,
            "删除会话失败，请稍后再试。",
            response.status
          )
        );
      }

      const allRemainingSessions = sessions.filter(
        (session) => session.id !== sessionId
      );
      const remainingVisibleSessions = allRemainingSessions.filter(
        (session) => session.knowledgeBaseId === knowledgeBaseId
      );

      setSessions(allRemainingSessions);
      setLoadingSessions((prev) => {
        const next = { ...prev };
        delete next[sessionId];
        return next;
      });
      setSessionErrors((prev) => {
        const next = { ...prev };
        delete next[sessionId];
        return next;
      });

      if (editingSessionId === sessionId) {
        setEditingSessionId("");
        setEditingTitle("");
      }

      if (remainingVisibleSessions.length === 0) {
        setCurrentSessionId("");
        setInput("");
      } else if (currentSessionId === sessionId) {
        setCurrentSessionId(remainingVisibleSessions[0].id);
        setInput("");
      }
    } catch (error) {
      setPageError(
        error instanceof Error ? error.message : "删除会话失败，请稍后再试。"
      );
    } finally {
      setDeletingSessionId("");
    }
  }

  function handleStartRename(session: ChatSession) {
    setEditingSessionId(session.id);
    setEditingTitle(session.title);
  }

  async function handleSaveRename() {
    if (!editingSessionId || renamingSessionId) {
      return;
    }

    const normalizedTitle = editingTitle.trim() || "新对话";
    const session = sessions.find(
      (candidate) => candidate.id === editingSessionId
    );
    const knowledgeBaseId =
      session?.knowledgeBaseId || selectedKnowledgeBaseId;
    const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

    if (!authState) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      window.location.href = "/login";
      return;
    }

    setRenamingSessionId(editingSessionId);
    setSessionErrors((prev) => ({
      ...prev,
      [editingSessionId]: "",
    }));

    try {
      const response = await fetch(
        `/api/chat/knowledge-bases/${encodeURIComponent(
          knowledgeBaseId
        )}/conversations/${encodeURIComponent(editingSessionId)}`,
        {
          method: "PATCH",
          headers: {
            Authorization: buildAuthorizationHeader(authState),
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            title: normalizedTitle,
          }),
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(
          getResponseErrorMessage(
            errorText,
            "重命名失败，请稍后再试。",
            response.status
          )
        );
      }

      setSessions((prev) =>
        prev.map((session) =>
          session.id === editingSessionId
            ? {
                ...session,
                title: normalizedTitle,
              }
            : session
        )
      );

      setEditingSessionId("");
      setEditingTitle("");
    } catch (error) {
      setSessionErrors((prev) => ({
        ...prev,
        [editingSessionId]:
          error instanceof Error ? error.message : "重命名失败，请稍后再试。",
      }));
    } finally {
      setRenamingSessionId("");
    }
  }

  function handleCancelRename() {
    setEditingSessionId("");
    setEditingTitle("");
  }

  async function handleCopyMessage(messageKey: string, content: string) {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(content);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = content;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      }

      setCopiedMessageKey(messageKey);

      window.setTimeout(() => {
        setCopiedMessageKey((current) =>
          current === messageKey ? "" : current
        );
      }, 1500);
    } catch (error) {
      console.error("Failed to copy message:", error);

      try {
        const textarea = document.createElement("textarea");
        textarea.value = content;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);

        setCopiedMessageKey(messageKey);

        window.setTimeout(() => {
          setCopiedMessageKey((current) =>
            current === messageKey ? "" : current
          );
        }, 1500);
      } catch (fallbackError) {
        console.error("Fallback copy also failed:", fallbackError);
      }
    }
  }

  async function loadConversationDiagnostics(
    conversationId: string,
    options: { silent?: boolean } = {}
  ) {
    const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

    if (!authState) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      window.location.href = "/login";
      return;
    }

    if (!options.silent) {
      setLoadingDiagnostics((prev) => ({
        ...prev,
        [conversationId]: true,
      }));
      setDiagnosticErrors((prev) => ({
        ...prev,
        [conversationId]: "",
      }));
    }

    try {
      const response = await fetch(
        `/api/chat/conversations/${encodeURIComponent(
          conversationId
        )}/diagnostics`,
        {
          method: "GET",
          headers: {
            Authorization: buildAuthorizationHeader(authState),
          },
        }
      );
      const responseText = await response.text();

      if (!response.ok) {
        throw new Error(
          getResponseErrorMessage(
            responseText,
            "加载诊断信息失败，请稍后再试。",
            response.status
          )
        );
      }

      const data = parseJsonValue(responseText);
      const diagnostics = getConversationDiagnostics(data);

      setConversationDiagnostics((prev) => ({
        ...prev,
        [conversationId]: diagnostics,
      }));
    } catch (error) {
      if (!options.silent) {
        setDiagnosticErrors((prev) => ({
          ...prev,
          [conversationId]:
            error instanceof Error
              ? error.message
              : "加载诊断信息失败，请稍后再试。",
        }));
      }
    } finally {
      if (!options.silent) {
        setLoadingDiagnostics((prev) => ({
          ...prev,
          [conversationId]: false,
        }));
      }
    }
  }

  function handleToggleDiagnostics(conversationId: string, messageKey: string) {
    const panelKey = `${conversationId}:${messageKey}`;
    const shouldOpen = !expandedDiagnosticPanels[panelKey];

    setExpandedDiagnosticPanels((prev) => ({
      ...prev,
      [panelKey]: shouldOpen,
    }));

    if (
      shouldOpen &&
      conversationDiagnostics[conversationId] === undefined &&
      !loadingDiagnostics[conversationId]
    ) {
      void loadConversationDiagnostics(conversationId);
    }
  }

  async function handleSubmit(overrideInput?: string) {
    if (isCurrentSessionLoading || isCreatingSession) {
      return;
    }

    const messageContent = (overrideInput ?? input).trim();

    if (!messageContent) {
      if (currentSession) {
        setSessionErrors((prev) => ({
          ...prev,
          [currentSession.id]: "请先在下方输入问题。",
        }));
      } else {
        setPageError("请先在下方输入问题。");
      }
      return;
    }

    if (
      !selectedKnowledgeBaseId ||
      selectedKnowledgeBaseId === DEFAULT_KNOWLEDGE_BASE_ID
    ) {
      setPageError("请先选择一个知识库。");
      return;
    }

    const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

    if (!authState) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      window.location.href = "/login";
      return;
    }

    let activeSession = currentSession;

    if (!activeSession) {
      setIsCreatingSession(true);
      setPageError("");

      try {
        const newSession = await createBackendSession(
          selectedKnowledgeBaseId,
          buildSessionTitle(messageContent)
        );
        activeSession = newSession;
        setSessions((prev) => [newSession, ...prev]);
        setCurrentSessionId(newSession.id);
      } catch (error) {
        setPageError(
          error instanceof Error
            ? error.message
            : "创建对话失败，请稍后再试。"
        );
        return;
      } finally {
        setIsCreatingSession(false);
      }
    }

    setPageError("");

    const userMessage: Message = {
      role: "user",
      content: messageContent,
    };

    const updatedMessages = [...activeSession.messages, userMessage];
    const activeSessionId = activeSession.id;
    const activeKnowledgeBaseId = activeSession.knowledgeBaseId;

    setSessions((prev) =>
      prev.map((session) =>
        session.id === activeSessionId
          ? {
              ...session,
              title:
                session.messages.length === 0
                  ? buildSessionTitle(messageContent)
                  : session.title,
              messages: updatedMessages,
            }
          : session
      )
    );

    setInput("");
    setSessionErrors((prev) => ({
      ...prev,
      [activeSessionId]: "",
    }));
    setLoadingSessions((prev) => ({
      ...prev,
      [activeSessionId]: true,
    }));

    const appendAssistantContent = (content: string) => {
      setSessions((prev) =>
        prev.map((session) => {
          if (session.id !== activeSessionId) {
            return session;
          }

          const messages = [...session.messages];
          const lastMessage = messages[messages.length - 1];

          if (lastMessage?.role === "assistant") {
            messages[messages.length - 1] = {
              ...lastMessage,
              content: lastMessage.content + content,
            };
          } else {
            messages.push({
              role: "assistant",
              content,
            });
          }

          return {
            ...session,
            messages,
          };
        })
      );
    };

    const setAssistantSources = (sources: ChatSource[]) => {
      if (sources.length === 0) {
        return;
      }

      setSessions((prev) =>
        prev.map((session) => {
          if (session.id !== activeSessionId) {
            return session;
          }

          const messages = [...session.messages];
          const lastMessage = messages[messages.length - 1];

          if (lastMessage?.role === "assistant") {
            messages[messages.length - 1] = {
              ...lastMessage,
              sources,
            };
          } else {
            messages.push({
              role: "assistant",
              content: "",
              sources,
            });
          }

          return {
            ...session,
            messages,
          };
        })
      );
    };

    const setAssistantRetrieval = (retrieval: RetrievalState) => {
      setSessions((prev) =>
        prev.map((session) => {
          if (session.id !== activeSessionId) {
            return session;
          }

          const messages = [...session.messages];
          const lastMessage = messages[messages.length - 1];

          if (lastMessage?.role === "assistant") {
            messages[messages.length - 1] = {
              ...lastMessage,
              retrieval,
            };
          } else {
            messages.push({
              role: "assistant",
              content: "",
              retrieval,
            });
          }

          return {
            ...session,
            messages,
          };
        })
      );
    };

    const setAssistantMessageId = (messageId: string) => {
      if (!messageId) {
        return;
      }

      setSessions((prev) =>
        prev.map((session) => {
          if (session.id !== activeSessionId) {
            return session;
          }

          const messages = [...session.messages];
          const lastMessage = messages[messages.length - 1];

          if (lastMessage?.role === "assistant") {
            messages[messages.length - 1] = {
              ...lastMessage,
              id: messageId,
            };
          }

          return {
            ...session,
            messages,
          };
        })
      );
    };

    const setAssistantFallback = (content: string) => {
      setSessions((prev) =>
        prev.map((session) => {
          if (session.id !== activeSessionId) {
            return session;
          }

          const messages = [...session.messages];
          const lastMessage = messages[messages.length - 1];

          if (lastMessage?.role === "assistant" && !lastMessage.content) {
            messages[messages.length - 1] = {
              ...lastMessage,
              content,
            };
          }

          return {
            ...session,
            messages,
          };
        })
      );
    };

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          Authorization: buildAuthorizationHeader(authState),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          conversation_id: activeSessionId,
          knowledge_base_id: activeKnowledgeBaseId,
          message: messageContent,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        const errorMessage = getResponseErrorMessage(
          errorText,
          "请求失败了，请稍后再试。",
          response.status
        );

        setSessionErrors((prev) => ({
          ...prev,
          [activeSessionId]: errorMessage,
        }));
        return;
      }

      appendAssistantContent("");

      const contentType = response.headers.get("Content-Type") || "";

      if (contentType.includes("application/json")) {
        const data = (await response.json()) as unknown;
        const answer = getAssistantContent(data);
        const sources = getChatSources(data);
        const retrieval = getRetrievalState(data);
        const messageId = getAssistantMessageId(data);

        if (retrieval) {
          setAssistantRetrieval(retrieval);
        }
        setAssistantMessageId(messageId);
        setAssistantSources(sources);
        setAssistantFallback(answer || "模型暂时没有返回内容。");
        return;
      }

      if (!response.body) {
        const answer = await response.text();
        setAssistantFallback(answer || "模型暂时没有返回内容。");
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let streamedAnswer = "";
      let sseBuffer = "";
      const isSseStream = contentType.includes("text/event-stream");

      const handleSseBlock = (block: string) => {
        const { event, data } = parseSseBlock(block);

        if (event === "retrieval") {
          const retrieval = getRetrievalState(data);

          if (retrieval) {
            setAssistantRetrieval(retrieval);
          }

          return false;
        }

        if (event === "sources") {
          setAssistantSources(getChatSources(data));
          return false;
        }

        if (event === "answer") {
          const answerContent = getSseAnswerContent(data);

          if (answerContent) {
            streamedAnswer += answerContent;
            appendAssistantContent(answerContent);
          }

          return false;
        }

        if (event === "done") {
          const parsedData = parseJsonValue(data);
          const retrieval = getRetrievalState(parsedData);
          const doneSources = getChatSources(parsedData);
          const messageId = getAssistantMessageId(parsedData);

          if (retrieval) {
            setAssistantRetrieval(retrieval);
          }

          setAssistantMessageId(messageId);
          setAssistantSources(doneSources);
          void loadConversationDiagnostics(activeSessionId, { silent: true });

          const doneAnswer = getAssistantContent(parsedData);

          if (doneAnswer) {
            if (!streamedAnswer) {
              appendAssistantContent(doneAnswer);
            } else if (doneAnswer !== streamedAnswer) {
              setAssistantFallback(doneAnswer);
            }
          } else if (!streamedAnswer) {
            setAssistantFallback("模型暂时没有返回内容。");
          }

          return true;
        }

        if (data) {
          const answerContent = getSseAnswerContent(data);

          if (answerContent) {
            streamedAnswer += answerContent;
            appendAssistantContent(answerContent);
          }
        }

        return false;
      };

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          break;
        }

        const chunk = decoder.decode(value, { stream: true });

        if (chunk && isSseStream) {
          sseBuffer += chunk;

          while (true) {
            const separatorIndex = sseBuffer.search(/\r?\n\r?\n/);

            if (separatorIndex === -1) {
              break;
            }

            const block = sseBuffer.slice(0, separatorIndex);
            const separatorMatch = sseBuffer
              .slice(separatorIndex)
              .match(/^\r?\n\r?\n/);
            sseBuffer = sseBuffer.slice(
              separatorIndex + (separatorMatch?.[0].length || 2)
            );

            if (handleSseBlock(block)) {
              await reader.cancel();
              break;
            }
          }

          await waitForNextPaint();
          continue;
        }

        if (chunk) {
          streamedAnswer += chunk;
          appendAssistantContent(chunk);
          await waitForNextPaint();
        }
      }

      const finalChunk = decoder.decode();

      if (finalChunk && isSseStream) {
        sseBuffer += finalChunk;
      } else if (finalChunk) {
        streamedAnswer += finalChunk;
        appendAssistantContent(finalChunk);
        await waitForNextPaint();
      }

      if (isSseStream && sseBuffer.trim()) {
        handleSseBlock(sseBuffer.trim());
        await waitForNextPaint();
      }

      if (!streamedAnswer) {
        setAssistantFallback("模型暂时没有返回内容。");
      }
    } catch (error) {
      console.error(error);
      setSessionErrors((prev) => ({
        ...prev,
        [activeSessionId]: "请求失败了，请稍后再试。",
      }));
    } finally {
      setLoadingSessions((prev) => ({
        ...prev,
        [activeSessionId]: false,
      }));
    }
  }

  if (!hasCheckedAuth) {
    return (
      <main className="research-canvas flex min-h-screen items-center justify-center px-4">
        <div className="font-utility flex items-center gap-3 text-xs font-semibold text-[#176b62]">
          <span className="h-2.5 w-2.5 animate-pulse bg-[#e36b4f]" />
          正在整理研究台...
        </div>
      </main>
    );
  }

  return (
    <main className="research-canvas min-h-screen px-3 py-3 md:px-5 md:py-5 lg:h-screen lg:overflow-hidden">
      <div className="mx-auto grid min-w-0 w-full max-w-[1440px] gap-4 lg:h-full lg:grid-cols-[304px_minmax(0,1fr)]">
        <aside className="research-enter flex min-w-0 max-h-[calc(100vh-1.5rem)] flex-col border border-[#bdcac5] bg-[#edf2ef] p-4 lg:sticky lg:top-5 lg:h-[calc(100vh-2.5rem)] lg:max-h-none">
          <div className="flex items-center justify-between gap-3 border-b border-[#c7d1cd] px-1 pb-4">
            <div className="min-w-0">
              <p className="font-utility text-[10px] font-semibold uppercase text-[#72807b]">
                Researcher
              </p>
              <Link
                href="/settings"
                title="打开用户设置"
                className="font-display mt-1 block truncate text-lg font-semibold text-[#17201f] underline decoration-[#d5a83b] decoration-2 underline-offset-4 transition hover:text-[#176b62]"
              >
                {currentUsername || "已登录"}
              </Link>
            </div>
            <button
              type="button"
              onClick={handleLogout}
              className="font-utility shrink-0 border-b border-[#9eaaa6] px-1 py-1 text-[11px] font-semibold text-[#64716d] transition hover:border-[#e36b4f] hover:text-[#9b3c29]"
            >
              退出
            </button>
          </div>

          <div className="border-b border-[#c7d1cd] py-4">
            <div className="flex items-center justify-between gap-3">
              <label
                htmlFor="knowledge-base"
                className="font-utility text-[10px] font-semibold uppercase text-[#72807b]"
              >
                Knowledge Base
              </label>
              <button
                type="button"
                onClick={() => setIsKnowledgeBaseManagerOpen(true)}
                className="text-xs font-semibold text-[#176b62] underline decoration-[#d5a83b] decoration-2 underline-offset-4"
              >
                管理
              </button>
            </div>

            <select
              id="knowledge-base"
              value={selectedKnowledgeBaseId}
              onChange={(event) =>
                setSelectedKnowledgeBaseId(event.target.value)
              }
              className="research-focus mt-2 w-full border border-[#b7c4bf] bg-[#fcfdfb] px-3 py-2.5 text-sm font-semibold text-[#17201f]"
            >
              {knowledgeBases.length === 0 && (
                <option value="">暂无知识库</option>
              )}
              {knowledgeBases.map((knowledgeBase) => (
                <option key={knowledgeBase.id} value={knowledgeBase.id}>
                  {knowledgeBase.name}
                </option>
              ))}
            </select>

            <div className="mt-3 grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={
                  !selectedKnowledgeBaseId || isUploadingKnowledgeFiles
                }
                className="bg-[#176b62] px-3 py-2.5 text-xs font-semibold text-white transition hover:bg-[#105149] disabled:bg-[#91aaa4]"
              >
                {isUploadingKnowledgeFiles ? "上传中..." : "上传文件"}
              </button>
              <button
                type="button"
                onClick={() => {
                  void handleOpenFileManager();
                }}
                className="border border-[#aebdb7] bg-[#fcfdfb] px-3 py-2.5 text-xs font-semibold text-[#46514e] transition hover:border-[#176b62] hover:text-[#176b62]"
              >
                文件 {selectedKnowledgeBaseFileCount}
              </button>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".txt,.md,.csv,.json,.pdf,.png,.jpg,.jpeg,.webp,.gif"
              onChange={(event) => {
                void handleSelectFiles(event.target.files);
              }}
              className="hidden"
            />
          </div>

          <button
            onClick={() => {
              void handleCreateSession();
            }}
            disabled={isCreatingSession}
            className="mt-4 w-full border border-[#17201f] bg-[#17201f] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#2d3936] disabled:border-[#9ba8a3] disabled:bg-[#9ba8a3]"
          >
            {isCreatingSession ? "创建中..." : "＋ 新建研究会话"}
          </button>

          <div className="mt-4 flex items-center justify-between px-1">
            <p className="font-utility text-[10px] font-semibold uppercase text-[#72807b]">
              Conversation Index
            </p>
            <p className="font-utility text-[10px] text-[#72807b]">
              {String(visibleSessions.length).padStart(2, "0")}
            </p>
          </div>

          <div className="mt-2 min-h-0 min-w-0 flex-1 space-y-2 overflow-y-auto pr-1">
            {visibleSessions.length === 0 && (
              <p className="px-1 py-2 text-xs text-[#7b8884]">
                暂无会话，发送问题即可开始
              </p>
            )}
            {visibleSessions.map((session) => {
              const isActive = session.id === currentSession?.id;

              return (
                <div
                  key={session.id}
                  className={`min-w-0 w-full border-l-4 px-3 py-3 text-left text-sm transition ${
                    isActive
                      ? "border-[#e36b4f] bg-[#17201f] text-white"
                      : "border-transparent bg-[#fcfdfb] text-[#46514e] hover:border-[#d5a83b] hover:bg-white"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      {editingSessionId === session.id ? (
                        <div className="space-y-2">
                          <input
                            value={editingTitle}
                            onChange={(e) => setEditingTitle(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") {
                                e.preventDefault();
                                void handleSaveRename();
                              }

                              if (e.key === "Escape") {
                                handleCancelRename();
                              }
                            }}
                            autoFocus
                            className="research-focus w-full border border-[#b7c4bf] bg-white px-3 py-2 text-sm text-[#17201f]"
                          />
                          <div className="flex gap-2">
                            <button
                              onClick={() => {
                                void handleSaveRename();
                              }}
                              disabled={renamingSessionId === session.id}
                              className="bg-[#176b62] px-2 py-1 text-xs text-white transition hover:bg-[#105149]"
                            >
                              {renamingSessionId === session.id
                                ? "保存中..."
                                : "保存"}
                            </button>
                            <button
                              onClick={handleCancelRename}
                              className="px-2 py-1 text-xs transition hover:bg-[#dfe7e3] hover:text-[#17201f]"
                            >
                              取消
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button
                          onClick={() => {
                            void handleSelectSession(session);
                          }}
                          className="min-w-0 w-full text-left"
                        >
                          <div className="truncate font-semibold">{session.title}</div>
                          <div
                            className={`mt-1 truncate text-xs ${
                              isActive ? "text-[#b8c8c3]" : "text-[#7b8884]"
                            }`}
                          >
                            {session.messages[session.messages.length - 1]?.content ||
                              "暂无消息"}
                          </div>
                        </button>
                      )}
                    </div>

                    {editingSessionId !== session.id && (
                      <div className="flex shrink-0 gap-1">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleStartRename(session);
                          }}
                          className={`rounded-lg px-2 py-1 text-xs transition ${
                            isActive
                              ? "text-[#b8c8c3] hover:bg-white/10 hover:text-white"
                              : "text-[#73807c] hover:bg-[#dfe7e3] hover:text-[#17201f]"
                          }`}
                        >
                          重命名
                        </button>

                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            void handleDeleteSession(session.id);
                          }}
                          disabled={deletingSessionId === session.id}
                          className={`rounded-lg px-2 py-1 text-xs transition ${
                            isActive
                              ? "text-[#b8c8c3] hover:bg-white/10 hover:text-white"
                              : "text-[#73807c] hover:bg-[#fff1ed] hover:text-[#9b3c29]"
                          }`}
                        >
                          {deletingSessionId === session.id
                            ? "删除中..."
                            : "删除"}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </aside>

        <section className="research-paper research-enter min-w-0 border border-[#bdcac5] lg:flex lg:h-full lg:min-h-0 lg:flex-col lg:overflow-hidden">
          <header className="shrink-0 border-b border-[#cbd5d1] bg-[#fcfdfb] px-5 py-5 md:px-8 md:py-6">
            <div className="flex flex-col justify-between gap-5 md:flex-row md:items-end">
              <div className="min-w-0">
                <div className="flex items-center gap-3">
                  <span className="font-utility bg-[#d5a83b] px-2 py-1 text-[10px] font-bold uppercase text-[#17201f]">
                    Live Research
                  </span>
                  <span className="font-utility text-[10px] font-semibold uppercase text-[#72807b]">
                    {selectedKnowledgeBase?.name || "暂无知识库"}
                  </span>
                </div>
                <h1 className="font-display mt-4 truncate text-3xl font-semibold text-[#17201f] md:text-4xl">
                  {currentSession?.title || "研究工作台"}
                </h1>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-[#64716d]">
                  基于当前知识库继续提问，回答与上下文会保存在此会话中。
                </p>
              </div>
              <div className="font-utility flex shrink-0 gap-5 border-t border-[#d6dedb] pt-4 text-[10px] uppercase text-[#72807b] md:border-l md:border-t-0 md:pl-5 md:pt-0">
                <span>
                  Messages
                  <strong className="mt-1 block text-base text-[#17201f]">
                    {String(currentSession?.messages.length || 0).padStart(2, "0")}
                  </strong>
                </span>
                <span>
                  Files
                  <strong className="mt-1 block text-base text-[#17201f]">
                    {String(selectedKnowledgeBaseFileCount).padStart(2, "0")}
                  </strong>
                </span>
              </div>
            </div>
          </header>

          <div
            ref={messagesContainerRef}
            className="research-scroll px-5 py-7 md:px-8 md:py-9 lg:min-h-0 lg:flex-1 lg:overflow-y-auto lg:overscroll-contain"
          >
            <div className="space-y-6">
              {!currentSession && (
                <div className="flex min-h-[240px] items-center justify-center text-center">
                  <p className="text-sm text-[#7b8884]">
                    输入问题，开始新的研究会话
                  </p>
                </div>
              )}

              {currentSession?.messages.length === 0 && (
                <div className="border-y border-[#cbd5d1] py-12 text-center">
                  <p className="font-utility text-[10px] font-semibold uppercase text-[#176b62]">
                    Empty Research Log
                  </p>
                  <h2 className="font-display mt-3 text-2xl font-semibold text-[#17201f]">
                    从一个明确的问题开始
                  </h2>
                  <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[#64716d]">
                    你的问题和 AI 回答会按顺序记录在这里，便于后续回顾与继续追问。
                  </p>
                </div>
              )}

              {currentSession?.messages.map((message, index) => {
                const messageKey = `${currentSession.id}-${index}`;
                const diagnosticPanelKey = `${currentSession.id}:${messageKey}`;
                const isDiagnosticExpanded = Boolean(
                  expandedDiagnosticPanels[diagnosticPanelKey]
                );
                const cachedDiagnostics =
                  conversationDiagnostics[currentSession.id];
                const diagnostic = message.id
                  ? (cachedDiagnostics?.find(
                      (item) => item.messageId === message.id
                    ) ?? null)
                  : null;
                const isDiagnosticLoading = Boolean(
                  loadingDiagnostics[currentSession.id]
                );
                const diagnosticError =
                  diagnosticErrors[currentSession.id] || "";
                const diagnosticChannels = diagnostic
                  ? diagnostic.retrievalSources.length > 0
                    ? diagnostic.retrievalSources
                    : diagnostic.diagnostics.retrievalSources
                  : [];
                const diagnosticTiming = diagnostic?.diagnostics.timing;
                const finalDiagnosticNeedRetrieval = diagnostic
                  ? (diagnostic.finalNeedRetrieval ?? diagnostic.needRetrieval)
                  : null;
                const isStreamingPlaceholder =
                  message.role === "assistant" &&
                  index === currentSession.messages.length - 1 &&
                  isCurrentSessionLoading &&
                  !message.content;
                const sourceCount = message.sources?.length ?? 0;
                const shouldShowSources =
                  message.role === "assistant" && sourceCount > 0;
                const displaySourceCount =
                  message.retrieval && message.retrieval.source_count > 0
                    ? message.retrieval.source_count
                    : sourceCount;
                const retrievedCount =
                  message.retrieval && message.retrieval.retrieved_count > 0
                    ? message.retrieval.retrieved_count
                    : null;
                const shouldShowRetrievalEmptyHint =
                  message.role === "assistant" &&
                  message.retrieval?.need_retrieval === true &&
                  message.retrieval.source_count === 0 &&
                  !shouldShowSources;

                return (
                  <div
                    key={messageKey}
                    className={`relative grid min-w-0 gap-3 border-l-2 pl-5 md:grid-cols-[74px_minmax(0,1fr)] md:gap-5 md:pl-6 ${
                      message.role === "user"
                        ? "border-[#e36b4f]"
                        : "border-[#176b62]"
                    }`}
                  >
                    <div className="font-utility pt-1 text-[10px] font-semibold uppercase text-[#72807b]">
                      <span className="block text-[#17201f]">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                      {message.role === "user" ? "Question" : "Response"}
                    </div>
                    <article
                      className={`min-w-0 px-5 py-4 ${
                        message.role === "user"
                          ? "bg-[#17201f] text-white"
                          : "border border-[#d5ded9] bg-[#f5f8f6] text-[#26312f]"
                      }`}
                    >
                      <MarkdownContent
                        content={
                          isStreamingPlaceholder
                            ? "AI 正在思考中..."
                            : message.content
                        }
                        isUserMessage={message.role === "user"}
                      />

                      {shouldShowRetrievalEmptyHint && (
                        <div className="mt-4 border-t border-[#d6dedb] pt-3">
                          <p className="text-xs leading-5 text-[#64716d]">
                            已检索知识库，但没有找到高相关引用
                          </p>
                        </div>
                      )}

                      {shouldShowSources && message.sources && (
                        <div className="mt-4 border-t border-[#d6dedb] pt-3">
                          <div className="flex flex-wrap items-baseline justify-between gap-2">
                            <p className="font-utility text-[10px] font-semibold uppercase text-[#64716d]">
                              Sources
                            </p>
                            <p className="text-xs text-[#64716d]">
                              可展示 {displaySourceCount} 条
                              {retrievedCount !== null
                                ? ` · 召回 ${retrievedCount} 段`
                                : ""}
                            </p>
                          </div>
                          <div className="mt-2 space-y-2">
                            {message.sources.map((source, sourceIndex) => (
                              <div
                                key={`${messageKey}-source-${
                                  source.index ?? sourceIndex
                                }`}
                                className="border border-[#d5ded9] bg-[#fcfdfb] px-3 py-2 text-xs text-[#46514e]"
                              >
                                <div className="flex items-start justify-between gap-3">
                                  <p className="min-w-0 truncate font-semibold text-[#17201f]">
                                    {source.title}
                                  </p>
                                  <div className="font-utility flex shrink-0 flex-wrap justify-end gap-2 text-[10px] text-[#72807b]">
                                    {source.chunkIndex !== undefined && (
                                      <span>
                                        文件片段 #{source.chunkIndex}
                                      </span>
                                    )}
                                    {source.vectorScore !== undefined && (
                                      <span>
                                        向量距离{" "}
                                        {source.vectorScore.toFixed(4)}
                                      </span>
                                    )}
                                    {source.fulltextScore !== undefined && (
                                      <span>
                                        文本分{" "}
                                        {source.fulltextScore.toFixed(4)}
                                      </span>
                                    )}
                                    {source.rerankScore !== undefined && (
                                      <span>
                                        相关性{" "}
                                        {source.rerankScore.toFixed(4)}
                                      </span>
                                    )}
                                    {source.metadata && (
                                      <span>{source.metadata}</span>
                                    )}
                                  </div>
                                </div>
                                {source.content && (
                                  <p className="mt-1 max-h-10 overflow-hidden leading-5 text-[#64716d]">
                                    {source.content}
                                  </p>
                                )}
                                {((source.fileName &&
                                  source.fileName !== source.title) ||
                                  source.fileType) && (
                                  <p className="mt-1 truncate text-[11px] text-[#72807b]">
                                    {[
                                      source.fileName !== source.title
                                        ? source.fileName
                                        : "",
                                      source.fileType,
                                    ]
                                      .filter(Boolean)
                                      .join(" · ")}
                                  </p>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {message.role === "assistant" &&
                        isDiagnosticExpanded && (
                          <div className="mt-4 border-t border-[#d6dedb] pt-3">
                            <div className="flex flex-wrap items-baseline justify-between gap-2">
                              <p className="font-utility text-[10px] font-semibold uppercase text-[#64716d]">
                                诊断
                              </p>
                              {diagnostic?.createdAt && (
                                <p className="text-xs text-[#72807b]">
                                  {diagnostic.createdAt}
                                </p>
                              )}
                            </div>

                            {isDiagnosticLoading && !cachedDiagnostics && (
                              <p className="mt-2 text-xs text-[#64716d]">
                                正在加载诊断信息...
                              </p>
                            )}

                            {diagnosticError && (
                              <p className="mt-2 border border-[#f0b8a8] bg-[#fff1ed] px-3 py-2 text-xs text-[#9b3c29]">
                                {diagnosticError}
                              </p>
                            )}

                            {!isDiagnosticLoading &&
                              !diagnosticError &&
                              !diagnostic && (
                                <div className="mt-2 border border-[#d5ded9] bg-[#fcfdfb] px-3 py-2 text-xs text-[#64716d]">
                                  <p className="font-semibold text-[#17201f]">
                                    暂无诊断信息
                                  </p>
                                  <p className="mt-1">
                                    常见原因：这是旧消息、本地问候短路回答、消息生成失败或被取消，或后端版本较旧。
                                  </p>
                                </div>
                              )}

                            {diagnostic && (
                              <div className="mt-2 space-y-3">
                                <div className="grid gap-2 border border-[#d5ded9] bg-[#fcfdfb] px-3 py-2 text-xs text-[#46514e] md:grid-cols-2">
                                  <p>
                                    <span className="text-[#72807b]">
                                      最终决策：
                                    </span>
                                    {formatRetrievalDecision(
                                      finalDiagnosticNeedRetrieval
                                    )}
                                  </p>
                                  <p>
                                    <span className="text-[#72807b]">
                                      LLM 判断：
                                    </span>
                                    {formatRetrievalDecision(
                                      diagnostic.llmNeedRetrieval
                                    )}
                                  </p>
                                  <p>
                                    <span className="text-[#72807b]">
                                      规则覆盖：
                                    </span>
                                    {diagnostic.overrideApplied ? "是" : "否"}
                                  </p>
                                  <p>
                                    <span className="text-[#72807b]">
                                      向量降级：
                                    </span>
                                    {diagnostic.vectorDegraded ? "是" : "否"}
                                  </p>
                                  <p>
                                    <span className="text-[#72807b]">
                                      展示引用：
                                    </span>
                                    {diagnostic.sourceCount}
                                  </p>
                                  <p>
                                    <span className="text-[#72807b]">
                                      最终引用通道：
                                    </span>
                                    {diagnosticChannels.length > 0
                                      ? diagnosticChannels.join(" + ")
                                      : "—"}
                                  </p>
                                  <p className="md:col-span-2">
                                    <span className="text-[#72807b]">
                                      改写问题：
                                    </span>
                                    {diagnostic.rewrittenQuery || "—"}
                                  </p>
                                  <p className="md:col-span-2">
                                    <span className="text-[#72807b]">
                                      LLM 原因：
                                    </span>
                                    {diagnostic.llmReason ||
                                      diagnostic.reason ||
                                      "—"}
                                  </p>
                                  <p className="md:col-span-2">
                                    <span className="text-[#72807b]">
                                      覆盖原因：
                                    </span>
                                    {diagnostic.overrideReason || "—"}
                                  </p>
                                </div>

                                <div className="grid gap-2 border border-[#d5ded9] bg-[#fcfdfb] px-3 py-2 text-xs text-[#46514e] md:grid-cols-4">
                                  <p>
                                    <span className="block text-[#72807b]">
                                      Vector 召回
                                    </span>
                                    {formatDiagnosticCount(
                                      diagnostic.diagnostics.vectorCount
                                    )}
                                  </p>
                                  <p>
                                    <span className="block text-[#72807b]">
                                      Fulltext 召回
                                    </span>
                                    {formatDiagnosticCount(
                                      diagnostic.diagnostics.fulltextCount
                                    )}
                                  </p>
                                  <p>
                                    <span className="block text-[#72807b]">
                                      融合后
                                    </span>
                                    {formatDiagnosticCount(
                                      diagnostic.diagnostics.fusedCount
                                    )}
                                  </p>
                                  <p>
                                    <span className="block text-[#72807b]">
                                      精排后
                                    </span>
                                    {formatDiagnosticCount(
                                      diagnostic.diagnostics.rerankedCount
                                    )}
                                  </p>
                                </div>

                                <div className="border border-[#d5ded9] bg-[#fcfdfb] px-3 py-2 text-xs text-[#46514e]">
                                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                                    <p className="font-utility text-[10px] font-semibold uppercase text-[#64716d]">
                                      LLM
                                    </p>
                                    <p className="max-w-full truncate text-[11px] text-[#72807b]">
                                      {formatDiagnosticValue(
                                        diagnostic.diagnostics.llm.baseUrl
                                      )}
                                    </p>
                                  </div>
                                  <div className="mt-2 grid gap-2 md:grid-cols-4">
                                    <p>
                                      <span className="block text-[#72807b]">
                                        Provider
                                      </span>
                                      {formatDiagnosticValue(
                                        diagnostic.diagnostics.llm.provider
                                      )}
                                    </p>
                                    <p>
                                      <span className="block text-[#72807b]">
                                        Model
                                      </span>
                                      {formatDiagnosticValue(
                                        diagnostic.diagnostics.llm.model
                                      )}
                                    </p>
                                    <p>
                                      <span className="block text-[#72807b]">
                                        Key 来源
                                      </span>
                                      {formatDiagnosticValue(
                                        diagnostic.diagnostics.llm
                                          .credentialMode
                                      )}
                                    </p>
                                    <p>
                                      <span className="block text-[#72807b]">
                                        Temperature
                                      </span>
                                      {formatDiagnosticValue(
                                        diagnostic.diagnostics.llm.temperature
                                      )}
                                    </p>
                                    <p>
                                      <span className="block text-[#72807b]">
                                        Max tokens
                                      </span>
                                      {formatDiagnosticValue(
                                        diagnostic.diagnostics.llm.maxTokens
                                      )}
                                    </p>
                                    <p>
                                      <span className="block text-[#72807b]">
                                        Prompt tokens
                                      </span>
                                      {formatDiagnosticValue(
                                        diagnostic.diagnostics.llm.promptTokens
                                      )}
                                    </p>
                                    <p>
                                      <span className="block text-[#72807b]">
                                        Completion tokens
                                      </span>
                                      {formatDiagnosticValue(
                                        diagnostic.diagnostics.llm
                                          .completionTokens
                                      )}
                                    </p>
                                    <p>
                                      <span className="block text-[#72807b]">
                                        Total tokens
                                      </span>
                                      {formatDiagnosticValue(
                                        diagnostic.diagnostics.llm.totalTokens
                                      )}
                                    </p>
                                  </div>
                                </div>

                                <div className="border border-[#d5ded9] bg-[#fcfdfb] px-3 py-2 text-xs text-[#46514e]">
                                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                                    <p className="font-utility text-[10px] font-semibold uppercase text-[#64716d]">
                                      耗时分析
                                    </p>
                                    <p className="text-[11px] text-[#72807b]">
                                      总耗时{" "}
                                      {formatDiagnosticTiming(
                                        diagnosticTiming?.chatStreamTotalMs
                                      )}
                                    </p>
                                  </div>
                                  <div className="mt-3 space-y-3">
                                    <div>
                                      <p className="font-utility text-[10px] font-semibold uppercase text-[#72807b]">
                                        Decision
                                      </p>
                                      <div className="mt-1 grid gap-2 md:grid-cols-5">
                                        <p>
                                          <span className="block text-[#72807b]">
                                            问题改写
                                          </span>
                                          {formatDiagnosticTiming(
                                            diagnosticTiming?.standaloneQuestionMs
                                          )}
                                        </p>
                                        <p>
                                          <span className="block text-[#72807b]">
                                            读取配置
                                          </span>
                                          {formatDiagnosticTiming(
                                            diagnosticTiming?.retrievalSettingsMs
                                          )}
                                        </p>
                                        <p>
                                          <span className="block text-[#72807b]">
                                            知识画像
                                          </span>
                                          {formatDiagnosticTiming(
                                            diagnosticTiming?.knowledgeProfileMs
                                          )}
                                        </p>
                                        <p>
                                          <span className="block text-[#72807b]">
                                            Router
                                          </span>
                                          {formatDiagnosticTiming(
                                            diagnosticTiming?.queryRouterMs
                                          )}
                                        </p>
                                        <p>
                                          <span className="block text-[#72807b]">
                                            最终决策
                                          </span>
                                          {formatDiagnosticTiming(
                                            diagnosticTiming?.finalizeDecisionMs
                                          )}
                                        </p>
                                      </div>
                                    </div>

                                    <div>
                                      <p className="font-utility text-[10px] font-semibold uppercase text-[#72807b]">
                                        Retrieval
                                      </p>
                                      <div className="mt-1 grid gap-2 md:grid-cols-4 lg:grid-cols-7">
                                        <p>
                                          <span className="block text-[#72807b]">
                                            检索调用
                                          </span>
                                          {formatDiagnosticTiming(
                                            diagnosticTiming?.retrieveDocumentsMs
                                          )}
                                        </p>
                                        <p>
                                          <span className="block text-[#72807b]">
                                            Embedding
                                          </span>
                                          {formatDiagnosticTiming(
                                            diagnosticTiming?.embeddingMs
                                          )}
                                        </p>
                                        <p>
                                          <span className="block text-[#72807b]">
                                            Vector
                                          </span>
                                          {formatDiagnosticTiming(
                                            diagnosticTiming?.vectorMs
                                          )}
                                        </p>
                                        <p>
                                          <span className="block text-[#72807b]">
                                            Fulltext
                                          </span>
                                          {formatDiagnosticTiming(
                                            diagnosticTiming?.fulltextMs
                                          )}
                                        </p>
                                        <p>
                                          <span className="block text-[#72807b]">
                                            RRF
                                          </span>
                                          {formatDiagnosticTiming(
                                            diagnosticTiming?.rrfMs
                                          )}
                                        </p>
                                        <p>
                                          <span className="block text-[#72807b]">
                                            Rerank
                                          </span>
                                          {formatDiagnosticTiming(
                                            diagnosticTiming?.rerankMs
                                          )}
                                        </p>
                                        <p>
                                          <span className="block text-[#72807b]">
                                            检索总计
                                          </span>
                                          {formatDiagnosticTiming(
                                            diagnosticTiming?.retrievalTotalMs
                                          )}
                                        </p>
                                      </div>
                                    </div>

                                    <div>
                                      <p className="font-utility text-[10px] font-semibold uppercase text-[#72807b]">
                                        Answer
                                      </p>
                                      <div className="mt-1 grid gap-2 md:grid-cols-4">
                                        <p>
                                          <span className="block text-[#72807b]">
                                            回答前
                                          </span>
                                          {formatDiagnosticTiming(
                                            diagnosticTiming?.preAnswerTotalMs
                                          )}
                                        </p>
                                        <p>
                                          <span className="block text-[#72807b]">
                                            首 token
                                          </span>
                                          {formatDiagnosticTiming(
                                            diagnosticTiming?.firstAnswerTokenMs
                                          )}
                                        </p>
                                        <p>
                                          <span className="block text-[#72807b]">
                                            输出耗时
                                          </span>
                                          {formatDiagnosticTiming(
                                            diagnosticTiming?.answerStreamMs
                                          )}
                                        </p>
                                        <p>
                                          <span className="block text-[#72807b]">
                                            总耗时
                                          </span>
                                          {formatDiagnosticTiming(
                                            diagnosticTiming?.chatStreamTotalMs
                                          )}
                                        </p>
                                      </div>
                                    </div>
                                  </div>
                                </div>

                                {diagnostic.vectorDegraded && (
                                  <div className="border border-[#f0b8a8] bg-[#fff1ed] px-3 py-2 text-xs text-[#9b3c29]">
                                    <p>
                                      向量检索发生降级，已尝试使用全文检索兜底。
                                    </p>
                                    {diagnostic.diagnostics.vectorErrors
                                      .length > 0 && (
                                      <ul className="mt-1 list-disc space-y-1 pl-4">
                                        {diagnostic.diagnostics.vectorErrors.map(
                                          (error) => (
                                            <li key={error}>{error}</li>
                                          )
                                        )}
                                      </ul>
                                    )}
                                  </div>
                                )}

                                {diagnostic.sourcesPreview.length > 0 && (
                                  <div className="space-y-2">
                                    <p className="font-utility text-[10px] font-semibold uppercase text-[#64716d]">
                                      Sources 预览
                                    </p>
                                    {diagnostic.sourcesPreview.map(
                                      (source, sourceIndex) => (
                                        <div
                                          key={`${messageKey}-diagnostic-source-${sourceIndex}`}
                                          className="border border-[#d5ded9] bg-[#fcfdfb] px-3 py-2 text-xs text-[#46514e]"
                                        >
                                          <div className="flex flex-wrap items-start justify-between gap-2">
                                            <p className="font-semibold text-[#17201f]">
                                              {source.index !== null
                                                ? `${source.index}. `
                                                : ""}
                                              {source.fileName ||
                                                "未知来源"}
                                            </p>
                                            <p className="font-utility text-[10px] text-[#72807b]">
                                              文件片段{" "}
                                              {source.chunkIndex !== null
                                                ? `#${source.chunkIndex}`
                                                : "—"}
                                            </p>
                                          </div>
                                          <p className="mt-1 text-[#64716d]">
                                            通道：
                                            {source.retrievalSources.length > 0
                                              ? source.retrievalSources.join(
                                                  " + "
                                                )
                                              : "—"}
                                          </p>
                                          <p className="mt-1 text-[#64716d]">
                                            RRF：
                                            {formatDiagnosticScore(
                                              source.rrfScore
                                            )}{" "}
                                            · 向量距离：
                                            {formatDiagnosticScore(
                                              source.vectorScore
                                            )}{" "}
                                            · 文本分：
                                            {formatDiagnosticScore(
                                              source.fulltextScore
                                            )}{" "}
                                            · 相关性：
                                            {formatDiagnosticScore(
                                              source.rerankScore
                                            )}
                                          </p>
                                        </div>
                                      )
                                    )}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        )}

                      {message.role === "assistant" && message.content && (
                        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-[#d6dedb] pt-3">
                          <button
                            type="button"
                            onClick={() =>
                              handleToggleDiagnostics(
                                currentSession.id,
                                messageKey
                              )
                            }
                            className="font-utility text-[10px] font-semibold uppercase text-[#64716d] transition hover:text-[#176b62]"
                          >
                            {isDiagnosticExpanded ? "收起诊断" : "诊断"}
                          </button>
                          <button
                            type="button"
                            onClick={() =>
                              handleCopyMessage(messageKey, message.content)
                            }
                            className="font-utility text-[10px] font-semibold uppercase text-[#64716d] transition hover:text-[#176b62]"
                          >
                            {copiedMessageKey === messageKey
                              ? "Copied"
                              : "Copy Response"}
                          </button>
                        </div>
                      )}
                    </article>
                  </div>
                );
              })}

              {shouldShowThinkingIndicator && (
                <div className="grid gap-3 border-l-2 border-[#176b62] pl-5 md:grid-cols-[74px_minmax(0,1fr)] md:gap-5 md:pl-6">
                  <p className="font-utility pt-1 text-[10px] font-semibold uppercase text-[#72807b]">
                    Response
                  </p>
                  <div className="animate-pulse border border-[#d5ded9] bg-[#f5f8f6] px-5 py-4 text-sm text-[#64716d]">
                    正在检索资料并组织回答...
                  </div>
                </div>
              )}

              {currentSessionError && (
                <div className="border-l-4 border-[#e36b4f] bg-[#fff1ed] px-5 py-4 text-[#9b3c29]">
                  {currentSessionError}
                </div>
              )}

              {pageError && (
                <div className="border-l-4 border-[#e36b4f] bg-[#fff1ed] px-5 py-4 text-[#9b3c29]">
                  {pageError}
                </div>
              )}

              <div ref={bottomRef} />
            </div>
          </div>

          <div className="shrink-0 border-t border-[#cbd5d1] bg-[#eef3f0] px-5 py-5 md:px-8 md:py-6">
            <div className="flex items-center justify-between gap-4">
              <label
                htmlFor="question"
                className="font-utility block text-[10px] font-semibold uppercase text-[#176b62]"
              >
                Add To Research Log
              </label>
              <span className="font-utility text-[10px] text-[#7b8884]">
                Enter 发送 · Shift + Enter 换行
              </span>
            </div>
            <div className="mt-3 flex flex-col gap-3 md:flex-row md:items-end">
              <textarea
                id="question"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (
                    e.key === "Enter" &&
                    !e.shiftKey &&
                    !isCurrentSessionLoading
                  ) {
                    e.preventDefault();
                    void handleSubmit();
                  }
                }}
                placeholder="输入一个需要结合当前知识库回答的问题..."
                className="research-focus min-h-[104px] min-w-0 flex-1 resize-y border border-[#aebdb7] bg-[#fcfdfb] px-4 py-3 text-[#17201f]"
              />

              <button
                onClick={() => {
                  void handleSubmit();
                }}
                disabled={
                  isCurrentSessionLoading ||
                  isCreatingSession ||
                  !selectedKnowledgeBaseId ||
                  selectedKnowledgeBaseId === DEFAULT_KNOWLEDGE_BASE_ID
                }
                className="h-12 shrink-0 bg-[#176b62] px-6 text-sm font-semibold text-white transition hover:bg-[#105149] disabled:bg-[#91aaa4] md:h-[104px] md:w-32"
              >
                {isCreatingSession
                  ? "创建中..."
                  : isCurrentSessionLoading
                    ? "思考中..."
                    : "发送问题"}
              </button>
            </div>
          </div>
        </section>
      </div>

      {isKnowledgeBaseManagerOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-[#17201f]/55 px-4 py-8 backdrop-blur-[2px]"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setIsKnowledgeBaseManagerOpen(false);
            }
          }}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="knowledge-base-manager-title"
            className="research-paper max-h-full w-full max-w-lg overflow-y-auto border border-[#bdcac5]"
          >
            <div className="flex items-center justify-between border-b border-[#cbd5d1] px-6 py-5">
              <div>
                <p className="font-utility text-[10px] font-semibold uppercase text-[#176b62]">
                  Library Index
                </p>
                <h2
                  id="knowledge-base-manager-title"
                  className="font-display mt-2 text-2xl font-semibold text-[#17201f]"
                >
                  知识库管理
                </h2>
                <p className="mt-1 text-sm text-[#64716d]">
                  当前：{selectedKnowledgeBase?.name || "暂无知识库"}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsKnowledgeBaseManagerOpen(false)}
                aria-label="关闭知识库管理"
                className="flex h-9 w-9 items-center justify-center text-xl text-[#64716d] transition hover:bg-[#e1e9e5] hover:text-[#17201f]"
              >
                ×
              </button>
            </div>

            <div className="px-6 py-5">
              <div className="divide-y divide-[#d5ded9] border-y border-[#cbd5d1]">
                {knowledgeBases.map((knowledgeBase) => {
                  const localFileCount = knowledgeBaseFiles.filter(
                    (association) =>
                      association.knowledgeBaseId === knowledgeBase.id
                  ).length;
                  const fileCount =
                    localFileCount || knowledgeBase.fileCount || 0;
                  const conversationCount =
                    sessions.filter(
                      (session) =>
                        session.knowledgeBaseId === knowledgeBase.id
                    ).length;

                  return (
                    <button
                      key={knowledgeBase.id}
                      type="button"
                      onClick={() => {
                        setSelectedKnowledgeBaseId(knowledgeBase.id);
                        setIsKnowledgeBaseManagerOpen(false);
                      }}
                      className="flex w-full items-center justify-between gap-4 px-2 py-4 text-left transition hover:bg-[#eef3f0]"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="truncate text-sm font-semibold text-[#17201f]">
                            {knowledgeBase.name}
                          </p>
                          {knowledgeBase.isDefault && (
                            <span className="font-utility bg-[#e0ebe7] px-1.5 py-0.5 text-[10px] font-semibold text-[#176b62]">
                              默认
                            </span>
                          )}
                        </div>
                        <p className="mt-1 text-xs text-[#72807b]">
                          {fileCount} 个文件 · {conversationCount} 个会话
                        </p>
                      </div>
                      <span className="text-sm font-semibold text-[#176b62]">
                        选择
                      </span>
                    </button>
                  );
                })}
              </div>

              <div className="mt-6 border border-[#cbd5d1] bg-[#f7faf8] px-4 py-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="font-utility text-[10px] font-semibold uppercase text-[#176b62]">
                      Retrieval Policy
                    </p>
                    <h3 className="mt-1 text-sm font-semibold text-[#17201f]">
                      当前知识库检索策略
                    </h3>
                    <p className="mt-1 text-xs leading-5 text-[#72807b]">
                      调整后会影响下一次聊天，不会重建已有向量。
                    </p>
                  </div>
                  {isLoadingRetrievalSettings && (
                    <span className="text-xs text-[#72807b]">读取中...</span>
                  )}
                </div>

                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  <label className="block text-xs font-semibold text-[#46514e]">
                    检索模式
                    <select
                      value={selectedRetrievalSettings.retrievalMode}
                      onChange={(event) =>
                        updateSelectedRetrievalSettings({
                          retrievalMode: event.target.value as RetrievalMode,
                        })
                      }
                      disabled={
                        !selectedKnowledgeBaseId ||
                        selectedKnowledgeBaseId === DEFAULT_KNOWLEDGE_BASE_ID
                      }
                      className="research-focus mt-1 w-full border border-[#b7c4bf] bg-white px-3 py-2 text-sm text-[#17201f]"
                    >
                      <option value="auto">自动判断</option>
                      <option value="always">强制检索</option>
                      <option value="never">永不检索</option>
                    </select>
                  </label>

                  <label className="block text-xs font-semibold text-[#46514e]">
                    引用阈值
                    <input
                      type="number"
                      step="0.1"
                      min="-20"
                      max="20"
                      value={selectedRetrievalSettings.rerankScoreThreshold}
                      onChange={(event) =>
                        updateSelectedRetrievalSettings({
                          rerankScoreThreshold: Number(event.target.value),
                        })
                      }
                      className="research-focus mt-1 w-full border border-[#b7c4bf] bg-white px-3 py-2 text-sm text-[#17201f]"
                    />
                  </label>

                  <label className="flex items-center gap-2 text-xs font-semibold text-[#46514e]">
                    <input
                      type="checkbox"
                      checked={selectedRetrievalSettings.enableQueryRouter}
                      onChange={(event) =>
                        updateSelectedRetrievalSettings({
                          enableQueryRouter: event.target.checked,
                        })
                      }
                      className="h-4 w-4 accent-[#176b62]"
                    />
                    启用 Query Router
                  </label>

                  <label className="flex items-center gap-2 text-xs font-semibold text-[#46514e]">
                    <input
                      type="checkbox"
                      checked={selectedRetrievalSettings.enableRerank}
                      onChange={(event) =>
                        updateSelectedRetrievalSettings({
                          enableRerank: event.target.checked,
                        })
                      }
                      className="h-4 w-4 accent-[#176b62]"
                    />
                    启用 Rerank 精排
                  </label>
                </div>

                <div className="mt-3 grid gap-3 md:grid-cols-4">
                  {[
                    ["topK", "最终引用", 1, 20],
                    ["vectorTopK", "Vector 召回", 1, 100],
                    ["fulltextTopK", "Fulltext 召回", 1, 100],
                    ["rrfK", "RRF 候选", 1, 100],
                  ].map(([field, label, min, max]) => (
                    <label
                      key={field}
                      className="block text-xs font-semibold text-[#46514e]"
                    >
                      {label}
                      <input
                        type="number"
                        min={min}
                        max={max}
                        value={
                          selectedRetrievalSettings[
                            field as keyof KnowledgeBaseRetrievalSettings
                          ] as number
                        }
                        onChange={(event) =>
                          updateSelectedRetrievalSettings({
                            [field]: Number(event.target.value),
                          } as Partial<KnowledgeBaseRetrievalSettings>)
                        }
                        className="research-focus mt-1 w-full border border-[#b7c4bf] bg-white px-2 py-2 text-sm text-[#17201f]"
                      />
                    </label>
                  ))}
                </div>

                {retrievalSettingsMessage && (
                  <p className="mt-3 border-l-4 border-[#176b62] bg-[#edf7f3] px-3 py-2 text-xs text-[#176b62]">
                    {retrievalSettingsMessage}
                  </p>
                )}

                {retrievalSettingsError && (
                  <p className="mt-3 border-l-4 border-[#e36b4f] bg-[#fff1ed] px-3 py-2 text-xs text-[#9b3c29]">
                    {retrievalSettingsError}
                  </p>
                )}

                <button
                  type="button"
                  onClick={() => {
                    void handleSaveRetrievalSettings();
                  }}
                  disabled={
                    !selectedKnowledgeBaseId ||
                    selectedKnowledgeBaseId === DEFAULT_KNOWLEDGE_BASE_ID ||
                    isSavingRetrievalSettings
                  }
                  className="mt-4 w-full bg-[#176b62] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#105149] disabled:bg-[#a7b8b2]"
                >
                  {isSavingRetrievalSettings ? "保存中..." : "保存检索设置"}
                </button>
              </div>

              <div className="mt-6">
                <label
                  htmlFor="new-knowledge-base-name"
                  className="font-utility block text-[10px] font-semibold uppercase text-[#72807b]"
                >
                  新建知识库
                </label>
                <div className="mt-2 flex gap-2">
                  <input
                    id="new-knowledge-base-name"
                    value={newKnowledgeBaseName}
                    onChange={(event) =>
                      setNewKnowledgeBaseName(event.target.value)
                    }
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        void handleCreateKnowledgeBase();
                      }
                    }}
                    placeholder="知识库名称"
                    className="research-focus min-w-0 flex-1 border border-[#b7c4bf] bg-white px-3 py-2.5 text-sm text-[#17201f]"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      void handleCreateKnowledgeBase();
                    }}
                    disabled={
                      !newKnowledgeBaseName.trim() ||
                      isCreatingKnowledgeBase
                    }
                    className="bg-[#176b62] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#105149] disabled:bg-[#a7b8b2]"
                  >
                    {isCreatingKnowledgeBase ? "创建中..." : "创建"}
                  </button>
                </div>
              </div>
            </div>
          </section>
        </div>
      )}

      {isFileManagerOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-[#17201f]/55 px-4 py-8 backdrop-blur-[2px]"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setIsFileManagerOpen(false);
            }
          }}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="file-manager-title"
            className="research-paper max-h-full w-full max-w-xl overflow-y-auto border border-[#bdcac5]"
          >
            <div className="flex items-center justify-between border-b border-[#cbd5d1] px-6 py-5">
              <div>
                <p className="font-utility text-[10px] font-semibold uppercase text-[#176b62]">
                  Source Material
                </p>
                <h2
                  id="file-manager-title"
                  className="font-display mt-2 text-2xl font-semibold text-[#17201f]"
                >
                  知识库文件
                </h2>
                <p className="mt-1 text-sm text-[#64716d]">
                  {selectedKnowledgeBase?.name || "暂无知识库"}
                </p>
                <p className="mt-1 text-xs text-[#72807b]">
                  文件只保存一次，可关联到多个知识库
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsFileManagerOpen(false)}
                aria-label="关闭文件管理"
                className="flex h-9 w-9 items-center justify-center text-xl text-[#64716d] transition hover:bg-[#e1e9e5] hover:text-[#17201f]"
              >
                ×
              </button>
            </div>

            <div className="px-6 py-5">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={
                  !selectedKnowledgeBaseId || isUploadingKnowledgeFiles
                }
                className="w-full border border-dashed border-[#9bada6] bg-[#eef3f0] px-4 py-5 text-sm font-semibold text-[#46514e] transition hover:border-[#176b62] hover:text-[#176b62] disabled:border-[#cbd5d1] disabled:text-[#9ba8a3]"
              >
                {isUploadingKnowledgeFiles
                  ? "正在上传并登记文件..."
                  : selectedKnowledgeBaseId
                    ? "选择文件上传"
                    : "请先创建知识库"}
              </button>

              <button
                type="button"
                onClick={() => {
                  void handleIndexKnowledgeBase();
                }}
                disabled={
                  selectedKnowledgeFiles.length === 0 ||
                  isIndexingKnowledgeBase ||
                  isUploadingKnowledgeFiles
                }
                className="mt-3 w-full border border-[#176b62] bg-[#fcfdfb] px-4 py-3 text-sm font-semibold text-[#176b62] transition hover:bg-[#e4f0ec] disabled:border-[#cbd5d1] disabled:text-[#9ba8a3]"
              >
                {isIndexingKnowledgeBase
                  ? "知识库向量化中..."
                  : "向量化当前知识库"}
              </button>

              {knowledgeFileUploadError && (
                <p
                  role="alert"
                  className="mt-3 border-l-4 border-[#e36b4f] bg-[#fff1ed] px-4 py-3 text-sm text-[#9b3c29]"
                >
                  {knowledgeFileUploadError}
                </p>
              )}

              {knowledgeFileDetachError && (
                <p
                  role="alert"
                  className="mt-3 border-l-4 border-[#e36b4f] bg-[#fff1ed] px-4 py-3 text-sm text-[#9b3c29]"
                >
                  {knowledgeFileDetachError}
                </p>
              )}

              {knowledgeFileAttachError && (
                <p
                  role="alert"
                  className="mt-3 border-l-4 border-[#e36b4f] bg-[#fff1ed] px-4 py-3 text-sm text-[#9b3c29]"
                >
                  {knowledgeFileAttachError}
                </p>
              )}

              {knowledgeFileLoadError && (
                <p
                  role="alert"
                  className="mt-3 border-l-4 border-[#e36b4f] bg-[#fff1ed] px-4 py-3 text-sm text-[#9b3c29]"
                >
                  {knowledgeFileLoadError}
                </p>
              )}

              {reusableFileLoadError && (
                <p
                  role="alert"
                  className="mt-3 border-l-4 border-[#e36b4f] bg-[#fff1ed] px-4 py-3 text-sm text-[#9b3c29]"
                >
                  {reusableFileLoadError}
                </p>
              )}

              {vectorIndexMessage && (
                <p className="mt-3 border-l-4 border-[#176b62] bg-[#edf7f3] px-4 py-3 text-sm text-[#176b62]">
                  {vectorIndexMessage}
                </p>
              )}

              {vectorIndexError && (
                <p
                  role="alert"
                  className="mt-3 border-l-4 border-[#e36b4f] bg-[#fff1ed] px-4 py-3 text-sm text-[#9b3c29]"
                >
                  {vectorIndexError}
                </p>
              )}

              <div className="mt-6 border border-[#cbd5d1] bg-[#f7faf8]">
                <div className="flex items-center justify-between gap-4 border-b border-[#d5ded9] px-4 py-3">
                  <div>
                    <p className="font-utility text-[10px] font-semibold uppercase text-[#176b62]">
                      任务队列
                    </p>
                    <p className="mt-1 text-xs text-[#72807b]">
                      {isLoadingVectorIndexHealth
                        ? "正在读取任务状态..."
                        : workerHealthLabel.label}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-utility text-[10px] text-[#72807b]">
                      {String(vectorQueueCount).padStart(2, "0")}
                    </span>
                    {vectorIndexQueue.some(isVectorIndexJobDone) && (
                      <button
                        type="button"
                        onClick={() => {
                          setVectorIndexQueue((prev) =>
                            prev.filter((job) => !isVectorIndexJobDone(job))
                          );
                        }}
                        className="text-xs font-semibold text-[#72807b] underline decoration-[#d9aa2f] underline-offset-4 transition hover:text-[#176b62]"
                      >
                        清除完成
                      </button>
                    )}
                  </div>
                </div>

                <div className="border-b border-[#d5ded9] px-4 py-3">
                  <div
                    className={`border px-3 py-2 text-xs ${getWorkerHealthToneClass(
                      workerHealthLabel.tone
                    )}`}
                  >
                    <p className="font-semibold">{workerHealthLabel.label}</p>
                    {vectorIndexHealth && (
                      <p className="mt-1 text-[11px]">
                        {getQueueStatusLabel(vectorIndexHealth.queue.status)} · 排队{" "}
                        {vectorIndexHealth.queue.queued} · 处理中{" "}
                        {vectorIndexHealth.queue.processing} · 失败{" "}
                        {vectorIndexHealth.queue.failed} · 已完成{" "}
                        {vectorIndexHealth.queue.succeeded}
                      </p>
                    )}
                    {vectorIndexHealth?.worker.hint && (
                      <p className="mt-2 font-semibold">
                        {vectorIndexHealth.worker.hint}
                      </p>
                    )}
                    {vectorIndexHealth &&
                      vectorIndexHealth.worker.oldestActiveSeconds !== null && (
                      <p className="mt-1 text-[11px]">
                        最老活跃任务已等待{" "}
                        {formatDurationSeconds(
                          vectorIndexHealth.worker.oldestActiveSeconds
                        )}
                      </p>
                    )}
                  </div>
                </div>

                {vectorIndexQueue.length > 0 ? (
                  <div className="divide-y divide-[#d5ded9]">
                    {vectorIndexQueue.map((job) => {
                      const isFailed = job.status === "failed";
                      const isSucceeded = job.status === "succeeded";

                      return (
                        <div
                          key={job.id}
                          className="flex items-start justify-between gap-4 px-4 py-3"
                        >
                          <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-[#17201f]">
                              {job.targetName}
                            </p>
                            <p className="mt-1 font-utility text-[10px] uppercase text-[#72807b]">
                              {job.targetType === "file" ? "File" : "Knowledge Base"} ·{" "}
                              {job.id.slice(0, 8)}
                            </p>
                            {job.errorMessage && (
                              <p className="mt-2 text-xs text-[#9b3c29]">
                                {job.errorMessage}
                              </p>
                            )}
                            {job.failureHint && (
                              <p className="mt-1 text-xs font-semibold text-[#9b3c29]">
                                {job.failureHint}
                              </p>
                            )}
                          </div>
                          <span
                            className={`shrink-0 border px-2 py-1 text-xs font-semibold ${
                              isFailed
                                ? "border-[#e36b4f] bg-[#fff1ed] text-[#9b3c29]"
                                : isSucceeded
                                  ? "border-[#176b62] bg-[#edf7f3] text-[#176b62]"
                                  : "border-[#d9aa2f] bg-[#fff7df] text-[#7a5a12]"
                            }`}
                          >
                            {getVectorIndexStatusText(job.status)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="px-4 py-5 text-center text-sm text-[#72807b]">
                    暂无向量化任务
                  </p>
                )}
              </div>

              <div className="mt-6">
                <div className="flex items-center justify-between gap-4">
                  <p className="font-utility text-[10px] font-semibold uppercase text-[#176b62]">
                    当前知识库
                  </p>
                  <span className="font-utility text-[10px] text-[#72807b]">
                    {String(selectedKnowledgeFiles.length).padStart(2, "0")}
                  </span>
                </div>

                <div className="mt-2 divide-y divide-[#d5ded9] border-y border-[#cbd5d1]">
                  {isLoadingKnowledgeFiles ? (
                    <p className="py-7 text-center text-sm text-[#64716d]">
                      正在读取文件...
                    </p>
                  ) : selectedKnowledgeFiles.length > 0 ? (
                    selectedKnowledgeFiles.map((file) => {
                      const isFileIndexing = Boolean(
                        vectorIndexingFileIds[file.id]
                      );
                      const vectorStatus = getVectorStatus(file);

                      return (
                        <div
                          key={file.id}
                          className="flex items-center justify-between gap-4 py-4"
                        >
                          <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-[#17201f]">
                              {file.name}
                            </p>
                            <p className="mt-1 text-xs text-[#72807b]">
                              {formatFileSize(file.size)} ·{" "}
                              {vectorStatus.label}
                            </p>
                            {vectorStatus.errorMessage && (
                              <p className="mt-1 text-xs text-[#9b3c29]">
                                {vectorStatus.errorMessage}
                              </p>
                            )}
                            {vectorStatus.failureHint && (
                              <p className="mt-1 text-xs font-semibold text-[#9b3c29]">
                                {vectorStatus.failureHint}
                              </p>
                            )}
                            {vectorStatus.workerHint && (
                              <p className="mt-1 text-xs font-semibold text-[#9b3c29]">
                                {vectorStatus.workerHint}
                              </p>
                            )}
                          </div>
                          <div className="flex shrink-0 items-center gap-2">
                            {vectorStatus.canDeleteVector && (
                              <button
                                type="button"
                                onClick={() => {
                                  void handleDeleteKnowledgeFileVectors(file.id);
                                }}
                                disabled={
                                  isFileIndexing ||
                                  isIndexingKnowledgeBase ||
                                  Boolean(deletingVectorFileId)
                                }
                                className="px-2 py-1 text-xs font-semibold text-[#9b3c29] transition hover:bg-[#fff1ed] disabled:cursor-not-allowed disabled:text-[#aab3b0]"
                              >
                                {deletingVectorFileId === file.id
                                  ? "删除向量中..."
                                  : "删除向量"}
                              </button>
                            )}
                            <button
                              type="button"
                              onClick={() => {
                                void handleIndexKnowledgeFile(file.id);
                              }}
                              disabled={
                                isFileIndexing ||
                                !vectorStatus.canVectorize ||
                                isIndexingKnowledgeBase
                              }
                              className="px-2 py-1 text-xs font-semibold text-[#176b62] transition hover:bg-[#e4f0ec] disabled:cursor-not-allowed disabled:text-[#aab3b0]"
                            >
                              {isFileIndexing || vectorStatus.canPoll
                                ? "向量化中..."
                                : vectorStatus.type === "failed"
                                  ? "重新向量化"
                                  : "向量化"}
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                void handleRemoveKnowledgeFile(file.id);
                              }}
                              disabled={Boolean(detachingKnowledgeFileId)}
                              className="px-2 py-1 text-xs font-semibold text-[#72807b] transition hover:bg-[#fff1ed] hover:text-[#9b3c29] disabled:cursor-not-allowed disabled:text-[#aab3b0]"
                            >
                              {detachingKnowledgeFileId === file.id
                                ? "解除中..."
                                : "解除关联"}
                            </button>
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <div className="py-7 text-center">
                      <p className="text-sm text-[#64716d]">
                        当前知识库还没有文件
                      </p>
                      <p className="mt-1 text-xs text-[#8a9692]">
                        上传新文件，或从下方文件库添加
                      </p>
                    </div>
                  )}
                </div>
              </div>

              <div className="mt-7">
                <div className="flex items-center justify-between gap-4">
                  <p className="font-utility text-[10px] font-semibold uppercase text-[#72807b]">
                    可复用文件
                  </p>
                  <span className="font-utility text-[10px] text-[#72807b]">
                    {String(reusableKnowledgeFiles.length).padStart(2, "0")}
                  </span>
                </div>

                <div className="mt-2 divide-y divide-[#d5ded9] border-y border-[#cbd5d1]">
                  {isLoadingReusableFiles ? (
                    <p className="py-7 text-center text-sm text-[#64716d]">
                      正在读取可复用文件...
                    </p>
                  ) : reusableKnowledgeFiles.length > 0 ? (
                    reusableKnowledgeFiles.map((file) => {
                      const isFileIndexing = Boolean(
                        vectorIndexingFileIds[file.id]
                      );
                      const vectorStatus = getVectorStatus(file);

                      return (
                        <div
                          key={file.id}
                          className="flex items-center justify-between gap-4 py-4"
                        >
                          <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-[#17201f]">
                              {file.name}
                            </p>
                            <p className="mt-1 text-xs text-[#72807b]">
                              {formatFileSize(file.size)} ·{" "}
                              {vectorStatus.label}
                            </p>
                            {vectorStatus.errorMessage && (
                              <p className="mt-1 text-xs text-[#9b3c29]">
                                {vectorStatus.errorMessage}
                              </p>
                            )}
                            {vectorStatus.failureHint && (
                              <p className="mt-1 text-xs font-semibold text-[#9b3c29]">
                                {vectorStatus.failureHint}
                              </p>
                            )}
                            {vectorStatus.workerHint && (
                              <p className="mt-1 text-xs font-semibold text-[#9b3c29]">
                                {vectorStatus.workerHint}
                              </p>
                            )}
                          </div>
                          <div className="flex shrink-0 items-center gap-2">
                            {vectorStatus.canDeleteVector && (
                              <button
                                type="button"
                                onClick={() => {
                                  void handleDeleteKnowledgeFileVectors(file.id);
                                }}
                                disabled={
                                  isFileIndexing ||
                                  isIndexingKnowledgeBase ||
                                  Boolean(deletingVectorFileId)
                                }
                                className="px-2 py-1 text-xs font-semibold text-[#9b3c29] transition hover:bg-[#fff1ed] disabled:cursor-not-allowed disabled:text-[#aab3b0]"
                              >
                                {deletingVectorFileId === file.id
                                  ? "删除向量中..."
                                  : "删除向量"}
                              </button>
                            )}
                            <button
                              type="button"
                              onClick={() => {
                                void handleIndexKnowledgeFile(file.id);
                              }}
                              disabled={
                                isFileIndexing ||
                                !vectorStatus.canVectorize ||
                                isIndexingKnowledgeBase
                              }
                              className="px-2 py-1 text-xs font-semibold text-[#176b62] transition hover:bg-[#e4f0ec] disabled:cursor-not-allowed disabled:text-[#aab3b0]"
                            >
                              {isFileIndexing || vectorStatus.canPoll
                                ? "向量化中..."
                                : vectorStatus.type === "failed"
                                  ? "重新向量化"
                                  : "向量化"}
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                void handleAttachKnowledgeFile(file.id);
                              }}
                              disabled={Boolean(attachingKnowledgeFileId)}
                              className="bg-[#176b62] px-3 py-2 text-xs font-semibold text-white transition hover:bg-[#105149] disabled:cursor-not-allowed disabled:bg-[#91aaa4]"
                            >
                              {attachingKnowledgeFileId === file.id
                                ? "添加中..."
                                : "添加"}
                            </button>
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <p className="py-7 text-center text-sm text-[#72807b]">
                      暂无其他可复用文件
                    </p>
                  )}
                </div>
              </div>
            </div>
          </section>
        </div>
      )}

      <button
        onClick={() => {
          if (window.matchMedia("(min-width: 1024px)").matches) {
            messagesContainerRef.current?.scrollTo({
              top: 0,
              behavior: "smooth",
            });
            return;
          }

          window.scrollTo({ top: 0, behavior: "smooth" });
        }}
        className="font-utility fixed bottom-5 right-5 border border-[#9bada6] bg-[#fcfdfb] px-3 py-2 text-[10px] font-semibold uppercase text-[#46514e] shadow-sm transition hover:border-[#176b62] hover:text-[#176b62]"
      >
        Top ↑
      </button>
    </main>
  );
}
