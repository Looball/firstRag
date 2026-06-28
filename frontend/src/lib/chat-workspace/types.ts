export type Message = {
  id?: string;
  role: "user" | "assistant";
  content: string;
  status?: string;
  errorMessage?: string | null;
  sources?: ChatSource[];
  retrieval?: RetrievalState;
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
  canRetry?: boolean;
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

export type VectorIndexJob = {
  id: string;
  status: VectorIndexJobStatus;
  errorMessage: string;
  failureHint: string;
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
