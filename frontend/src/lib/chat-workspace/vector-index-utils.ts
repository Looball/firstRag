import type {
  BackendKnowledgeFile,
  KnowledgeFile,
  KnowledgeFileStatus,
  LatestIndexJob,
  LatestIndexJobStatus,
  VectorIndexHealthResponse,
  VectorIndexJob,
  VectorIndexJobStatus,
  VectorIndexResponse,
  VectorStatus,
  WorkerHealthDetails,
  WorkerHealthTone,
} from "./types";
import {
  formatDateTimeText,
  formatDurationSeconds,
  getFileFingerprint,
  getNullableBooleanField,
  getNullableNumberField,
  getNullableStringField,
  getNumberField,
  getRecordField,
} from "./utils";

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

  if (failureType === "ocr_error") {
    return [
      "确认扫描页面清晰且 OCR 页数未超过限制",
      "检查 worker 的 Tesseract 中文/英文语言包",
      ...retryAction,
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
      "确认 Milvus 及其 etcd/MinIO 依赖健康",
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
