import {
  DEFAULT_RETRIEVAL_SETTINGS,
  LEGACY_INITIAL_MESSAGE,
} from "./constants";
import type {
  BackendConversation,
  BackendKnowledgeBase,
  ChatSession,
  ChatSource,
  KnowledgeBase,
  KnowledgeBaseRetrievalSettings,
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


export function formatSourcePosition(
  position: Pick<
    ChatSource,
    "pageNumber" | "pageCount" | "paragraphStart" | "paragraphEnd"
  >,
) {
  if (position.pageNumber !== undefined) {
    const pageCount = position.pageCount;
    return pageCount !== undefined
      ? `第 ${position.pageNumber} / ${pageCount} 页`
      : `第 ${position.pageNumber} 页`;
  }

  if (position.paragraphStart !== undefined) {
    const paragraphEnd = position.paragraphEnd ?? position.paragraphStart;
    return paragraphEnd === position.paragraphStart
      ? `第 ${position.paragraphStart} 段`
      : `第 ${position.paragraphStart}–${paragraphEnd} 段`;
  }

  return "";
}


export function formatOcrConfidence(confidence?: number) {
  if (confidence === undefined || !Number.isFinite(confidence)) {
    return "";
  }
  return `${Math.round(Math.min(100, Math.max(0, confidence)))}%`;
}


export function buildOriginalFilePreviewUrl(
  objectUrl: string,
  mimeType: string,
  pageNumber?: number,
) {
  const isPdf =
    mimeType.split(";", 1)[0].trim().toLowerCase() === "application/pdf";
  if (!isPdf || pageNumber === undefined || !Number.isFinite(pageNumber)) {
    return objectUrl;
  }

  return `${objectUrl}#page=${Math.max(1, Math.floor(pageNumber))}`;
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
    denseScore: getNullableNumberField(source, ["dense_score"]),
    sparseScore: getNullableNumberField(source, ["sparse_score"]),
    hybridScore: getNullableNumberField(source, ["hybrid_score"]),
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
    denseDegraded: diagnostics.dense_degraded === true,
    denseErrors: getStringArrayField(diagnostics, "dense_errors"),
    sparseDegraded: diagnostics.sparse_degraded === true,
    sparseErrors: getStringArrayField(diagnostics, "sparse_errors"),
    hybridDegraded: diagnostics.hybrid_degraded === true,
    hybridErrors: getStringArrayField(diagnostics, "hybrid_errors"),
    vectorCount: getNullableNumberField(diagnostics, ["vector_count"]),
    fulltextCount: getNullableNumberField(diagnostics, ["fulltext_count"]),
    denseCount: getNullableNumberField(diagnostics, ["dense_count"]),
    sparseCount: getNullableNumberField(diagnostics, ["sparse_count"]),
    hybridCount: getNullableNumberField(diagnostics, ["hybrid_count"]),
    parentCount: getNullableNumberField(diagnostics, ["parent_count"]),
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
      denseEmbeddingMs: getNullableNumberField(timing, [
        "dense_embedding_ms",
      ]),
      sparseEmbeddingMs: getNullableNumberField(timing, [
        "sparse_embedding_ms",
      ]),
      hybridMs: getNullableNumberField(timing, ["hybrid_ms"]),
      parentContextMs: getNullableNumberField(timing, [
        "parent_context_ms",
      ]),
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
  const pageIndex =
    getOptionalNumberField(source, ["page_index"]) ??
    (metadataRecord
      ? getOptionalNumberField(metadataRecord, ["page_index"])
      : undefined);
  const pageNumber =
    getOptionalNumberField(source, ["page_number", "page"]) ??
    (metadataRecord
      ? getOptionalNumberField(metadataRecord, ["page_number", "page"])
      : undefined);
  const pageCount =
    getOptionalNumberField(source, ["page_count"]) ??
    (metadataRecord
      ? getOptionalNumberField(metadataRecord, ["page_count"])
      : undefined);
  const paragraphStart =
    getOptionalNumberField(source, ["paragraph_start"]) ??
    (metadataRecord
      ? getOptionalNumberField(metadataRecord, ["paragraph_start"])
      : undefined);
  const paragraphEnd =
    getOptionalNumberField(source, ["paragraph_end"]) ??
    (metadataRecord
      ? getOptionalNumberField(metadataRecord, ["paragraph_end"])
      : undefined);
  const pdfParseMethod =
    getStringField(source, ["pdf_parse_method"]) ||
    (metadataRecord
      ? getStringField(metadataRecord, ["pdf_parse_method"])
      : "");
  const ocrConfidence =
    getOptionalNumberField(source, ["ocr_confidence"]) ??
    (metadataRecord
      ? getOptionalNumberField(metadataRecord, ["ocr_confidence"])
      : undefined);
  const ocrQuality =
    getStringField(source, ["ocr_quality"]) ||
    (metadataRecord ? getStringField(metadataRecord, ["ocr_quality"]) : "");
  const ocrAttempt =
    getOptionalNumberField(source, ["ocr_attempt"]) ??
    (metadataRecord
      ? getOptionalNumberField(metadataRecord, ["ocr_attempt"])
      : undefined);
  const ocrCorrectionApplied =
    source["ocr_correction_applied"] === true ||
    metadataRecord?.["ocr_correction_applied"] === true;
  const ocrCorrectionRevision =
    getOptionalNumberField(source, ["ocr_correction_revision"]) ??
    (metadataRecord
      ? getOptionalNumberField(metadataRecord, ["ocr_correction_revision"])
      : undefined);
  const rerankScore = getOptionalNumberField(source, [
    "rerank_score",
    "score",
  ]);
  const rrfScore = getOptionalNumberField(source, ["rrf_score"]);
  const vectorScore = getOptionalNumberField(source, ["vector_score"]);
  const fulltextScore = getOptionalNumberField(source, ["fulltext_score"]);
  const denseScore = getOptionalNumberField(source, ["dense_score"]);
  const sparseScore = getOptionalNumberField(source, ["sparse_score"]);
  const hybridScore = getOptionalNumberField(source, ["hybrid_score"]);
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
  const sourcePosition = formatSourcePosition({
    pageNumber,
    pageCount,
    paragraphStart,
    paragraphEnd,
  });
  if (sourcePosition) {
    metadataParts.push(sourcePosition);
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
    ...(pageIndex !== undefined ? { pageIndex } : {}),
    ...(pageNumber !== undefined ? { pageNumber } : {}),
    ...(pageCount !== undefined ? { pageCount } : {}),
    ...(paragraphStart !== undefined ? { paragraphStart } : {}),
    ...(paragraphEnd !== undefined ? { paragraphEnd } : {}),
    ...(pdfParseMethod ? { pdfParseMethod } : {}),
    ...(ocrConfidence !== undefined ? { ocrConfidence } : {}),
    ...(ocrQuality ? { ocrQuality } : {}),
    ...(ocrAttempt !== undefined ? { ocrAttempt } : {}),
    ...(ocrCorrectionApplied ? { ocrCorrectionApplied: true } : {}),
    ...(ocrCorrectionRevision !== undefined
      ? { ocrCorrectionRevision }
      : {}),
    ...(vectorScore !== undefined ? { vectorScore } : {}),
    ...(fulltextScore !== undefined ? { fulltextScore } : {}),
    ...(denseScore !== undefined ? { denseScore } : {}),
    ...(sparseScore !== undefined ? { sparseScore } : {}),
    ...(hybridScore !== undefined ? { hybridScore } : {}),
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
    "page_index",
    "page_number",
    "page_count",
    "paragraph_start",
    "paragraph_end",
    "pdf_parse_method",
    "ocr_confidence",
    "ocr_quality",
    "ocr_attempt",
    "ocr_correction_applied",
    "ocr_correction_revision",
    "vector_score",
    "fulltext_score",
    "dense_score",
    "sparse_score",
    "hybrid_score",
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
    sparseTopK: getBoundedNumber(
      settings,
      ["sparse_top_k"],
      DEFAULT_RETRIEVAL_SETTINGS.sparseTopK,
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
    sparse_top_k: settings.sparseTopK,
    rrf_k: settings.rrfK,
    rerank_score_threshold: settings.rerankScoreThreshold,
  };
}


export function wait(ms: number) {
  return new Promise<void>((resolve) => {
    window.setTimeout(resolve, ms);
  });
}
