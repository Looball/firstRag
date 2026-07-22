import { describe, expect, it } from "vitest";

import type { KnowledgeFile, PdfOcrQualityPage } from "./types";
import {
  buildOcrPageSource,
  filterAndSortOcrPages,
  mergeOcrPageSelection,
  toggleOcrPageSelection,
} from "./ocr-quality";

const pages: PdfOcrQualityPage[] = [
  {
    pageNumber: 1,
    pageCount: 3,
    chunkIndex: 0,
    indexVersion: 4,
    ocrConfidence: 92,
    ocrQuality: "ok",
    ocrAttempt: 1,
    needsReview: false,
    hasCorrection: false,
    correctionRevision: 0,
    correctionUpdatedAt: null,
    historyCount: 1,
    latestConfidenceDelta: null,
    excerpt: "Clear page",
  },
  {
    pageNumber: 2,
    pageCount: 3,
    chunkIndex: 1,
    indexVersion: 4,
    ocrConfidence: 38,
    ocrQuality: "low",
    ocrAttempt: 1,
    needsReview: true,
    hasCorrection: false,
    correctionRevision: 0,
    correctionUpdatedAt: null,
    historyCount: 2,
    latestConfidenceDelta: 4,
    excerpt: "Needs review",
  },
  {
    pageNumber: 3,
    pageCount: 3,
    chunkIndex: 2,
    indexVersion: 4,
    ocrConfidence: 44,
    ocrQuality: "low",
    ocrAttempt: 1,
    needsReview: false,
    hasCorrection: true,
    correctionRevision: 2,
    correctionUpdatedAt: "2026-07-22T10:00:00+08:00",
    historyCount: 3,
    latestConfidenceDelta: -2,
    excerpt: "Corrected page",
  },
];

describe("OCR quality review helpers", () => {
  it("shows only unresolved low-confidence pages in review mode", () => {
    expect(filterAndSortOcrPages(pages, "review", "confidence")).toEqual([
      expect.objectContaining({ pageNumber: 2 }),
    ]);
  });

  it("filters corrected pages and preserves page sorting", () => {
    expect(filterAndSortOcrPages(pages, "corrected", "page")).toEqual([
      expect.objectContaining({ pageNumber: 3, correctionRevision: 2 }),
    ]);
  });

  it("sorts the complete list by page number", () => {
    expect(
      filterAndSortOcrPages([...pages].reverse(), "all", "page").map(
        (page) => page.pageNumber,
      ),
    ).toEqual([1, 2, 3]);
  });

  it("builds a source that opens the exact page and index version", () => {
    const file: KnowledgeFile = {
      id: "file-1",
      name: "scan.pdf",
      size: 100,
      fingerprint: "hash",
      status: "indexed",
      latestIndexJob: null,
      usageCount: 1,
    };

    expect(buildOcrPageSource(file, pages[1])).toEqual(
      expect.objectContaining({
        fileId: "file-1",
        chunkIndex: 1,
        indexVersion: 4,
        pageNumber: 2,
        pdfParseMethod: "ocr",
      }),
    );
  });

  it("normalizes batch selection and respects its maximum", () => {
    expect(mergeOcrPageSelection([3], [2, 1, 2, 4], 3)).toEqual([1, 2, 3]);
  });

  it("toggles pages without mutating the current selection", () => {
    const current = [1, 2];
    expect(toggleOcrPageSelection(current, 2, 20)).toEqual([1]);
    expect(toggleOcrPageSelection(current, 3, 20)).toEqual([1, 2, 3]);
    expect(current).toEqual([1, 2]);
  });
});
