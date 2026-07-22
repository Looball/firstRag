"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import {
  getVectorIndexJob,
  loadPdfOcrQualityReport,
  reindexKnowledgeFileOcrPages,
  retryKnowledgeFileOcrReindexBatch,
} from "@/lib/chat-workspace/api";
import type {
  KnowledgeFile,
  PdfOcrQualityPage,
} from "@/lib/chat-workspace/types";
import { formatOcrConfidence } from "@/lib/chat-workspace/utils";
import {
  buildOcrPageSource,
  filterAndSortOcrPages,
  mergeOcrPageSelection,
  toggleOcrPageSelection,
  type OcrQualityFilter,
  type OcrQualitySort,
} from "@/lib/chat-workspace/ocr-quality";

import { SourcePreviewDialog } from "./SourcePreviewDialog";
import { OcrHistoryDialog } from "./OcrHistoryDialog";

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
  const [historyPage, setHistoryPage] = useState<PdfOcrQualityPage | null>(null);
  const [selectedPageNumbers, setSelectedPageNumbers] = useState<number[]>([]);
  const [batchPageNumbers, setBatchPageNumbers] = useState<number[]>([]);
  const [batchJobId, setBatchJobId] = useState("");
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
  const maxBatchPages = report?.summary.maxReindexPages || 20;
  const selectedPageNumberSet = useMemo(
    () => new Set(selectedPageNumbers),
    [selectedPageNumbers],
  );
  const batchMutation = useMutation({
    mutationFn: (pageNumbers: number[]) =>
      reindexKnowledgeFileOcrPages(file.id, pageNumbers),
    onSuccess: (job, pageNumbers) => {
      setBatchPageNumbers(pageNumbers);
      setBatchJobId(job.id);
    },
  });
  const batchJobQuery = useQuery({
    queryKey: ["pdf-ocr-batch-reindex", batchJobId],
    queryFn: async () => {
      const job = await getVectorIndexJob(batchJobId);
      if (job?.status === "succeeded") {
        void reportQuery.refetch();
      }
      return job;
    },
    enabled: Boolean(batchJobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "processing" ? 1_000 : false;
    },
  });
  const batchJob = batchJobQuery.data;
  const retryBatchMutation = useMutation({
    mutationFn: (failedJobId: string) =>
      retryKnowledgeFileOcrReindexBatch(file.id, failedJobId),
    onSuccess: (job) => setBatchJobId(job.id),
  });
  const batchIsActive =
    batchMutation.isPending ||
    retryBatchMutation.isPending ||
    batchJob?.status === "queued" ||
    batchJob?.status === "processing";
  const batchError =
    batchMutation.error instanceof Error
      ? batchMutation.error.message
      : retryBatchMutation.error instanceof Error
        ? retryBatchMutation.error.message
        : batchJobQuery.error instanceof Error
          ? batchJobQuery.error.message
          : batchJob?.status === "failed"
            ? batchJob.errorMessage ||
              batchJob.failureHint ||
              "OCR 批次重新识别失败，请按原批次重试。"
            : "";
  const batchProgress = batchJob?.status === "succeeded"
    ? 100
    : batchJob?.status === "processing"
      ? 68
      : batchJob?.status === "queued" || batchMutation.isPending
        ? 22
        : batchJob?.status === "failed"
          ? 100
          : 0;

  function selectBatchPages(pageNumbers: number[]) {
    setSelectedPageNumbers((current) =>
      mergeOcrPageSelection(current, pageNumbers, maxBatchPages),
    );
  }

  function handleBatchRetry() {
    if (batchJobQuery.isError) {
      void batchJobQuery.refetch();
      return;
    }
    if (batchJob?.status === "failed") {
      retryBatchMutation.mutate(batchJob.id);
    }
  }

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

              <section
                className="mt-5 border border-[#b8c7c2] bg-white"
                aria-labelledby="ocr-batch-title"
              >
                <div className="grid gap-4 border-b border-[#d3ddda] px-4 py-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
                  <div>
                    <p className="font-utility text-[9px] font-semibold uppercase tracking-[0.15em] text-[#176b62]">
                      Re-OCR Batch
                    </p>
                    <h3 id="ocr-batch-title" className="mt-1 text-base font-semibold text-[#17201f]">
                      批量重新识别
                    </h3>
                    <p className="mt-1 max-w-2xl text-xs leading-5 text-[#64716d]">
                      所选页合并为一个队列任务，只重建一次整份文件。已人工校对页面保持人工文本，不加入批次。
                    </p>
                  </div>
                  <p className="font-utility text-[10px] font-semibold text-[#52605c]">
                    已选 {selectedPageNumbers.length} / {maxBatchPages} 页
                  </p>
                </div>

                <div className="px-4 py-4">
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={batchIsActive || !report.pages.some((page) => page.needsReview)}
                      onClick={() => selectBatchPages(
                        report.pages
                          .filter((page) => page.needsReview)
                          .map((page) => page.pageNumber),
                      )}
                      className="font-utility border border-[#c2ceca] px-3 py-2 text-[9px] font-semibold uppercase text-[#52605c] transition-colors duration-150 hover:border-[#d08b24] hover:text-[#7a4a08] disabled:cursor-not-allowed disabled:opacity-45"
                    >
                      选择待处理
                    </button>
                    <button
                      type="button"
                      disabled={batchIsActive || !visiblePages.some((page) => !page.hasCorrection)}
                      onClick={() => selectBatchPages(
                        visiblePages
                          .filter((page) => !page.hasCorrection)
                          .map((page) => page.pageNumber),
                      )}
                      className="font-utility border border-[#c2ceca] px-3 py-2 text-[9px] font-semibold uppercase text-[#52605c] transition-colors duration-150 hover:border-[#176b62] hover:text-[#176b62] disabled:cursor-not-allowed disabled:opacity-45"
                    >
                      选择当前筛选
                    </button>
                    <button
                      type="button"
                      disabled={batchIsActive || selectedPageNumbers.length === 0}
                      onClick={() => setSelectedPageNumbers([])}
                      className="font-utility border border-transparent px-3 py-2 text-[9px] font-semibold uppercase text-[#72807b] hover:text-[#9b3c29] disabled:cursor-not-allowed disabled:opacity-45"
                    >
                      清空选择
                    </button>
                  </div>

                  <div className="mt-4 flex min-h-10 flex-wrap items-center gap-1.5 border-y border-[#d8e0dd] bg-[#f4f7f5] px-3 py-2" aria-live="polite">
                    {selectedPageNumbers.length ? selectedPageNumbers.map((pageNumber) => (
                      <span
                        key={pageNumber}
                        className="font-utility border border-[#9dbbb2] bg-[#e6f2ee] px-2 py-1 text-[9px] font-semibold text-[#275f58]"
                      >
                        P{String(pageNumber).padStart(2, "0")}
                      </span>
                    )) : (
                      <span className="text-xs text-[#7a8682]">从下面的页面列表勾选需要重新识别的页面。</span>
                    )}
                  </div>

                  <div className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
                    <div>
                      {batchJobId ||
                      batchMutation.isPending ||
                      batchMutation.isError ||
                      retryBatchMutation.isError ? (
                        <div aria-live="polite">
                          <div className="h-1.5 overflow-hidden bg-[#e1e8e5]">
                            <div
                              className={`h-full origin-left transition-transform duration-300 motion-reduce:transition-none ${batchJob?.status === "failed" ? "bg-[#b9513c]" : "bg-[#176b62]"}`}
                              style={{ transform: `scaleX(${batchProgress / 100})` }}
                            />
                          </div>
                          <p className={`mt-2 text-xs ${batchError ? "text-[#9b3c29]" : "text-[#52605c]"}`}>
                            {batchError ||
                              (batchJob?.status === "succeeded"
                                ? `已完成 ${batchPageNumbers.length} 页重新识别，质量清单已刷新。`
                                : batchJob?.status === "processing"
                                  ? `Worker 正在重新识别 ${batchPageNumbers.length} 页并重建索引。`
                                  : `批次已进入队列，共 ${batchPageNumbers.length || selectedPageNumbers.length} 页。`)}
                          </p>
                        </div>
                      ) : (
                        <p className="text-xs leading-5 text-[#72807b]">
                          提交期间文件暂不可检索；完成后会自动刷新置信度和识别次数。
                        </p>
                      )}
                    </div>
                    {batchError && (batchJob?.status === "failed" || batchJobQuery.isError) ? (
                      <button
                        type="button"
                        disabled={retryBatchMutation.isPending}
                        onClick={handleBatchRetry}
                        className="font-utility border border-[#9b3c29] px-4 py-2 text-[10px] font-semibold uppercase text-[#9b3c29] disabled:opacity-50"
                      >
                        {retryBatchMutation.isPending
                          ? "重新排队中..."
                          : batchJobQuery.isError
                            ? "重试查询"
                            : "按原批次重试"}
                      </button>
                    ) : (
                      <button
                        type="button"
                        disabled={batchIsActive || selectedPageNumbers.length === 0}
                        onClick={() => batchMutation.mutate(selectedPageNumbers)}
                        className="font-utility border border-[#176b62] bg-[#176b62] px-4 py-2.5 text-[10px] font-semibold uppercase text-white transition-colors duration-150 hover:bg-[#105149] disabled:cursor-not-allowed disabled:border-[#9eb2ac] disabled:bg-[#9eb2ac]"
                      >
                        {batchIsActive
                          ? "批次处理中..."
                          : `重新识别 ${selectedPageNumbers.length} 页`}
                      </button>
                    )}
                  </div>
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
                      className="grid gap-3 py-4 [content-visibility:auto] sm:grid-cols-[auto_5rem_minmax(0,1fr)_auto] sm:items-center"
                    >
                      <input
                        type="checkbox"
                        aria-label={`选择第 ${page.pageNumber} 页重新识别`}
                        checked={selectedPageNumberSet.has(page.pageNumber)}
                        disabled={
                          batchIsActive ||
                          page.hasCorrection ||
                          (!selectedPageNumberSet.has(page.pageNumber) &&
                            selectedPageNumbers.length >= maxBatchPages)
                        }
                        onChange={() => setSelectedPageNumbers((current) =>
                          toggleOcrPageSelection(
                            current,
                            page.pageNumber,
                            maxBatchPages,
                          ))}
                        className="h-4 w-4 accent-[#176b62] disabled:cursor-not-allowed disabled:opacity-40"
                      />
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
                          <span className="text-[#8a9591]">第 {page.ocrAttempt} 次识别</span>
                          {page.latestConfidenceDelta !== null ? (
                            <span className={page.latestConfidenceDelta >= 0
                              ? "font-utility text-[10px] font-semibold text-[#176b62]"
                              : "font-utility text-[10px] font-semibold text-[#9b3c29]"}
                            >
                              最近 {page.latestConfidenceDelta > 0 ? "+" : ""}{page.latestConfidenceDelta.toFixed(2)}%
                            </span>
                          ) : null}
                        </div>
                        <p className="mt-2 line-clamp-2 text-xs leading-5 text-[#64716d]">
                          {page.excerpt || "此页没有可展示的 OCR 文本摘要。"}
                        </p>
                      </div>
                      <div className="flex w-full flex-wrap gap-2 sm:w-auto sm:justify-end">
                        <button
                          type="button"
                          onClick={() => setHistoryPage(page)}
                          className="font-utility flex-1 border border-[#8ca8a1] bg-[#eef5f2] px-3 py-2 text-[10px] font-semibold uppercase text-[#275f58] transition-colors duration-150 hover:border-[#176b62] sm:flex-none"
                        >
                          识别历史 {page.historyCount}
                        </button>
                        <button
                          type="button"
                          onClick={() => setSelectedPage(page)}
                          className="font-utility flex-1 border border-[#176b62] bg-white px-4 py-2 text-[10px] font-semibold uppercase text-[#176b62] transition-colors duration-150 hover:bg-[#e7f1ed] sm:flex-none"
                        >
                          {page.hasCorrection ? "继续校对" : "校对这一页"}
                        </button>
                      </div>
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

      {historyPage ? (
        <OcrHistoryDialog
          file={file}
          page={historyPage}
          onClose={() => setHistoryPage(null)}
        />
      ) : null}
    </div>
  );
}
