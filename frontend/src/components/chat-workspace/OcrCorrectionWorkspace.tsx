"use client";

import Image from "next/image";
import {
  useDeferredValue,
  useEffect,
  useMemo,
  useState,
} from "react";

import { loadKnowledgePdfPagePreview } from "@/lib/chat-workspace/api";
import {
  buildOcrCorrectionDiff,
  type OcrCorrectionDiffSegment,
  type OcrCorrectionDiffStatus,
} from "@/lib/chat-workspace/ocr-correction-diff";

type OcrCorrectionWorkspaceProps = {
  fileId: string;
  pageNumber: number;
  originalText: string;
  value: string;
  disabled: boolean;
  saving: boolean;
  onChange: (value: string) => void;
  onCancel: () => void;
  onOpenOriginalFile: () => void;
  onSave: () => void;
  openingOriginalFile: boolean;
};

type WorkspaceView = "diff" | "edit";

const DIFF_STATUS_LABELS: Record<OcrCorrectionDiffStatus, string> = {
  added: "新增",
  modified: "修改",
  removed: "删除",
  unchanged: "未变",
};

/** 渲染单行文本，并只给实际变化的字符添加语义化高亮。 */
function DiffSegments({
  segments,
  side,
}: {
  segments: OcrCorrectionDiffSegment[];
  side: "corrected" | "original";
}) {
  if (!segments.length) {
    return <span className="text-[#9aa5a1]">∅</span>;
  }
  return segments.map((segment, index) =>
    segment.changed ? (
      <mark
        key={`${index}-${segment.text}`}
        className={
          side === "original"
            ? "bg-[#f3c9bf] px-0.5 text-[#7d3124]"
            : "bg-[#bfe4d8] px-0.5 text-[#165d53]"
        }
      >
        {segment.text}
      </mark>
    ) : (
      <span key={`${index}-${segment.text}`}>{segment.text}</span>
    ),
  );
}

/** 提供目标 PDF 页、完整校对文本和前端差异视图。 */
export function OcrCorrectionWorkspace({
  fileId,
  pageNumber,
  originalText,
  value,
  disabled,
  saving,
  onChange,
  onCancel,
  onOpenOriginalFile,
  onSave,
  openingOriginalFile,
}: OcrCorrectionWorkspaceProps) {
  const [view, setView] = useState<WorkspaceView>("edit");
  const [showOnlyChanges, setShowOnlyChanges] = useState(true);
  const [pdfState, setPdfState] = useState({
    requestKey: "",
    previewUrl: "",
    error: "",
  });
  const [pdfReloadVersion, setPdfReloadVersion] = useState(0);
  const pdfRequestKey = `${fileId}:${pageNumber}:${pdfReloadVersion}`;
  const pdfPreviewUrl =
    pdfState.requestKey === pdfRequestKey ? pdfState.previewUrl : "";
  const pdfError = pdfState.requestKey === pdfRequestKey ? pdfState.error : "";
  const deferredValue = useDeferredValue(value);
  const diff = useMemo(
    () => buildOcrCorrectionDiff(originalText, deferredValue),
    [deferredValue, originalText],
  );
  const visibleDiffRows = useMemo(
    () =>
      showOnlyChanges
        ? diff.rows.filter((row) => row.status !== "unchanged")
        : diff.rows,
    [diff.rows, showOnlyChanges],
  );

  useEffect(() => {
    let active = true;
    let objectUrl = "";
    const requestKey = `${fileId}:${pageNumber}:${pdfReloadVersion}`;

    void loadKnowledgePdfPagePreview(fileId, pageNumber)
      .then((blob) => {
        if (blob.type && !blob.type.toLowerCase().includes("png")) {
          throw new Error("PDF 页面预览响应不是有效的 PNG。");
        }
        objectUrl = URL.createObjectURL(blob);
        if (!active) {
          URL.revokeObjectURL(objectUrl);
          return;
        }
        setPdfState({
          requestKey,
          previewUrl: objectUrl,
          error: "",
        });
      })
      .catch((error: unknown) => {
        if (!active) return;
        setPdfState({
          requestKey,
          previewUrl: "",
          error:
            error instanceof Error
              ? error.message
              : "PDF 页面加载失败，请稍后重试。",
        });
      });

    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [fileId, pageNumber, pdfReloadVersion]);

  const draftCharacterCount = value.trim().length;
  const differenceIsUpdating = deferredValue !== value;

  return (
    <div className="mt-4 border-t border-current/25 pt-4">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="font-utility text-[10px] font-semibold uppercase tracking-[0.14em]">
            OCR Correction Desk
          </p>
          <h3 className="mt-1 text-base font-semibold text-[#17201f]">
            第 {pageNumber} 页校对工作台
          </h3>
          <p className="mt-1 text-xs leading-5 text-[#64716d]">
            左侧核对扫描原页，右侧编辑全文或查看相对原 OCR 的变化。
          </p>
        </div>
        <button
          type="button"
          onClick={onOpenOriginalFile}
          disabled={openingOriginalFile}
          className="font-utility border border-[#8ca8a1] bg-white px-3 py-2 text-[10px] font-semibold uppercase text-[#275f58] transition-colors duration-150 hover:border-[#176b62] disabled:opacity-50"
        >
          {openingOriginalFile ? "正在打开" : "在新窗口打开 PDF"}
        </button>
      </div>

      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
        <section className="min-w-0 border border-[#b8c8c3] bg-[#dfe7e3]" aria-label="原始 PDF 页面">
          <div className="flex items-center justify-between border-b border-[#b8c8c3] bg-[#edf2ef] px-3 py-2">
            <p className="font-utility text-[10px] font-semibold uppercase tracking-[0.12em] text-[#52605c]">
              原始 PDF · 第 {pageNumber} 页
            </p>
            {pdfError ? (
              <button
                type="button"
                onClick={() => setPdfReloadVersion((version) => version + 1)}
                className="font-utility border border-[#a46b5e] px-2 py-1 text-[9px] font-semibold uppercase text-[#8f3d2d]"
              >
                重新加载
              </button>
            ) : null}
          </div>
          {pdfPreviewUrl ? (
            <div className="research-scroll h-[58vh] min-h-[28rem] overflow-auto bg-[#dfe7e3] p-3">
              <Image
                src={pdfPreviewUrl}
                alt={`原始 PDF 第 ${pageNumber} 页`}
                width={1800}
                height={2546}
                unoptimized
                className="mx-auto h-auto w-full max-w-[56rem] border border-[#c5cfcb] bg-white shadow-sm"
              />
            </div>
          ) : pdfError ? (
            <div className="flex h-[58vh] min-h-[28rem] flex-col items-center justify-center px-6 text-center">
              <p className="text-sm font-semibold text-[#8f3d2d]">PDF 页面未能加载</p>
              <p className="mt-2 max-w-md text-xs leading-5 text-[#6f4b43]">
                {pdfError} 校对草稿仍然保留，可重新加载或在新窗口打开原文件。
              </p>
            </div>
          ) : (
            <div
              className="flex h-[58vh] min-h-[28rem] flex-col items-center justify-center bg-[#e7ece9]"
              aria-live="polite"
            >
              <div className="h-3 w-40 animate-pulse bg-[#c2d0cb]" />
              <div className="mt-3 h-2 w-28 animate-pulse bg-[#ccd8d4]" />
              <p className="mt-4 text-xs text-[#64716d]">正在安全读取原始 PDF...</p>
            </div>
          )}
        </section>

        <section className="min-w-0 overflow-hidden border border-[#b8c8c3] bg-white" aria-label="OCR 校对文本">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#d1dad7] bg-[#f5f7f5] px-3 py-2">
            <div className="flex" role="group" aria-label="校对视图">
              {(["edit", "diff"] as const).map((nextView) => (
                <button
                  key={nextView}
                  type="button"
                  aria-pressed={view === nextView}
                  onClick={() => setView(nextView)}
                  className={
                    view === nextView
                      ? "font-utility border border-[#176b62] bg-[#176b62] px-3 py-1.5 text-[10px] font-semibold uppercase text-white"
                      : "font-utility border border-[#b7c6c1] bg-white px-3 py-1.5 text-[10px] font-semibold uppercase text-[#52605c] hover:border-[#176b62]"
                  }
                >
                  {nextView === "edit" ? "编辑全文" : "查看差异"}
                </button>
              ))}
            </div>
            <p className="font-utility text-[10px] text-[#64716d]">
              {draftCharacterCount.toLocaleString()} / 50,000 字符
            </p>
          </div>

          {view === "edit" ? (
            <div className="p-3">
              <label htmlFor="ocr-correction-text" className="sr-only">
                第 {pageNumber} 页完整校对文本
              </label>
              <textarea
                id="ocr-correction-text"
                value={value}
                onChange={(event) => onChange(event.target.value)}
                maxLength={50000}
                className="research-focus h-[calc(58vh-3.75rem)] min-h-[24rem] w-full resize-y border border-[#9fbcb5] bg-[#fffefb] px-4 py-3 font-mono text-sm leading-6 text-[#26312f]"
                spellCheck={false}
              />
              <p className="mt-2 text-xs leading-5 text-[#64716d]">
                修改只会在保存并完成异步重建后进入新索引；历史回答引用保持原版本。
              </p>
            </div>
          ) : (
            <div className="min-w-0 overflow-hidden">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#e0e6e3] px-3 py-2 text-xs">
                <div className="flex flex-wrap gap-2" aria-live="polite">
                  {diff.changedRows ? (
                    <>
                      <span className="bg-[#fff0d2] px-2 py-1 text-[#71500d]">
                        修改 {diff.modifiedRows}
                      </span>
                      <span className="bg-[#e2f3ed] px-2 py-1 text-[#176b62]">
                        新增 {diff.addedRows}
                      </span>
                      <span className="bg-[#fae3dd] px-2 py-1 text-[#8f3d2d]">
                        删除 {diff.removedRows}
                      </span>
                    </>
                  ) : (
                    <span className="bg-[#e2f3ed] px-2 py-1 font-medium text-[#176b62]">
                      当前文本与原 OCR 一致
                    </span>
                  )}
                  {differenceIsUpdating ? (
                    <span className="px-2 py-1 text-[#64716d]">正在更新差异...</span>
                  ) : null}
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
              <div className="research-scroll h-[calc(58vh-3.75rem)] min-h-[24rem] overflow-auto">
                <div className="min-w-[520px]" role="table" aria-label="原 OCR 与校对文本差异">
                  <div className="sticky top-0 z-10 grid grid-cols-2 border-b border-[#cfd9d5] bg-[#eef2f0] text-xs font-semibold text-[#52605c]" role="row">
                    <div className="border-r border-[#cfd9d5] px-3 py-2" role="columnheader">
                      原 OCR
                    </div>
                    <div className="px-3 py-2" role="columnheader">
                      当前校对文本
                    </div>
                  </div>
                  {visibleDiffRows.length ? (
                    visibleDiffRows.map((row, index) => (
                      <div
                        key={`${row.originalLineNumber ?? "x"}-${row.correctedLineNumber ?? "x"}-${index}`}
                        className="grid grid-cols-2 border-b border-[#e3e8e6] [content-visibility:auto]"
                        role="row"
                      >
                        <div
                          className={
                            row.status === "removed" || row.status === "modified"
                              ? "grid min-w-0 grid-cols-[2.25rem_1fr] border-r border-[#d7dfdc] bg-[#fff7f5]"
                              : "grid min-w-0 grid-cols-[2.25rem_1fr] border-r border-[#d7dfdc]"
                          }
                          role="cell"
                        >
                          <span className="select-none border-r border-[#e0e6e3] px-2 py-2 text-right font-mono text-[10px] text-[#8b9692]">
                            {row.originalLineNumber ?? ""}
                          </span>
                          <p className="min-w-0 whitespace-pre-wrap break-words px-3 py-2 font-mono text-xs leading-5 text-[#34413e]">
                            <DiffSegments segments={row.originalSegments} side="original" />
                          </p>
                        </div>
                        <div
                          className={
                            row.status === "added" || row.status === "modified"
                              ? "grid min-w-0 grid-cols-[2.25rem_1fr] bg-[#f3fbf8]"
                              : "grid min-w-0 grid-cols-[2.25rem_1fr]"
                          }
                          role="cell"
                        >
                          <span className="select-none border-r border-[#e0e6e3] px-2 py-2 text-right font-mono text-[10px] text-[#8b9692]">
                            {row.correctedLineNumber ?? ""}
                          </span>
                          <p className="min-w-0 whitespace-pre-wrap break-words px-3 py-2 font-mono text-xs leading-5 text-[#34413e]">
                            <DiffSegments segments={row.correctedSegments} side="corrected" />
                          </p>
                        </div>
                        <span className="sr-only">{DIFF_STATUS_LABELS[row.status]}</span>
                      </div>
                    ))
                  ) : (
                    <p className="px-4 py-12 text-center text-sm text-[#64716d]">
                      没有需要高亮的变化行。
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}
        </section>
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-current/20 pt-3">
        <p className="text-xs text-[#64716d]">
          保存后将重建整个文件索引，期间文件暂不可检索。
        </p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="font-utility border border-[#8ca8a1] bg-white px-4 py-2 text-[10px] font-semibold uppercase text-[#52605c]"
          >
            取消
          </button>
          <button
            type="button"
            disabled={disabled}
            onClick={onSave}
            className="font-utility border border-[#176b62] bg-[#176b62] px-4 py-2 text-[10px] font-semibold uppercase text-white transition-colors duration-150 hover:bg-[#105149] disabled:opacity-50"
          >
            {saving ? "保存中" : "保存并重建索引"}
          </button>
        </div>
      </div>
    </div>
  );
}
