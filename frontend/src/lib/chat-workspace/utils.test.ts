import { describe, expect, it } from "vitest";

import {
  buildOriginalFilePreviewUrl,
  formatDiagnosticTiming,
  formatSourcePosition,
  getChatSources,
  getRetrievalState,
  getVectorStatus,
  getVectorFailureRecoveryActions,
  getWorkerHealthDetails,
  getWorkerHealthLabel,
  parseVectorIndexHealth,
  serializeRetrievalSettings,
  toVectorIndexJob,
  toRetrievalSettings,
} from "./utils";
import type { KnowledgeFile } from "./types";

describe("chat workspace retrieval parsing", () => {
  it("parses persisted retrieval state from nested JSON", () => {
    const retrieval = getRetrievalState(
      JSON.stringify({
        retrieval: {
          need_retrieval: true,
          final_need_retrieval: true,
          llm_need_retrieval: false,
          rewritten_query: "RAG 核心",
          reason: "命中文档画像",
          llm_reason: "普通问题",
          override_applied: true,
          override_reason: "profile keyword match",
          retrieved_count: "5",
          source_count: 3,
        },
      })
    );

    expect(retrieval).toEqual({
      need_retrieval: true,
      final_need_retrieval: true,
      llm_need_retrieval: false,
      rewritten_query: "RAG 核心",
      reason: "命中文档画像",
      llm_reason: "普通问题",
      override_applied: true,
      override_reason: "profile keyword match",
      retrieved_count: 5,
      source_count: 3,
    });
  });

  it("returns undefined when retrieval payload has no boolean decision", () => {
    expect(getRetrievalState({ retrieval: { need_retrieval: "true" } })).toBe(
      undefined
    );
  });
});

describe("chat workspace source parsing", () => {
  it("normalizes source fields and retrieval channel metadata", () => {
    const sources = getChatSources({
      sources: [
        {
          file_id: "file-1",
          file_name: "source.md",
          chunk_index: "2",
          index_version: "4",
          page_index: 1,
          page_number: 2,
          page_count: 3,
          pdf_parse_method: "ocr",
          ocr_confidence: "62.4",
          ocr_quality: "low",
          ocr_attempt: 2,
          ocr_correction_applied: true,
          ocr_correction_revision: 3,
          rerank_score: "1.25",
          retrieval_sources: ["fulltext", "vector"],
          content: "matched chunk",
        },
      ],
    });

    expect(sources).toEqual([
      {
        title: "source.md",
        content: "matched chunk",
        metadata: "第 2 / 3 页",
        fileId: "file-1",
        fileName: "source.md",
        chunkIndex: 2,
        indexVersion: 4,
        pageIndex: 1,
        pageNumber: 2,
        pageCount: 3,
        pdfParseMethod: "ocr",
        ocrConfidence: 62.4,
        ocrQuality: "low",
        ocrAttempt: 2,
        ocrCorrectionApplied: true,
        ocrCorrectionRevision: 3,
        rerankScore: 1.25,
        retrievalSources: ["fulltext", "vector"],
      },
    ]);
  });

  it("normalizes DOCX paragraph locations from nested metadata", () => {
    const sources = getChatSources({
      sources: [
        {
          file_name: "contract.docx",
          content: "target paragraph",
          metadata: {
            paragraph_start: "4",
            paragraph_end: 5,
          },
        },
      ],
    });

    expect(sources[0]).toEqual(
      expect.objectContaining({
        metadata: "第 4–5 段",
        paragraphStart: 4,
        paragraphEnd: 5,
      }),
    );
  });
});

describe("source position helpers", () => {
  it("formats pages and paragraph ranges", () => {
    expect(formatSourcePosition({ pageNumber: 2, pageCount: 3 })).toBe(
      "第 2 / 3 页",
    );
    expect(formatSourcePosition({ paragraphStart: 4, paragraphEnd: 5 })).toBe(
      "第 4–5 段",
    );
  });

  it("adds PDF page fragments without changing other file URLs", () => {
    expect(
      buildOriginalFilePreviewUrl("blob:test", "application/pdf", 2),
    ).toBe("blob:test#page=2");
    expect(
      buildOriginalFilePreviewUrl(
        "blob:test",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        2,
      ),
    ).toBe("blob:test");
  });
});

describe("chat workspace vector status parsing", () => {
  it("parses worker health response and label", () => {
    const health = parseVectorIndexHealth({
      success: true,
      worker: {
        status: "attention_needed",
        is_healthy: false,
        has_recent_activity: false,
        hint: "存在排队任务长时间未被领取，可能 worker 未启动。",
        stale_queued: 1,
        stale_processing: 2,
        oldest_active_seconds: 120,
        redis_available: true,
        online_count: 0,
        last_heartbeat_at: "2026-06-28T07:59:50",
        last_heartbeat_age_seconds: 10,
        heartbeat_ttl_seconds: 30,
        active_file_lock_count: 0,
        checked_at: "2026-06-28T08:00:00",
      },
      queue: {
        status: "stuck",
        total: 3,
        active: 3,
        queued: 1,
        processing: 2,
        succeeded: 0,
        failed: 0,
        cancelled: 0,
      },
    });

    expect(health?.worker.status).toBe("attention_needed");
    expect(health?.worker.staleQueued).toBe(1);
    expect(health?.worker.onlineCount).toBe(0);
    expect(health?.queue.status).toBe("stuck");
    expect(getWorkerHealthLabel(health, "")).toEqual({
      label: "任务可能卡住：排队 1 个，处理中 2 个",
      tone: "danger",
    });
    expect(getWorkerHealthDetails(health, "")).toMatchObject({
      summary: "任务可能卡住：排队 1 个，处理中 2 个",
      tone: "danger",
      checkedAtLabel: "2026-06-28 08:00:00",
    });
    expect(getWorkerHealthDetails(health, "").suggestedActions).toContain(
      "存在长时间未领取任务，优先启动或重启 vector index worker。"
    );
    expect(getWorkerHealthDetails(health, "").details).toContainEqual({
      label: "Redis 运行态",
      value: "可用",
      tone: "success",
    });
  });

  it("reports active queue without online redis worker", () => {
    const health = parseVectorIndexHealth({
      success: true,
      worker: {
        status: "attention_needed",
        is_healthy: false,
        has_recent_activity: false,
        hint: "没有检测到在线 vector worker，排队或处理中任务可能无法推进。",
        stale_queued: 0,
        stale_processing: 0,
        redis_available: true,
        online_count: 0,
        checked_at: "2026-06-28T08:00:00",
      },
      queue: {
        status: "stuck",
        total: 2,
        active: 2,
        queued: 2,
        processing: 0,
        succeeded: 0,
        failed: 0,
        cancelled: 0,
      },
    });

    const details = getWorkerHealthDetails(health, "");

    expect(getWorkerHealthLabel(health, "")).toEqual({
      label: "未检测到在线 Worker：2 个任务待处理",
      tone: "danger",
    });
    expect(details.details).toContainEqual({
      label: "在线 Worker",
      value: "0 个",
      tone: "danger",
    });
    expect(details.suggestedActions).toContain(
      "未检测到在线 vector index worker，优先启动或重启 worker 容器。"
    );
  });

  it("builds actionable worker health details for active and failed queues", () => {
    const health = parseVectorIndexHealth({
      success: true,
      worker: {
        status: "active",
        is_healthy: true,
        has_recent_activity: true,
        hint: null,
        last_job_updated_at: "2026-06-28T08:01:02",
        last_processing_heartbeat_at: "2026-06-28T08:02:03",
        redis_available: false,
        redis_error_message: "connection refused",
        stale_queued: 0,
        stale_processing: 0,
        oldest_active_seconds: 45,
        checked_at: "2026-06-28T08:03:04",
      },
      queue: {
        status: "processing",
        total: 4,
        active: 1,
        queued: 0,
        processing: 1,
        succeeded: 2,
        failed: 1,
        cancelled: 0,
      },
    });

    const details = getWorkerHealthDetails(health, "");

    expect(details).toMatchObject({
      summary: "Worker 正在处理：1 个",
      tone: "success",
      checkedAtLabel: "2026-06-28 08:03:04",
    });
    expect(details.details).toContainEqual({
      label: "失败",
      value: "1 个",
      tone: "danger",
    });
    expect(details.details).toContainEqual({
      label: "最近处理心跳",
      value: "2026-06-28 08:02:03",
    });
    expect(details.details).toContainEqual({
      label: "Redis 运行态",
      value: "不可用",
      tone: "warning",
    });
    expect(details.suggestedActions).toContain(
      "失败任务可在下方任务列表或文件卡片中按红色状态快速定位。"
    );
    expect(details.suggestedActions).toContain(
      "Redis worker 运行态暂不可用；队列仍会按 PostgreSQL 状态判断，必要时检查 Redis 连接。"
    );
  });

  it("builds clear guidance for idle and waiting worker states", () => {
    const idleHealth = parseVectorIndexHealth({
      success: true,
      worker: {
        status: "idle",
        is_healthy: true,
        has_recent_activity: false,
        hint: null,
        stale_queued: 0,
        stale_processing: 0,
        checked_at: "2026-06-28T08:04:05",
      },
      queue: {
        status: "idle",
        total: 0,
        active: 0,
        queued: 0,
        processing: 0,
        succeeded: 0,
        failed: 0,
        cancelled: 0,
      },
    });
    const waitingHealth = parseVectorIndexHealth({
      success: true,
      worker: {
        status: "waiting",
        is_healthy: false,
        has_recent_activity: false,
        hint: "存在排队任务长时间未被领取，可能 worker 未启动。",
        stale_queued: 0,
        stale_processing: 0,
        checked_at: "2026-06-28T08:05:06",
      },
      queue: {
        status: "waiting",
        total: 2,
        active: 2,
        queued: 2,
        processing: 0,
        succeeded: 0,
        failed: 0,
        cancelled: 0,
      },
    });

    expect(getWorkerHealthDetails(idleHealth, "")).toMatchObject({
      summary: "暂无向量化任务",
      checkedAtLabel: "2026-06-28 08:04:05",
      suggestedActions: ["无需操作；上传文件或手动向量化后会进入队列。"],
    });
    expect(getWorkerHealthDetails(waitingHealth, "").suggestedActions).toContain(
      "确认 vector index worker 已启动，排队任务会自动被领取。"
    );
  });

  it("maps failed file index job to retryable vector status", () => {
    const file: KnowledgeFile = {
      id: "file-1",
      name: "source.md",
      size: 128,
      fingerprint: "fingerprint",
      status: "failed",
      usageCount: null,
      latestIndexJob: {
        id: "job-1",
        userId: 1,
        knowledgeFileId: "file-1",
        knowledgeBaseId: null,
        indexVersion: 1,
        status: "failed",
        attempts: 1,
        maxAttempts: 3,
        errorMessage: "解析失败",
        createdAt: "2026-06-28T08:00:00",
        updatedAt: "2026-06-28T08:00:00",
        startedAt: null,
        finishedAt: null,
        activeSeconds: null,
        isStale: false,
        workerHint: null,
        failureType: "parse_error",
        failureHint: "请确认文件内容可读取。",
        canRetry: true,
      },
    };

    expect(getVectorStatus(file)).toEqual({
      label: "向量化失败",
      type: "failed",
      canVectorize: true,
      canDeleteVector: true,
      canPoll: false,
      errorMessage: "解析失败",
      failureHint: "请确认文件内容可读取。",
      recoveryActions: [
        "确认文件可打开且内容可复制",
        "必要时转为 PDF、Markdown、TXT 或支持的图片格式后重新上传",
        "重新向量化",
      ],
      canRetry: true,
      deleteVectorLabel: "清理残留向量",
    });
  });

  it("maps vector failure types to recovery actions", () => {
    expect(getVectorFailureRecoveryActions("vector_store_error", true)).toEqual([
      "确认 Chroma/vector_db 可写",
      "清理残留向量后重新向量化",
    ]);
    expect(getVectorFailureRecoveryActions("empty_document", true)).toEqual([
      "确认文件不是空文件",
      "转为可复制文本后重新上传",
      "重新向量化",
    ]);
    expect(getVectorFailureRecoveryActions("image_parse_error", true)).toEqual([
      "在模型设置中选择支持 vision 的聊天模型",
      "确认图片文字清晰后重新向量化",
    ]);
    expect(getVectorFailureRecoveryActions("ocr_error", true)).toEqual([
      "确认扫描页面清晰且 OCR 页数未超过限制",
      "检查 worker 的 Tesseract 中文/英文语言包",
      "重新向量化",
    ]);
    expect(getVectorFailureRecoveryActions("chunk_write_error", true)).toEqual([
      "检查 PostgreSQL chunk 表和迁移状态",
      "修复数据库后重新向量化",
    ]);
    expect(getVectorFailureRecoveryActions("task_timeout", true)).toEqual([
      "查看 worker 日志和文件大小",
      "必要时重启 worker 后重新向量化",
    ]);
  });

  it("parses queue jobs with retry metadata and recovery actions", () => {
    expect(
      toVectorIndexJob({
        id: "job-1",
        knowledge_file_id: "file-1",
        status: "failed",
        error_message: "向量库写入失败",
        failure_type: "vector_store_error",
        failure_hint: "确认 Chroma/vector_db 可用。",
        worker_hint: "查看 worker 日志。",
        can_retry: true,
      }),
    ).toEqual({
      id: "job-1",
      knowledgeFileId: "file-1",
      status: "failed",
      errorMessage: "向量库写入失败",
      failureType: "vector_store_error",
      failureHint: "确认 Chroma/vector_db 可用。",
      workerHint: "查看 worker 日志。",
      canRetry: true,
      recoveryActions: [
        "确认 Chroma/vector_db 可写",
        "清理残留向量后重新向量化",
      ],
    });
  });
});

describe("chat workspace settings and formatting helpers", () => {
  it("bounds retrieval settings and serializes backend payload", () => {
    const settings = toRetrievalSettings({
      retrieval_mode: "always",
      enable_query_router: "false",
      enable_rerank: true,
      top_k: 50,
      vector_top_k: 0,
      fulltext_top_k: "10",
      rrf_k: "200",
      rerank_score_threshold: "-30",
    });

    expect(settings).toEqual({
      retrievalMode: "always",
      enableQueryRouter: false,
      enableRerank: true,
      topK: 20,
      vectorTopK: 1,
      fulltextTopK: 10,
      rrfK: 100,
      rerankScoreThreshold: -20,
    });
    expect(serializeRetrievalSettings(settings)).toEqual({
      retrieval_mode: "always",
      enable_query_router: false,
      enable_rerank: true,
      top_k: 20,
      vector_top_k: 1,
      fulltext_top_k: 10,
      rrf_k: 100,
      rerank_score_threshold: -20,
    });
  });

  it("formats timing values for diagnostics", () => {
    expect(formatDiagnosticTiming(null)).toBe("—");
    expect(formatDiagnosticTiming(8.123)).toBe("8.12ms");
    expect(formatDiagnosticTiming(120)).toBe("120ms");
    expect(formatDiagnosticTiming(1530)).toBe("1.53s");
  });
});
