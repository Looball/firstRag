import {
  DEFAULT_RETRIEVAL_SETTINGS,
  LEGACY_INITIAL_MESSAGE,
} from "./constants";
import type {
  BackendConversation,
  BackendKnowledgeBase,
  BackendKnowledgeFile,
  ChatSession,
  ChatSource,
  KnowledgeBase,
  KnowledgeBaseRetrievalSettings,
  KnowledgeFile,
  KnowledgeFileStatus,
  LatestIndexJob,
  LatestIndexJobStatus,
  Message,
  MessageAttachment,
  MessageFeedback,
  MessageFeedbackRating,
  MessageFeedbackReason,
  MessageDiagnostic,
  MessageSourceFeedback,
  MessageSourceFeedbackRating,
  QualityDashboard,
  RetrievalDiagnostics,
  RetrievalMode,
  RetrievalState,
  SourcePreview,
  VectorIndexHealthResponse,
  VectorIndexJob,
  VectorIndexJobStatus,
  VectorIndexResponse,
  VectorStatus,
  WorkerHealthDetails,
  WorkerHealthTone,
} from "./types";

export function isAuthExpiredMessage(message: string) {
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


export function formatFileSize(size: number) {
  if (size < 1024) {
    return `${size} B`;
  }

  if (size < 1024 * 1024) {
    return `${Math.round(size / 1024)} KB`;
  }

  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}


export function formatDurationSeconds(seconds: number | null) {
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


export function formatDateTimeText(value: string | null) {
  if (!value) {
    return "未知";
  }

  const match = value.match(
    /^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})(?::(\d{2}))?/
  );

  if (!match) {
    return value;
  }

  const [, year, month, day, hour, minute, second = "00"] = match;
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
}


export function getFileFingerprint(file: File) {
  return `${file.name}:${file.size}:${file.lastModified}`;
}


export function buildSessionTitle(input: string) {
  const normalized = input.replace(/\s+/g, " ").trim();

  if (!normalized) {
    return "新对话";
  }

  return normalized.length > 24 ? `${normalized.slice(0, 24)}...` : normalized;
}


const MESSAGE_FEEDBACK_RATINGS = new Set<MessageFeedbackRating>([
  "positive",
  "negative",
]);

const MESSAGE_FEEDBACK_REASONS = new Set<MessageFeedbackReason>([
  "irrelevant_sources",
  "missing_answer",
  "hallucination",
  "outdated_or_wrong",
  "too_slow",
  "format_issue",
  "other",
]);

const MESSAGE_SOURCE_FEEDBACK_RATINGS = new Set<MessageSourceFeedbackRating>([
  "useful",
  "irrelevant",
]);

export function toMessageFeedback(value: unknown): MessageFeedback | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }

  const candidate = value as Record<string, unknown>;
  const rating = candidate.rating;

  if (
    typeof rating !== "string" ||
    !MESSAGE_FEEDBACK_RATINGS.has(rating as MessageFeedbackRating)
  ) {
    return null;
  }

  const reason = candidate.reason;
  const note = candidate.note;

  return {
    ...(typeof candidate.id === "string" ? { id: candidate.id } : {}),
    rating: rating as MessageFeedbackRating,
    reason:
      typeof reason === "string" &&
      MESSAGE_FEEDBACK_REASONS.has(reason as MessageFeedbackReason)
        ? (reason as MessageFeedbackReason)
        : null,
    note: typeof note === "string" ? note : null,
  };
}


export function toMessageSourceFeedback(
  value: unknown,
): MessageSourceFeedback | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }

  const candidate = value as Record<string, unknown>;
  const rating = candidate.rating;
  const sourceIndex = getOptionalNumberField(candidate, ["source_index"]);

  if (
    typeof rating !== "string" ||
    !MESSAGE_SOURCE_FEEDBACK_RATINGS.has(rating as MessageSourceFeedbackRating) ||
    sourceIndex === undefined
  ) {
    return null;
  }

  return {
    ...(typeof candidate.id === "string" ? { id: candidate.id } : {}),
    sourceIndex,
    knowledgeFileId:
      typeof candidate.knowledge_file_id === "string"
        ? candidate.knowledge_file_id
        : null,
    chunkIndex: getOptionalNumberField(candidate, ["chunk_index"]) ?? null,
    rating: rating as MessageSourceFeedbackRating,
    note: typeof candidate.note === "string" ? candidate.note : null,
  };
}

export function resolveChatAttachmentContentUrl(value: string) {
  if (!value) {
    return "";
  }
  if (value.startsWith("/api/")) {
    return value;
  }
  if (value.startsWith("/chat/")) {
    return `/api${value}`;
  }
  return value;
}


export function toMessageAttachment(value: unknown): MessageAttachment | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }

  const candidate = value as Record<string, unknown>;
  const id = typeof candidate.id === "string" ? candidate.id : "";
  const originalName =
    typeof candidate.original_name === "string"
      ? candidate.original_name
      : typeof candidate.originalName === "string"
        ? candidate.originalName
        : "";
  const mimeType =
    typeof candidate.mime_type === "string"
      ? candidate.mime_type
      : typeof candidate.mimeType === "string"
        ? candidate.mimeType
        : "";
  const sizeBytes =
    typeof candidate.size_bytes === "number"
      ? candidate.size_bytes
      : typeof candidate.sizeBytes === "number"
        ? candidate.sizeBytes
        : 0;
  const contentUrl = resolveChatAttachmentContentUrl(
    typeof candidate.content_url === "string"
      ? candidate.content_url
      : typeof candidate.contentUrl === "string"
        ? candidate.contentUrl
        : "",
  );

  if (!id || !mimeType || !contentUrl) {
    return null;
  }

  return {
    id,
    originalName: originalName || "图片附件",
    mimeType,
    sizeBytes,
    contentUrl,
    createdAt:
      typeof candidate.created_at === "string"
        ? candidate.created_at
        : typeof candidate.createdAt === "string"
          ? candidate.createdAt
          : undefined,
  };
}


export function toMessage(value: unknown): Message | null {
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
  const feedback = toMessageFeedback(candidate.feedback);
  const attachments = Array.isArray(candidate.attachments)
    ? candidate.attachments
        .map(toMessageAttachment)
        .filter((attachment): attachment is MessageAttachment => attachment !== null)
    : [];

  return {
    ...(id ? { id } : {}),
    role,
    content: candidate.content,
    ...(status ? { status } : {}),
    ...(errorMessage !== undefined ? { errorMessage } : {}),
    ...(attachments.length > 0 ? { attachments } : {}),
    ...(sources.length > 0 ? { sources } : {}),
    ...(retrieval ? { retrieval } : {}),
    ...(feedback ? { feedback } : {}),
  };
}


export function toMessages(values: unknown[]) {
  return values
    .map(toMessage)
    .filter((message): message is Message => message !== null);
}


export function getAssistantContent(value: unknown) {
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


export function getAssistantMessageId(value: unknown) {
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


export function parseJsonValue(value: string) {
  try {
    return JSON.parse(value) as unknown;
  } catch {
    return value;
  }
}


export function getNumberField(value: Record<string, unknown>, fieldName: string) {
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


export function getOptionalNumberField(
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


export function getNullableNumberField(
  value: Record<string, unknown>,
  fieldNames: string[]
) {
  const numberValue = getOptionalNumberField(value, fieldNames);

  return numberValue === undefined ? null : numberValue;
}


export function getNullableStringField(
  value: Record<string, unknown>,
  fieldNames: string[]
) {
  const stringValue = getStringField(value, fieldNames);

  return stringValue || null;
}


export function getNullableBooleanField(
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


export function getRetrievalState(value: unknown): RetrievalState | undefined {
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


export function getStringField(
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


export function getRecordField(
  value: Record<string, unknown>,
  fieldName: string
): Record<string, unknown> | null {
  const fieldValue = value[fieldName];

  return typeof fieldValue === "object" && fieldValue !== null
    ? (fieldValue as Record<string, unknown>)
    : null;
}


export function getStringArrayField(value: Record<string, unknown>, fieldName: string) {
  const fieldValue = value[fieldName];

  return Array.isArray(fieldValue)
    ? fieldValue
        .filter((item): item is string => typeof item === "string")
        .map((item) => item.trim())
        .filter(Boolean)
    : [];
}


export function toSourcePreview(value: unknown): SourcePreview | null {
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


export function getSourcesPreview(value: Record<string, unknown>) {
  const sourcesPreview = value.sources_preview;

  return Array.isArray(sourcesPreview)
    ? sourcesPreview
        .map(toSourcePreview)
        .filter((source): source is SourcePreview => source !== null)
    : [];
}


export function getRetrievalDiagnostics(
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


export function toMessageDiagnostic(value: unknown): MessageDiagnostic | null {
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


export function getConversationDiagnostics(value: unknown) {
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


function toCountList(
  values: unknown,
  labelField: string,
): Array<{ label: string; count: number }> {
  if (!Array.isArray(values)) {
    return [];
  }

  return values
    .map((value) => {
      if (typeof value !== "object" || value === null) {
        return null;
      }

      const item = value as Record<string, unknown>;
      const label = getStringField(item, [labelField]);
      const count = getNumberField(item, "count");

      return label ? { label, count } : null;
    })
    .filter((item): item is { label: string; count: number } => item !== null);
}


export function toQualityDashboard(value: unknown): QualityDashboard | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }

  const data = value as Record<string, unknown>;
  const messageFeedback = getRecordField(data, "message_feedback") || {};
  const sourceFeedback = getRecordField(data, "source_feedback") || {};
  const retrieval = getRecordField(data, "retrieval") || {};

  return {
    windowDays: getNumberField(data, "window_days") || 7,
    hasFeedback: Boolean(data.has_feedback),
    messageFeedback: {
      total: getNumberField(messageFeedback, "total"),
      positive: getNumberField(messageFeedback, "positive"),
      negative: getNumberField(messageFeedback, "negative"),
      negativeRate: getNullableNumberField(messageFeedback, ["negative_rate"]),
      reasonDistribution: toCountList(
        messageFeedback.reason_distribution,
        "reason",
      ).map((item) => ({
        reason: item.label,
        count: item.count,
      })),
    },
    sourceFeedback: {
      total: getNumberField(sourceFeedback, "total"),
      useful: getNumberField(sourceFeedback, "useful"),
      irrelevant: getNumberField(sourceFeedback, "irrelevant"),
      irrelevantRate: getNullableNumberField(sourceFeedback, [
        "irrelevant_rate",
      ]),
      topIrrelevantFiles: toCountList(
        sourceFeedback.top_irrelevant_files,
        "file_name",
      ).map((item) => ({
        fileName: item.label,
        count: item.count,
      })),
    },
    retrieval: {
      assistantMessages: getNumberField(retrieval, "assistant_messages"),
      averageSources: getNullableNumberField(retrieval, ["average_sources"]),
      averageFirstTokenMs: getNullableNumberField(retrieval, [
        "average_first_token_ms",
      ]),
    },
  };
}


export function formatDiagnosticScore(value?: number | null) {
  return typeof value === "number" && Number.isFinite(value)
    ? value.toFixed(4)
    : "—";
}


export function formatDiagnosticCount(value: number | null) {
  return value === null ? "—" : String(value);
}


export function formatDiagnosticValue(value?: string | number | null) {
  if (typeof value === "number") {
    return Number.isFinite(value) ? String(value) : "—";
  }

  return value ? value : "—";
}


export function formatDiagnosticTiming(value?: number | null) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "—";
  }

  if (value >= 1000) {
    return `${(value / 1000).toFixed(2)}s`;
  }

  return `${value.toFixed(value >= 10 ? 0 : 2)}ms`;
}


export function formatRetrievalDecision(value?: boolean | null) {
  if (value === null || value === undefined) {
    return "未知";
  }

  return value ? "检索" : "不检索";
}


export function toChatSource(value: unknown, index: number): ChatSource | null {
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
  const indexVersion = getOptionalNumberField(source, ["index_version"]);
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
  const feedback = toMessageSourceFeedback(source.feedback);
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
    ...(indexVersion !== undefined ? { indexVersion } : {}),
    ...(vectorScore !== undefined ? { vectorScore } : {}),
    ...(fulltextScore !== undefined ? { fulltextScore } : {}),
    ...(rerankScore !== undefined ? { rerankScore } : {}),
    ...(rrfScore !== undefined ? { rrfScore } : {}),
    ...(retrievalSources.length > 0 ? { retrievalSources } : {}),
    ...(feedback ? { feedback } : {}),
  };
}


export function hasSourceShape(value: Record<string, unknown>) {
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
    "index_version",
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


export function getChatSources(value: unknown) {
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


export function parseSseBlock(block: string) {
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


export function getSseAnswerContent(data: string) {
  const parsedData = parseJsonValue(data);
  const answer = getAssistantContent(parsedData);

  return answer || (typeof parsedData === "string" ? parsedData : "");
}


export function removeLegacyInitialMessage(messages: Message[]) {
  if (
    messages[0]?.role === "assistant" &&
    messages[0].content === LEGACY_INITIAL_MESSAGE
  ) {
    return messages.slice(1);
  }

  return messages;
}


export function toChatSession(
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


export function toKnowledgeBase(value: unknown): KnowledgeBase | null {
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


export function getRetrievalMode(value: unknown): RetrievalMode {
  return value === "always" || value === "never" || value === "auto"
    ? value
    : DEFAULT_RETRIEVAL_SETTINGS.retrievalMode;
}


export function getBoundedNumber(
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


export function toRetrievalSettings(
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


export function serializeRetrievalSettings(
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


export function toKnowledgeFile(
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
    reused: knowledgeFile.reused === true,
    alreadyInKnowledgeBase: knowledgeFile.already_in_knowledge_base === true,
  };
}


export function toLatestIndexJob(value: unknown): LatestIndexJob | null {
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


export function getLatestIndexJobStatus(value: unknown): LatestIndexJobStatus {
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


export function getKnowledgeFileStatus(value: unknown): KnowledgeFileStatus {
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


export function getVectorFailureRecoveryActions(
  failureType: string | null,
  canRetry: boolean
) {
  const retryAction = canRetry ? ["重新向量化"] : [];

  if (failureType === "unsupported_file_type") {
    return [
      "请改用 PDF、DOCX、Markdown、TXT、PNG、JPEG 或 WebP 文件",
      "替换文件后重新上传",
      ...retryAction,
    ];
  }

  if (failureType === "empty_document") {
    return [
      "确认文件不是空文件",
      "转为可复制文本后重新上传",
      ...retryAction,
    ];
  }

  if (failureType === "image_parse_error") {
    return [
      "在模型设置中选择支持 vision 的聊天模型",
      "确认图片文字清晰后重新向量化",
    ];
  }

  if (failureType === "parse_error") {
    return [
      "确认文件可打开且内容可复制",
      "必要时转为 PDF、Markdown、TXT 或支持的图片格式后重新上传",
      ...retryAction,
    ];
  }

  if (failureType === "embedding_error") {
    return [
      "检查 embedding provider 的 API Key、额度和网络",
      "确认后重试向量化",
    ];
  }

  if (failureType === "vector_store_error") {
    return [
      "确认 Chroma/vector_db 可写",
      "清理残留向量后重新向量化",
    ];
  }

  if (failureType === "chunk_write_error") {
    return [
      "检查 PostgreSQL chunk 表和迁移状态",
      "修复数据库后重新向量化",
    ];
  }

  if (failureType === "database_error") {
    return [
      "检查 PostgreSQL 连接和迁移状态",
      "数据库恢复后重新向量化",
    ];
  }

  if (failureType === "task_timeout") {
    return [
      "查看 worker 日志和文件大小",
      "必要时重启 worker 后重新向量化",
    ];
  }

  if (failureType === "stale_job") {
    return ["任务版本已过期，可直接重新向量化"];
  }

  if (failureType === "unknown_error") {
    return [
      "查看错误信息和 worker 日志",
      "确认模型配置、文件内容和服务状态后重新向量化",
    ];
  }

  return retryAction;
}


function getVectorWorkerRecoveryActions(
  status: LatestIndexJobStatus,
  workerHint?: string | null,
) {
  if (!workerHint) {
    return [];
  }

  if (status === "queued") {
    return ["确认 vector index worker 已启动", "启动后刷新任务状态"];
  }

  if (status === "processing") {
    return ["查看 worker 日志确认是否卡住", "必要时重启 worker 后重新向量化"];
  }

  return [];
}


export function getVectorStatus(file: KnowledgeFile): VectorStatus {
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
    const recoveryActions = getVectorWorkerRecoveryActions(
      job.status,
      job.workerHint
    );

    return {
      label: "排队中",
      type: "pending",
      canVectorize: false,
      canDeleteVector: false,
      canPoll: true,
      ...(job.workerHint ? { workerHint: job.workerHint } : {}),
      ...(recoveryActions.length > 0 ? { recoveryActions } : {}),
    };
  }

  if (job.status === "processing") {
    const recoveryActions = getVectorWorkerRecoveryActions(
      job.status,
      job.workerHint
    );

    return {
      label: "处理中",
      type: "processing",
      canVectorize: false,
      canDeleteVector: false,
      canPoll: true,
      ...(job.workerHint ? { workerHint: job.workerHint } : {}),
      ...(recoveryActions.length > 0 ? { recoveryActions } : {}),
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
    const recoveryActions = getVectorFailureRecoveryActions(
      job.failureType,
      job.canRetry
    );

    return {
      label: "向量化失败",
      type: "failed",
      canVectorize: job.canRetry,
      canDeleteVector: true,
      canPoll: false,
      ...(job.errorMessage ? { errorMessage: job.errorMessage } : {}),
      ...(job.failureHint ? { failureHint: job.failureHint } : {}),
      ...(recoveryActions.length > 0 ? { recoveryActions } : {}),
      canRetry: job.canRetry,
      deleteVectorLabel: "清理残留向量",
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


export function getWorkerStatus(value: unknown): VectorIndexHealthResponse["worker"]["status"] {
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


export function getQueueStatus(value: unknown): VectorIndexHealthResponse["queue"]["status"] {
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


export function getQueueStatusLabel(
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


export function parseVectorIndexHealth(value: unknown): VectorIndexHealthResponse | null {
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
      onlineCount: getNumberField(worker, "online_count"),
      redisEnabled: getNullableBooleanField(worker, ["redis_enabled"]),
      redisAvailable: getNullableBooleanField(worker, ["redis_available"]),
      redisStatus: getNullableStringField(worker, ["redis_status"]),
      redisErrorMessage: getNullableStringField(worker, [
        "redis_error_message",
      ]),
      lastHeartbeatAt:
        typeof worker.last_heartbeat_at === "string"
          ? worker.last_heartbeat_at
          : null,
      lastHeartbeatAgeSeconds: getNullableNumberField(worker, [
        "last_heartbeat_age_seconds",
      ]),
      heartbeatTtlSeconds: getNullableNumberField(worker, [
        "heartbeat_ttl_seconds",
      ]),
      activeFileLockCount: getNullableNumberField(worker, [
        "active_file_lock_count",
      ]),
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


export function getWorkerHealthLabel(
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
    if (
      health.queue.active > 0 &&
      health.worker.redisAvailable === true &&
      health.worker.onlineCount === 0 &&
      health.worker.staleQueued + health.worker.staleProcessing === 0
    ) {
      return {
        label: `未检测到在线 Worker：${health.queue.active} 个任务待处理`,
        tone: "danger",
      };
    }

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


function buildWorkerHealthDetails(
  health: VectorIndexHealthResponse
): WorkerHealthDetails["details"] {
  const details: WorkerHealthDetails["details"] = [
    {
      label: "队列状态",
      value: getQueueStatusLabel(health.queue.status),
    },
    {
      label: "排队",
      value: `${health.queue.queued} 个`,
      tone: health.queue.queued > 0 ? "warning" : "muted",
    },
    {
      label: "处理中",
      value: `${health.queue.processing} 个`,
      tone: health.queue.processing > 0 ? "success" : "muted",
    },
    {
      label: "失败",
      value: `${health.queue.failed} 个`,
      tone: health.queue.failed > 0 ? "danger" : "muted",
    },
  ];

  if (health.worker.redisAvailable !== null) {
    details.push({
      label: "Redis 运行态",
      value: health.worker.redisAvailable ? "可用" : "不可用",
      tone: health.worker.redisAvailable ? "success" : "warning",
    });
  }

  if (health.worker.redisAvailable === true) {
    details.push({
      label: "在线 Worker",
      value: `${health.worker.onlineCount} 个`,
      tone:
        health.queue.active > 0 && health.worker.onlineCount === 0
          ? "danger"
          : health.worker.onlineCount > 0
            ? "success"
            : "muted",
    });
  }

  if (health.worker.staleQueued > 0 || health.worker.staleProcessing > 0) {
    details.push({
      label: "疑似卡住",
      value: `${health.worker.staleQueued + health.worker.staleProcessing} 个`,
      tone: "danger",
    });
  }

  if (health.worker.oldestActiveSeconds !== null) {
    details.push({
      label: "最老活跃任务",
      value: formatDurationSeconds(health.worker.oldestActiveSeconds),
      tone: health.worker.oldestActiveSeconds > 0 ? "warning" : "muted",
    });
  }

  if (health.worker.lastJobUpdatedAt) {
    details.push({
      label: "最近任务更新",
      value: formatDateTimeText(health.worker.lastJobUpdatedAt),
    });
  }

  if (health.worker.lastProcessingHeartbeatAt) {
    details.push({
      label: "最近处理心跳",
      value: formatDateTimeText(health.worker.lastProcessingHeartbeatAt),
    });
  }

  if (health.worker.lastHeartbeatAt) {
    details.push({
      label: "最近 Worker 心跳",
      value: formatDateTimeText(health.worker.lastHeartbeatAt),
    });
  }

  if (health.worker.lastHeartbeatAgeSeconds !== null) {
    details.push({
      label: "心跳延迟",
      value: formatDurationSeconds(health.worker.lastHeartbeatAgeSeconds),
      tone:
        health.worker.heartbeatTtlSeconds !== null &&
        health.worker.lastHeartbeatAgeSeconds > health.worker.heartbeatTtlSeconds
          ? "danger"
          : "muted",
    });
  }

  if (health.worker.activeFileLockCount !== null) {
    details.push({
      label: "活跃文件锁",
      value: `${health.worker.activeFileLockCount} 个`,
      tone: health.worker.activeFileLockCount > 0 ? "success" : "muted",
    });
  }

  return details;
}


export function getWorkerHealthDetails(
  health: VectorIndexHealthResponse | null,
  errorMessage: string
): WorkerHealthDetails {
  const label = getWorkerHealthLabel(health, errorMessage);

  if (errorMessage) {
    return {
      summary: label.label,
      tone: label.tone,
      checkedAtLabel: "未知",
      details: [],
      suggestedActions: ["确认后端服务已启动，并检查登录状态后重新刷新。"],
    };
  }

  if (!health) {
    return {
      summary: label.label,
      tone: label.tone,
      checkedAtLabel: "读取中",
      details: [],
      suggestedActions: ["等待状态接口返回，或稍后手动刷新。"],
    };
  }

  const suggestedActions: string[] = [];

  if (health.worker.status === "idle") {
    suggestedActions.push("无需操作；上传文件或手动向量化后会进入队列。");
  } else if (health.worker.status === "waiting") {
    suggestedActions.push("确认 vector index worker 已启动，排队任务会自动被领取。");
  } else if (health.worker.status === "active") {
    suggestedActions.push("等待当前任务完成；长时间无变化时可刷新状态或查看 worker 日志。");
  } else if (health.worker.status === "attention_needed") {
    if (health.worker.staleQueued > 0) {
      suggestedActions.push("存在长时间未领取任务，优先启动或重启 vector index worker。");
    }

    if (health.worker.staleProcessing > 0) {
      suggestedActions.push("存在长时间处理中的任务，查看 worker 日志后决定是否重试。");
    }
  } else {
    suggestedActions.push("状态无法识别，请刷新后再判断是否需要查看后端日志。");
  }

  if (health.queue.failed > 0) {
    suggestedActions.push("失败任务可在下方任务列表或文件卡片中按红色状态快速定位。");
  }

  if (health.worker.redisAvailable === false) {
    suggestedActions.push(
      "Redis worker 运行态暂不可用；队列仍会按 PostgreSQL 状态判断，必要时检查 Redis 连接。"
    );
  }

  if (
    health.queue.active > 0 &&
    health.worker.redisAvailable === true &&
    health.worker.onlineCount === 0
  ) {
    suggestedActions.push("未检测到在线 vector index worker，优先启动或重启 worker 容器。");
  }

  if (health.worker.hint && !suggestedActions.includes(health.worker.hint)) {
    suggestedActions.push(health.worker.hint);
  }

  return {
    summary: label.label,
    tone: label.tone,
    checkedAtLabel: formatDateTimeText(health.worker.checkedAt),
    details: buildWorkerHealthDetails(health),
    suggestedActions,
  };
}

export function getWorkerHealthToneClass(tone: WorkerHealthTone) {
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


export function getWorkerHealthDetailToneClass(tone?: WorkerHealthTone) {
  if (tone === "danger") {
    return "border-[#e36b4f] bg-[#fff1ed] text-[#9b3c29]";
  }

  if (tone === "warning") {
    return "border-[#d9aa2f] bg-[#fff7df] text-[#7a5a12]";
  }

  if (tone === "success") {
    return "border-[#9fc6bd] bg-[#edf7f3] text-[#176b62]";
  }

  return "border-current/20 bg-white/45";
}


export function toVectorIndexJob(value: unknown): VectorIndexJob | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }

  const job = value as {
    id?: unknown;
    job_id?: unknown;
    knowledge_file_id?: unknown;
    status?: unknown;
    error_message?: unknown;
    failure_type?: unknown;
    failure_hint?: unknown;
    worker_hint?: unknown;
    can_retry?: unknown;
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
  const failureType = getNullableStringField(job, ["failure_type"]);
  const canRetry = status === "failed" && job.can_retry !== false;
  const recoveryActions = getVectorFailureRecoveryActions(
    failureType,
    canRetry
  );

  return {
    id,
    knowledgeFileId:
      typeof job.knowledge_file_id === "string" && job.knowledge_file_id.trim()
        ? job.knowledge_file_id.trim()
        : null,
    status,
    errorMessage:
      typeof job.error_message === "string" ? job.error_message : "",
    failureType,
    failureHint:
      typeof job.failure_hint === "string" ? job.failure_hint.trim() : "",
    workerHint:
      typeof job.worker_hint === "string" ? job.worker_hint.trim() : "",
    canRetry,
    ...(recoveryActions.length > 0 ? { recoveryActions } : {}),
  };
}


export function getVectorIndexJobs(value: unknown) {
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


export function isVectorIndexJobDone(job: VectorIndexJob) {
  return job.status === "succeeded" || job.status === "failed";
}


export function getVectorIndexStatusText(status: VectorIndexJobStatus) {
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


export function wait(ms: number) {
  return new Promise<void>((resolve) => {
    window.setTimeout(resolve, ms);
  });
}
