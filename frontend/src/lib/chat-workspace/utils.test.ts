import { describe, expect, it } from "vitest";

import {
  formatDiagnosticTiming,
  getChatSources,
  getRetrievalState,
  getVectorStatus,
  getWorkerHealthLabel,
  parseVectorIndexHealth,
  serializeRetrievalSettings,
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
        metadata: "fulltext / vector",
        fileId: "file-1",
        fileName: "source.md",
        chunkIndex: 2,
        rerankScore: 1.25,
        retrievalSources: ["fulltext", "vector"],
      },
    ]);
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
    expect(health?.queue.status).toBe("stuck");
    expect(getWorkerHealthLabel(health, "")).toEqual({
      label: "任务可能卡住：排队 1 个，处理中 2 个",
      tone: "danger",
    });
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
      canDeleteVector: false,
      canPoll: false,
      errorMessage: "解析失败",
      failureHint: "请确认文件内容可读取。",
      canRetry: true,
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
