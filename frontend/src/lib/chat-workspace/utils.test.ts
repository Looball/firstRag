import { describe, expect, it } from "vitest";

import {
  buildOriginalFilePreviewUrl,
  formatDiagnosticTiming,
  formatSourcePosition,
  getChatSources,
  getRetrievalState,
  serializeRetrievalSettings,
  toRetrievalSettings,
} from "./utils";

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
          dense_score: "0.82",
          sparse_score: "0.71",
          hybrid_score: "0.21",
          rerank_score: "1.25",
          retrieval_sources: ["dense", "sparse"],
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
        denseScore: 0.82,
        sparseScore: 0.71,
        hybridScore: 0.21,
        rerankScore: 1.25,
        retrievalSources: ["dense", "sparse"],
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

describe("chat workspace settings and formatting helpers", () => {
  it("bounds retrieval settings and serializes backend payload", () => {
    const settings = toRetrievalSettings({
      retrieval_mode: "always",
      enable_query_router: "false",
      enable_rerank: true,
      top_k: 50,
      vector_top_k: 0,
      sparse_top_k: "10",
      rrf_k: "200",
      rerank_score_threshold: "-30",
    });

    expect(settings).toEqual({
      retrievalMode: "always",
      enableQueryRouter: false,
      enableRerank: true,
      topK: 20,
      vectorTopK: 1,
      sparseTopK: 10,
      rrfK: 100,
      rerankScoreThreshold: -20,
    });
    expect(serializeRetrievalSettings(settings)).toEqual({
      retrieval_mode: "always",
      enable_query_router: false,
      enable_rerank: true,
      top_k: 20,
      vector_top_k: 1,
      sparse_top_k: 10,
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
