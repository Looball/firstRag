import type {
  ChatSource,
  KnowledgeFile,
  PdfOcrQualityPage,
} from "./types";

export type OcrQualityFilter = "all" | "corrected" | "review";
export type OcrQualitySort = "confidence" | "page";

/** 按巡检筛选和顺序返回新数组，不修改 query cache 中的原始页。 */
export function filterAndSortOcrPages(
  pages: PdfOcrQualityPage[],
  filter: OcrQualityFilter,
  sort: OcrQualitySort,
) {
  const filtered = pages.filter((page) => {
    if (filter === "review") return page.needsReview;
    if (filter === "corrected") return page.hasCorrection;
    return true;
  });
  return filtered.sort((left, right) => {
    if (sort === "page") return left.pageNumber - right.pageNumber;
    if (left.needsReview !== right.needsReview) return left.needsReview ? -1 : 1;
    if (left.ocrConfidence === null) return 1;
    if (right.ocrConfidence === null) return -1;
    return left.ocrConfidence - right.ocrConfidence || left.pageNumber - right.pageNumber;
  });
}

/** 将质量页构造为现有来源预览能直接定位和校对的输入。 */
export function buildOcrPageSource(
  file: KnowledgeFile,
  page: PdfOcrQualityPage,
): ChatSource {
  return {
    title: file.name,
    fileId: file.id,
    fileName: file.name,
    fileType: "pdf",
    chunkIndex: page.chunkIndex,
    indexVersion: page.indexVersion,
    pageNumber: page.pageNumber,
    pageCount: page.pageCount ?? undefined,
    pdfParseMethod: "ocr",
    ocrConfidence: page.ocrConfidence ?? undefined,
    ocrQuality: page.ocrQuality,
    ocrCorrectionApplied: page.hasCorrection,
    ocrCorrectionRevision: page.correctionRevision,
    content: page.excerpt,
    metadata: `第 ${page.pageNumber} 页 OCR 质量巡检`,
  };
}
