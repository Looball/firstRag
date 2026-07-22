"use client";

import { useQuery } from "@tanstack/react-query";
import { useDeferredValue, useMemo, useState } from "react";

import { loadPdfOcrPageHistory } from "@/lib/chat-workspace/api";
import {
  buildOcrCorrectionDiff,
  type OcrCorrectionDiffSegment,
  type OcrCorrectionDiffStatus,
} from "@/lib/chat-workspace/ocr-correction-diff";
import type {
  KnowledgeFile,
  PdfOcrHistoryRun,
  PdfOcrQualityPage,
} from "@/lib/chat-workspace/types";
import { formatOcrConfidence } from "@/lib/chat-workspace/utils";

type OcrHistoryDialogProps = {
  file: KnowledgeFile;
  page: PdfOcrQualityPage;
  onClose: () => void;
};

const DIFF_STATUS_LABELS: Record<OcrCorrectionDiffStatus, string> = {
  added: "新增",
  modified: "修改",
  removed: "删除",
  unchanged: "未变",
};

const TRIGGER_LABELS: Record<string, string> = {
  file_index: "首次索引",
  legacy_snapshot: "历史基线",
  pdf_page_ocr_reindex: "单页重识别",
  pdf_pages_ocr_reindex: "批量重识别",
  pdf_page_ocr_correction_saved: "保存人工校对",
  pdf_page_ocr_correction_deleted: "撤销人工校对",
};

/** 格式化带符号的 OCR 指标变化。 */
function formatDelta(value: number | null, suffix = "") {
  if (value === null) return "—";
  const normalized = Number.isInteger(value) ? value.toFixed(0) : value.toFixed(2);
  return `${value > 0 ? "+" : ""}${normalized}${suffix}`;
}

/** 根据 confidence delta 返回趋势语义颜色。 */
function deltaTone(value: number | null) {
  if (value === null || value === 0) return "text-[#64716d]";
  return value > 0 ? "text-[#176b62]" : "text-[#9b3c29]";
}

/** 渲染一行 OCR 差异中的字符级变化。 */
function HistoryDiffSegments({
  segments,
  side,
}: {
  segments: OcrCorrectionDiffSegment[];
  side: "current" | "previous";
}) {
  if (!segments.length) return <span className="text-[#9aa5a1]">∅</span>;
  return segments.map((segment, index) =>
    segment.changed ? (
      <mark
        key={`${index}-${segment.text}`}
        className={side === "previous"
          ? "bg-[#f3c9bf] px-0.5 text-[#7d3124]"
          : "bg-[#bfe4d8] px-0.5 text-[#165d53]"}
      >
        {segment.text}
      </mark>
    ) : (
      <span key={`${index}-${segment.text}`}>{segment.text}</span>
    ),
  );
}

/** 展示单次 OCR 记录在识别账本中的标题与趋势。 */
function RunLedgerLabel({ run }: { run: PdfOcrHistoryRun }) {
  return (
    <>
      <span className="font-utility text-[9px] font-semibold uppercase tracking-[0.12em]">
        Run {String(run.ocrAttempt).padStart(2, "0")}
      </span>
      <span className="mt-1 flex items-baseline justify-between gap-2">
        <strong className="text-lg font-semibold">
          {formatOcrConfidence(run.ocrConfidence ?? undefined) || "—"}
        </strong>
        <span className={`font-utility text-[10px] font-semibold ${deltaTone(run.confidenceDelta)}`}>
          {formatDelta(run.confidenceDelta, "%")}
        </span>
      </span>
      <span className="mt-1 text-[10px] text-[#72807b]">
        {TRIGGER_LABELS[run.trigger] || "索引识别"}
      </span>
    </>
  );
}

/** 展示指定 PDF 页的 OCR 识别账本、质量趋势和相邻文本差异。 */
export function OcrHistoryDialog({
  file,
  page,
  onClose,
}: OcrHistoryDialogProps) {
  const [selectedRunIndex, setSelectedRunIndex] = useState(0);
  const [showOnlyChanges, setShowOnlyChanges] = useState(true);
  const deferredRunIndex = useDeferredValue(selectedRunIndex);
  const historyQuery = useQuery({
    queryKey: ["pdf-ocr-page-history", file.id, page.pageNumber],
    queryFn: () => loadPdfOcrPageHistory(file.id, page.pageNumber),
    staleTime: 30_000,
    retry: 1,
  });
  const report = historyQuery.data;
  const selectedRun = report?.runs[deferredRunIndex] || null;
  const previousRun = report?.runs[deferredRunIndex + 1] || null;
  const diff = useMemo(
    () => buildOcrCorrectionDiff(
      previousRun?.ocrText || "",
      selectedRun?.ocrText || "",
    ),
    [previousRun?.ocrText, selectedRun?.ocrText],
  );
  const visibleDiffRows = useMemo(
    () => showOnlyChanges
      ? diff.rows.filter((row) => row.status !== "unchanged")
      : diff.rows,
    [diff.rows, showOnlyChanges],
  );

  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center bg-[#17201f]/70 p-3 backdrop-blur-[3px] sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="ocr-history-title"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section className="flex max-h-[94vh] w-full max-w-6xl flex-col border border-[#9fb2ac] bg-[#f8faf7] shadow-2xl">
        <header className="flex items-start justify-between gap-4 border-b border-[#c8d4cf] px-4 py-4 sm:px-6">
          <div className="min-w-0">
            <p className="font-utility text-[10px] font-semibold uppercase tracking-[0.18em] text-[#176b62]">
              Recognition Ledger · Page {page.pageNumber}
            </p>
            <h2 id="ocr-history-title" className="mt-1 truncate text-xl font-semibold text-[#17201f] sm:text-2xl">
              OCR 识别历史
            </h2>
            <p className="mt-1 text-xs leading-5 text-[#64716d]">
              {file.name} · 对比每次 Tesseract 原始结果；人工校对文本不会替代这里的 OCR 记录。
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
          {historyQuery.isPending ? (
            <div className="space-y-3" aria-live="polite">
              <div className="h-20 animate-pulse bg-[#e2e9e5]" />
              <div className="h-72 animate-pulse bg-[#e7ece9]" />
              <p className="text-center text-xs text-[#64716d]">正在读取识别账本...</p>
            </div>
          ) : historyQuery.isError ? (
            <div className="border border-[#d7a99b] bg-[#fff5f1] px-4 py-5 text-sm text-[#8f3d2d]">
              <p>{historyQuery.error instanceof Error
                ? historyQuery.error.message
                : "读取 OCR 识别历史失败，请稍后再试。"}</p>
              <button
                type="button"
                onClick={() => historyQuery.refetch()}
                className="font-utility mt-3 border border-current px-3 py-2 text-[10px] font-semibold uppercase"
              >
                重新加载
              </button>
            </div>
          ) : !report?.runs.length || !selectedRun ? (
            <div className="border border-[#cbd5d1] bg-white px-5 py-12 text-center">
              <p className="text-base font-semibold text-[#26312f]">尚未建立识别历史</p>
              <p className="mt-2 text-sm leading-6 text-[#64716d]">
                这是迁移前的 OCR 页面。下一次重新识别时会先保存当前基线，再记录新结果。
              </p>
            </div>
          ) : (
            <>
              <div className="grid border-y border-[#b8c7c2] bg-white sm:grid-cols-4">
                {[
                  ["保留记录", report.summary.runCount, `上限 ${report.summary.retentionLimit} 次`],
                  ["当前置信度", formatOcrConfidence(report.summary.latestConfidence ?? undefined) || "—", formatDelta(report.summary.latestDelta, "%")],
                  ["最佳置信度", formatOcrConfidence(report.summary.bestConfidence ?? undefined) || "—", "历史最高"],
                  ["质量变化", `${report.summary.improvedCount} ↑`, `${report.summary.degradedCount} ↓ · ${report.summary.unchangedCount} 持平`],
                ].map(([label, value, detail]) => (
                  <div key={label} className="border-b border-[#d7dfdc] px-4 py-3 last:border-b-0 sm:border-b-0 sm:border-r sm:last:border-r-0">
                    <p className="font-utility text-[9px] font-semibold uppercase tracking-[0.12em] text-[#72807b]">{label}</p>
                    <p className="mt-1 text-2xl font-semibold text-[#17201f]">{value}</p>
                    <p className="mt-1 text-[11px] text-[#7a8682]">{detail}</p>
                  </div>
                ))}
              </div>

              <div className="mt-5 grid min-w-0 gap-4 lg:grid-cols-[12rem_minmax(0,1fr)]">
                <aside className="border border-[#bdcac6] bg-[#eef3f0] p-3" aria-label="OCR 识别账本">
                  <p className="font-utility text-[9px] font-semibold uppercase tracking-[0.15em] text-[#52605c]">
                    Recognition Runs
                  </p>
                  <div className="research-scroll mt-3 flex gap-2 overflow-x-auto pb-1 lg:max-h-[62vh] lg:flex-col lg:overflow-y-auto lg:overflow-x-hidden">
                    {report.runs.map((run, index) => (
                      <button
                        key={run.id}
                        type="button"
                        aria-pressed={selectedRunIndex === index}
                        aria-label={`第 ${run.ocrAttempt} 次识别，置信度 ${formatOcrConfidence(run.ocrConfidence ?? undefined) || "未知"}`}
                        onClick={() => setSelectedRunIndex(index)}
                        className={selectedRunIndex === index
                          ? "min-w-40 border-l-4 border-[#176b62] bg-white px-3 py-3 text-left text-[#17201f] shadow-sm transition-colors duration-150 lg:min-w-0"
                          : "min-w-40 border-l-4 border-[#b8c7c2] bg-[#f7f9f7] px-3 py-3 text-left text-[#52605c] transition-colors duration-150 hover:border-[#6e9d92] lg:min-w-0"}
                      >
                        <RunLedgerLabel run={run} />
                      </button>
                    ))}
                  </div>
                </aside>

                <section className="min-w-0 overflow-hidden border border-[#bdcac6] bg-white" aria-label="相邻 OCR 文本差异">
                  <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[#d3ddda] bg-[#f4f7f5] px-4 py-3">
                    <div>
                      <p className="font-utility text-[9px] font-semibold uppercase tracking-[0.14em] text-[#176b62]">
                        Run {selectedRun.ocrAttempt} vs {previousRun ? `Run ${previousRun.ocrAttempt}` : "Baseline"}
                      </p>
                      <h3 className="mt-1 text-base font-semibold text-[#17201f]">
                        {previousRun ? "相邻识别文本差异" : "首次识别原文"}
                      </h3>
                      <p className="mt-1 text-xs text-[#64716d]">
                        {new Date(selectedRun.createdAt).toLocaleString("zh-CN")} · {TRIGGER_LABELS[selectedRun.trigger] || "索引识别"}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2 text-xs">
                      <span className={`px-2 py-1 font-semibold ${deltaTone(selectedRun.confidenceDelta)} bg-[#edf2ef]`}>
                        置信度 {formatDelta(selectedRun.confidenceDelta, "%")}
                      </span>
                      <span className="bg-[#edf2ef] px-2 py-1 text-[#52605c]">
                        词数 {formatDelta(selectedRun.wordCountDelta)}
                      </span>
                      <span className="bg-[#edf2ef] px-2 py-1 text-[#52605c]">
                        {selectedRun.textChanged === null
                          ? "首次记录"
                          : selectedRun.textChanged
                            ? "文字有变化"
                            : "文字未变化"}
                      </span>
                    </div>
                  </div>

                  {previousRun ? (
                    <>
                      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#e0e6e3] px-3 py-2 text-xs">
                        <div className="flex flex-wrap gap-2" aria-live="polite">
                          {diff.changedRows ? (
                            <>
                              <span className="bg-[#fff0d2] px-2 py-1 text-[#71500d]">修改 {diff.modifiedRows}</span>
                              <span className="bg-[#e2f3ed] px-2 py-1 text-[#176b62]">新增 {diff.addedRows}</span>
                              <span className="bg-[#fae3dd] px-2 py-1 text-[#8f3d2d]">删除 {diff.removedRows}</span>
                            </>
                          ) : (
                            <span className="bg-[#e2f3ed] px-2 py-1 font-medium text-[#176b62]">两次 OCR 文字完全一致</span>
                          )}
                        </div>
                        {diff.changedRows ? (
                          <button
                            type="button"
                            aria-pressed={showOnlyChanges}
                            onClick={() => setShowOnlyChanges((current) => !current)}
                            className="font-utility border border-[#b7c6c1] px-2 py-1 text-[9px] font-semibold uppercase text-[#52605c]"
                          >
                            {showOnlyChanges ? "显示全部行" : "只看变化"}
                          </button>
                        ) : null}
                      </div>
                      <div className="research-scroll max-h-[55vh] overflow-auto">
                        <div className="min-w-[620px]" role="table" aria-label="相邻 OCR 识别文本差异">
                          <div className="sticky top-0 z-10 grid grid-cols-2 border-b border-[#cfd9d5] bg-[#eef2f0] text-xs font-semibold text-[#52605c]" role="row">
                            <div className="border-r border-[#cfd9d5] px-3 py-2" role="columnheader">Run {previousRun.ocrAttempt}</div>
                            <div className="px-3 py-2" role="columnheader">Run {selectedRun.ocrAttempt}</div>
                          </div>
                          {visibleDiffRows.length ? visibleDiffRows.map((row, index) => (
                            <div
                              key={`${row.originalLineNumber ?? "x"}-${row.correctedLineNumber ?? "x"}-${index}`}
                              className="grid grid-cols-2 border-b border-[#e3e8e6] [content-visibility:auto]"
                              role="row"
                            >
                              <div className={row.status === "removed" || row.status === "modified"
                                ? "grid min-w-0 grid-cols-[2.25rem_1fr] border-r border-[#d7dfdc] bg-[#fff7f5]"
                                : "grid min-w-0 grid-cols-[2.25rem_1fr] border-r border-[#d7dfdc]"} role="cell">
                                <span className="select-none border-r border-[#e0e6e3] px-2 py-2 text-right font-mono text-[10px] text-[#8b9692]">{row.originalLineNumber ?? ""}</span>
                                <p className="min-w-0 whitespace-pre-wrap break-words px-3 py-2 font-mono text-xs leading-5 text-[#34413e]">
                                  <HistoryDiffSegments segments={row.originalSegments} side="previous" />
                                </p>
                              </div>
                              <div className={row.status === "added" || row.status === "modified"
                                ? "grid min-w-0 grid-cols-[2.25rem_1fr] bg-[#f3fbf8]"
                                : "grid min-w-0 grid-cols-[2.25rem_1fr]"} role="cell">
                                <span className="select-none border-r border-[#e0e6e3] px-2 py-2 text-right font-mono text-[10px] text-[#8b9692]">{row.correctedLineNumber ?? ""}</span>
                                <p className="min-w-0 whitespace-pre-wrap break-words px-3 py-2 font-mono text-xs leading-5 text-[#34413e]">
                                  <HistoryDiffSegments segments={row.correctedSegments} side="current" />
                                </p>
                              </div>
                              <span className="sr-only">{DIFF_STATUS_LABELS[row.status]}</span>
                            </div>
                          )) : (
                            <p className="px-4 py-12 text-center text-sm text-[#64716d]">没有需要高亮的变化行。</p>
                          )}
                        </div>
                      </div>
                    </>
                  ) : (
                    <pre className="research-scroll max-h-[55vh] overflow-auto whitespace-pre-wrap break-words px-4 py-4 font-mono text-xs leading-6 text-[#34413e]">
                      {selectedRun.ocrText || "这次识别没有返回文字。"}
                    </pre>
                  )}
                </section>
              </div>
            </>
          )}
        </div>
      </section>
    </div>
  );
}
