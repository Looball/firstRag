"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { loadPdfOcrQualityReport } from "@/lib/chat-workspace/api";
import type {
  KnowledgeFile,
  PdfOcrQualityPage,
} from "@/lib/chat-workspace/types";
import { formatOcrConfidence } from "@/lib/chat-workspace/utils";
import {
  buildOcrPageSource,
  filterAndSortOcrPages,
  type OcrQualityFilter,
  type OcrQualitySort,
} from "@/lib/chat-workspace/ocr-quality";

import { SourcePreviewDialog } from "./SourcePreviewDialog";

type OcrQualityInspectorDialogProps = {
  file: KnowledgeFile;
  onClose: () => void;
};

const FILTER_LABELS: Record<OcrQualityFilter, string> = {
  all: "全部 OCR 页",
  corrected: "已校对",
  review: "待处理",
};

/** 按页级状态返回刻度和列表共用的语义颜色。 */
function qualityTone(page: PdfOcrQualityPage) {
  if (page.hasCorrection) {
    return "border-[#4d9788] bg-[#cfe9e1] text-[#15594f]";
  }
  if (page.needsReview) {
    return "border-[#d08b24] bg-[#ffe2a8] text-[#6d4308]";
  }
  if (page.ocrConfidence === null) {
    return "border-[#aebbb6] bg-[#e7ece9] text-[#596662]";
  }
  return "border-[#9dbbb2] bg-[#e6f2ee] text-[#275f58]";
}

/** 展示单个已索引 PDF 的 OCR 页面质量队列。 */
export function OcrQualityInspectorDialog({
  file,
  onClose,
}: OcrQualityInspectorDialogProps) {
  const [filter, setFilter] = useState<OcrQualityFilter>("review");
  const [sort, setSort] = useState<OcrQualitySort>("confidence");
  const [selectedPage, setSelectedPage] = useState<PdfOcrQualityPage | null>(null);
  const reportQuery = useQuery({
    queryKey: ["pdf-ocr-quality-report", file.id],
    queryFn: () => loadPdfOcrQualityReport(file.id),
    staleTime: 30_000,
    retry: 1,
  });
  const report = reportQuery.data;
  const pageScale = useMemo(
    () => [...(report?.pages || [])].sort((left, right) => left.pageNumber - right.pageNumber),
    [report?.pages],
  );
  const visiblePages = useMemo(() => {
    return filterAndSortOcrPages(report?.pages || [], filter, sort);
  }, [filter, report?.pages, sort]);

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-[#17201f]/60 p-3 backdrop-blur-[2px] sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="ocr-quality-inspector-title"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section className="flex max-h-[94vh] w-full max-w-5xl flex-col border border-[#aebeb8] bg-[#f8faf7] shadow-2xl">
        <header className="flex items-start justify-between gap-4 border-b border-[#c8d4cf] px-4 py-4 sm:px-6">
          <div className="min-w-0">
            <p className="font-utility text-[10px] font-semibold uppercase tracking-[0.18em] text-[#176b62]">
              OCR Quality Review
            </p>
            <h2
              id="ocr-quality-inspector-title"
              className="mt-1 truncate text-xl font-semibold text-[#17201f] sm:text-2xl"
            >
              {file.name}
            </h2>
            <p className="mt-1 text-xs leading-5 text-[#64716d]">
              先处理置信度较低且尚未校对的页面；点击页码可直接核对原页并修改文本。
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="font-utility shrink-0 border border-[#bdc9c5] px-3 py-2 text-[10px] font-semibold uppercase text-[#52605c] transition-colors duration-150 hover:border-[#176b62] hover:text-[#176b62]"
          >
            关闭
          </button>
        </header>

        <div className="research-scroll min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5">
          {reportQuery.isPending ? (
            <div className="space-y-3" aria-live="polite">
              <div className="h-20 animate-pulse bg-[#e2e9e5]" />
              <div className="h-14 animate-pulse bg-[#e7ece9]" />
              <div className="h-28 animate-pulse bg-[#edf1ef]" />
              <p className="text-center text-xs text-[#64716d]">正在读取 OCR 页面质量...</p>
            </div>
          ) : reportQuery.isError ? (
            <div className="border border-[#d7a99b] bg-[#fff5f1] px-4 py-5 text-sm text-[#8f3d2d]">
              <p>
                {reportQuery.error instanceof Error
                  ? reportQuery.error.message
                  : "读取 OCR 质量巡检失败，请稍后再试。"}
              </p>
              <button
                type="button"
                onClick={() => reportQuery.refetch()}
                className="font-utility mt-3 border border-current px-3 py-2 text-[10px] font-semibold uppercase"
              >
                重新加载
              </button>
            </div>
          ) : !report?.pages.length ? (
            <div className="border border-[#cbd5d1] bg-white px-5 py-12 text-center">
              <p className="text-base font-semibold text-[#26312f]">当前索引没有 OCR 页面</p>
              <p className="mt-2 text-sm leading-6 text-[#64716d]">
                这个 PDF 可能自带可读取文本层，因此无需进行 OCR 质量巡检。
              </p>
            </div>
          ) : (
            <>
              <div className="grid border-y border-[#b8c7c2] bg-white sm:grid-cols-4">
                {[
                  ["待处理", report.summary.needsReviewCount, "优先校对"],
                  ["已校对", report.summary.correctedCount, "人工文本"],
                  ["OCR 页面", report.summary.ocrPageCount, `文档共 ${report.summary.documentPageCount} 页`],
                  ["平均置信度", formatOcrConfidence(report.summary.averageConfidence ?? undefined) || "—", "Tesseract"],
                ].map(([label, value, detail]) => (
                  <div key={label} className="border-b border-[#d7dfdc] px-4 py-3 last:border-b-0 sm:border-b-0 sm:border-r sm:last:border-r-0">
                    <p className="font-utility text-[9px] font-semibold uppercase tracking-[0.12em] text-[#72807b]">{label}</p>
                    <p className="mt-1 text-2xl font-semibold text-[#17201f]">{value}</p>
                    <p className="mt-1 text-[11px] text-[#7a8682]">{detail}</p>
                  </div>
                ))}
              </div>

              <section className="mt-5 border border-[#c5d0cc] bg-[#eef3f0] px-3 py-3" aria-label="页码质量刻度">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-utility text-[10px] font-semibold uppercase tracking-[0.14em] text-[#52605c]">页码质量刻度</p>
                  <p className="text-[10px] text-[#72807b]">琥珀：待处理 · 墨绿：已校对</p>
                </div>
                <div className="research-scroll mt-3 flex gap-1 overflow-x-auto pb-1">
                  {pageScale.map((page) => (
                    <button
                      key={page.pageNumber}
                      type="button"
                      onClick={() => setSelectedPage(page)}
                      aria-label={`第 ${page.pageNumber} 页，${page.hasCorrection ? "已校对" : page.needsReview ? "待处理" : "质量正常"}${page.ocrConfidence === null ? "" : `，置信度 ${formatOcrConfidence(page.ocrConfidence)}`}`}
                      className={`font-utility min-w-9 border px-2 py-2 text-[10px] font-semibold transition-transform duration-150 hover:-translate-y-0.5 ${qualityTone(page)}`}
                    >
                      {page.pageNumber}
                    </button>
                  ))}
                </div>
              </section>

              <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-b border-[#cbd5d1] pb-3">
                <div className="flex flex-wrap" role="group" aria-label="OCR 页面筛选">
                  {(Object.keys(FILTER_LABELS) as OcrQualityFilter[]).map((nextFilter) => (
                    <button
                      key={nextFilter}
                      type="button"
                      aria-pressed={filter === nextFilter}
                      onClick={() => setFilter(nextFilter)}
                      className={filter === nextFilter
                        ? "font-utility border border-[#176b62] bg-[#176b62] px-3 py-2 text-[10px] font-semibold uppercase text-white"
                        : "font-utility border border-[#b9c6c2] bg-white px-3 py-2 text-[10px] font-semibold uppercase text-[#52605c] hover:border-[#176b62]"}
                    >
                      {FILTER_LABELS[nextFilter]}
                    </button>
                  ))}
                </div>
                <div className="flex" role="group" aria-label="OCR 页面排序">
                  {(["confidence", "page"] as OcrQualitySort[]).map((nextSort) => (
                    <button
                      key={nextSort}
                      type="button"
                      aria-pressed={sort === nextSort}
                      onClick={() => setSort(nextSort)}
                      className={sort === nextSort
                        ? "font-utility border border-[#8ca8a1] bg-[#e4efeb] px-3 py-2 text-[9px] font-semibold uppercase text-[#176b62]"
                        : "font-utility border border-[#c5d0cc] bg-white px-3 py-2 text-[9px] font-semibold uppercase text-[#64716d]"}
                    >
                      {nextSort === "confidence" ? "低分优先" : "按页码"}
                    </button>
                  ))}
                </div>
              </div>

              {visiblePages.length ? (
                <div className="divide-y divide-[#d5ded9]">
                  {visiblePages.map((page) => (
                    <article
                      key={page.pageNumber}
                      className="grid gap-3 py-4 [content-visibility:auto] sm:grid-cols-[5rem_minmax(0,1fr)_auto] sm:items-center"
                    >
                      <div className={`w-fit min-w-16 border px-3 py-2 text-center ${qualityTone(page)}`}>
                        <p className="font-utility text-[9px] font-semibold uppercase">Page</p>
                        <p className="mt-1 text-xl font-semibold">{page.pageNumber}</p>
                      </div>
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2 text-xs">
                          <span className="font-semibold text-[#26312f]">
                            {page.ocrConfidence === null
                              ? "暂无置信度"
                              : `置信度 ${formatOcrConfidence(page.ocrConfidence)}`}
                          </span>
                          <span className="text-[#72807b]">
                            {page.hasCorrection
                              ? `已人工校对 · 修订 #${page.correctionRevision}`
                              : page.needsReview
                                ? "需要人工核对"
                                : "质量正常"}
                          </span>
                        </div>
                        <p className="mt-2 line-clamp-2 text-xs leading-5 text-[#64716d]">
                          {page.excerpt || "此页没有可展示的 OCR 文本摘要。"}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => setSelectedPage(page)}
                        className="font-utility w-full border border-[#176b62] bg-white px-4 py-2 text-[10px] font-semibold uppercase text-[#176b62] transition-colors duration-150 hover:bg-[#e7f1ed] sm:w-auto"
                      >
                        {page.hasCorrection ? "继续校对" : "校对这一页"}
                      </button>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="py-10 text-center">
                  <p className="text-sm font-semibold text-[#275f58]">
                    {filter === "review" ? "没有待处理的低置信度页面" : "当前筛选没有页面"}
                  </p>
                  <button
                    type="button"
                    onClick={() => setFilter("all")}
                    className="font-utility mt-3 border-b border-[#176b62] text-[10px] font-semibold uppercase text-[#176b62]"
                  >
                    查看全部 OCR 页
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </section>

      {selectedPage ? (
        <SourcePreviewDialog
          source={buildOcrPageSource(file, selectedPage)}
          initialCorrectionOpen
          onClose={() => {
            setSelectedPage(null);
            void reportQuery.refetch();
          }}
        />
      ) : null}
    </div>
  );
}
