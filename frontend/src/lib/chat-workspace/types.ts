export type Message = {
  id?: string;
  role: "user" | "assistant";
  content: string;
  status?: string;
  errorMessage?: string | null;
  attachments?: MessageAttachment[];
  sources?: ChatSource[];
  retrieval?: RetrievalState;
  feedback?: MessageFeedback | null;
};

export type MessageAttachment = {
  id: string;
  originalName: string;
  mimeType: string;
  sizeBytes: number;
  contentUrl: string;
  createdAt?: string;
  localPreviewUrl?: string;
};

export type MessageFeedbackRating = "positive" | "negative";

export type MessageFeedbackReason =
  | "irrelevant_sources"
  | "missing_answer"
  | "hallucination"
  | "outdated_or_wrong"
  | "too_slow"
  | "format_issue"
  | "other";

export type MessageFeedback = {
  id?: string;
  rating: MessageFeedbackRating;
  reason?: MessageFeedbackReason | null;
  note?: string | null;
};

export type ChatSource = {
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
  feedback?: MessageSourceFeedback | null;
};

export type MessageSourceFeedbackRating = "useful" | "irrelevant";

export type MessageSourceFeedback = {
  id?: string;
  sourceIndex: number;
  knowledgeFileId?: string | null;
  chunkIndex?: number | null;
  rating: MessageSourceFeedbackRating;
  note?: string | null;
};

export type RetrievalState = {
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

export type MessageDiagnostic = {
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

export type RetrievalDiagnostics = {
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

export type RetrievalLlmDiagnostics = {
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

export type RetrievalTiming = {
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

export type SourcePreview = {
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

export type ChatSession = {
  id: string;
  knowledgeBaseId: string;
  title: string;
  messages: Message[];
  messagesLoaded: boolean;
};

export type KnowledgeBase = {
  id: string;
  name: string;
  isDefault: boolean;
  fileCount: number;
};

export type RetrievalMode = "auto" | "always" | "never";

export type KnowledgeBaseRetrievalSettings = {
  retrievalMode: RetrievalMode;
  enableQueryRouter: boolean;
  enableRerank: boolean;
  topK: number;
  vectorTopK: number;
  fulltextTopK: number;
  rrfK: number;
  rerankScoreThreshold: number;
};

export type BackendKnowledgeBase = {
  id?: unknown;
  name?: unknown;
  is_default?: unknown;
  file_count?: unknown;
  conversations?: unknown;
};

export type KnowledgeFile = {
  id: string;
  name: string;
  size: number;
  fingerprint: string;
  status: KnowledgeFileStatus;
  latestIndexJob: LatestIndexJob | null;
  usageCount: number | null;
  reused?: boolean;
  alreadyInKnowledgeBase?: boolean;
};

export type KnowledgeFileStatus =
  | "pending"
  | "queued"
  | "processing"
  | "indexed"
  | "failed";

export type VectorIndexJobStatus =
  | "queued"
  | "processing"
  | "succeeded"
  | "failed";

export type LatestIndexJobStatus =
  | "queued"
  | "processing"
  | "completed"
  | "failed"
  | "unknown";

export type LatestIndexJob = {
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

export type VectorStatus = {
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
  recoveryActions?: string[];
  canRetry?: boolean;
  deleteVectorLabel?: string;
};

export type VectorIndexHealthResponse = {
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
    onlineCount: number;
    redisEnabled: boolean | null;
    redisAvailable: boolean | null;
    redisStatus: string | null;
    redisErrorMessage: string | null;
    lastHeartbeatAt: string | null;
    lastHeartbeatAgeSeconds: number | null;
    heartbeatTtlSeconds: number | null;
    activeFileLockCount: number | null;
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

export type WorkerHealthTone = "muted" | "warning" | "success" | "danger";

export type WorkerHealthDetail = {
  label: string;
  value: string;
  tone?: WorkerHealthTone;
};

export type WorkerHealthDetails = {
  summary: string;
  tone: WorkerHealthTone;
  checkedAtLabel: string;
  details: WorkerHealthDetail[];
  suggestedActions: string[];
};

export type VectorIndexJob = {
  id: string;
  knowledgeFileId?: string | null;
  status: VectorIndexJobStatus;
  errorMessage: string;
  failureType?: string | null;
  failureHint: string;
  workerHint?: string;
  canRetry?: boolean;
  recoveryActions?: string[];
};

export type VectorIndexQueueItem = VectorIndexJob & {
  targetName: string;
  targetType: "file" | "knowledge-base";
};

export type BackendKnowledgeFile = {
  id?: unknown;
  original_name?: unknown;
  size_bytes?: unknown;
  status?: unknown;
  usage_count?: unknown;
  reused?: unknown;
  already_in_knowledge_base?: unknown;
  latest_index_job?: unknown;
};

export type KnowledgeBaseFile = {
  knowledgeBaseId: string;
  knowledgeFileId: string;
};

export type BackendConversation = {
  id?: unknown;
  knowledge_base_id?: unknown;
  title?: unknown;
  messages?: unknown;
};

export type CreateConversationResponse = {
  conversation?: BackendConversation;
  id?: unknown;
  title?: unknown;
  answer?: string;
  detail?: string;
  error?: string;
  message?: string;
};

export type ListMessagesResponse = {
  messages?: unknown;
  detail?: string;
  error?: string;
  message?: string;
};

export type UploadChatAttachmentsResponse = {
  attachments?: unknown;
  detail?: string;
  error?: string;
  message?: string;
};

export type MessageFeedbackResponse = {
  feedback?: unknown;
  detail?: string;
  error?: string;
  message?: string;
};

export type MessageSourceFeedbackResponse = MessageFeedbackResponse;

export type EvalCaseDraftResponse = {
  draft?: unknown;
  detail?: string;
  error?: string;
  message?: string;
};

export type QualityDashboard = {
  windowDays: number;
  hasFeedback: boolean;
  messageFeedback: {
    total: number;
    positive: number;
    negative: number;
    negativeRate: number | null;
    reasonDistribution: Array<{
      reason: string;
      count: number;
    }>;
  };
  sourceFeedback: {
    total: number;
    useful: number;
    irrelevant: number;
    irrelevantRate: number | null;
    topIrrelevantFiles: Array<{
      fileName: string;
      count: number;
    }>;
  };
  retrieval: {
    assistantMessages: number;
    averageSources: number | null;
    averageFirstTokenMs: number | null;
  };
};

export type ListKnowledgeBasesResponse = {
  knowledge_bases?: unknown;
  detail?: string;
  error?: string;
  message?: string;
};

export type CreateKnowledgeBaseResponse = {
  knowledge_base?: BackendKnowledgeBase;
  detail?: string;
  error?: string;
  message?: string;
};

export type RetrievalSettingsResponse = {
  settings?: unknown;
  detail?: string;
  error?: string;
  message?: string;
};

export type UploadKnowledgeFilesResponse = {
  files?: unknown;
  detail?: string;
  error?: string;
  message?: string;
};

export type ListKnowledgeFilesResponse = UploadKnowledgeFilesResponse;

export type VectorIndexResponse = {
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
