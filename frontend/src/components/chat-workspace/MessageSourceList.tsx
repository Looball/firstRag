"use client";

import type {
  ChatSource,
  MessageSourceFeedbackRating,
} from "../../lib/chat-workspace/types";
import {
  formatOcrConfidence,
  formatSourcePosition,
} from "../../lib/chat-workspace/utils";

export type SourceFeedbackRequest = {
  sourceKey: string;
  sourceIndex: number;
  rating: MessageSourceFeedbackRating;
};

export type MessageSourceListProps = {
  messageKey: string;
  sources: ChatSource[];
  displaySourceCount: number;
  retrievedCount: number | null;
  isAdvancedMode: boolean;
  submittingFeedback: Record<string, boolean>;
  feedbackErrors: Record<string, string>;
  feedbackMessages: Record<string, string>;
  onOpenSource: (source: ChatSource) => void;
  onSubmitFeedback: (
    request: SourceFeedbackRequest,
  ) => void | Promise<void>;
};

/**
 * 展示回答引用、原文入口、检索 diagnostics 和 source feedback。
 *
 * 原文弹窗 state、feedback 请求、消息状态回写和提示计时继续由页面层管理。
 */
export function MessageSourceList({
  messageKey,
  sources,
  displaySourceCount,
  retrievedCount,
  isAdvancedMode,
  submittingFeedback,
  feedbackErrors,
  feedbackMessages,
  onOpenSource,
  onSubmitFeedback,
}: MessageSourceListProps) {
  return (
    <div className="mt-4 border-t border-[#d6dedb] pt-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-utility text-[10px] font-semibold uppercase text-[#64716d]">
          引用来源
        </p>
        <p className="text-xs text-[#64716d]">
          可展示 {displaySourceCount} 条
          {isAdvancedMode && retrievedCount !== null
            ? ` · 召回 ${retrievedCount} 段`
            : ""}
        </p>
      </div>
      <div className="mt-2 space-y-2">
        {sources.map((source, sourceIndex) => {
          const currentSourceIndex = source.index ?? sourceIndex;
          const sourceKey = `${messageKey}-source-${currentSourceIndex}`;
          const isSourceFeedbackSubmitting = Boolean(
            submittingFeedback[sourceKey],
          );
          const sourceFeedbackError = feedbackErrors[sourceKey] || "";
          const sourceFeedbackMessage = feedbackMessages[sourceKey] || "";
          const sourceFeedbackRating = source.feedback?.rating;
          const canPreviewSource =
            Boolean(source.fileId) && source.chunkIndex !== undefined;
          const sourceFeedbackLabel =
            sourceFeedbackRating === "useful"
              ? "已标记：引用有用"
              : sourceFeedbackRating === "irrelevant"
                ? "已标记：引用无关"
                : "";
          const sourceOcrConfidence = formatOcrConfidence(
            source.ocrConfidence,
          );
          const sourceFileMeta = [
            formatSourcePosition(source),
            source.pdfParseMethod === "ocr"
              ? source.ocrCorrectionApplied
                ? `已人工校对${source.ocrCorrectionRevision ? ` · 修订 #${source.ocrCorrectionRevision}` : ""}${sourceOcrConfidence ? ` · 原 OCR ${sourceOcrConfidence}` : ""}`
                : source.ocrQuality === "low"
                  ? `OCR 质量较低${sourceOcrConfidence ? ` ${sourceOcrConfidence}` : ""}`
                  : `OCR 识别${sourceOcrConfidence ? ` ${sourceOcrConfidence}` : ""}`
              : "",
            source.fileName !== source.title ? source.fileName : "",
            source.fileType,
            isAdvancedMode ? source.fileId : "",
          ]
            .filter(Boolean)
            .join(" · ");

          return (
            <div
              key={sourceKey}
              className="border border-[#d5ded9] bg-[#fcfdfb] px-3 py-2 text-xs text-[#46514e]"
            >
              <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
                <p className="min-w-0 truncate font-semibold text-[#17201f]">
                  {source.title}
                </p>
                {isAdvancedMode && (
                  <div className="font-utility flex min-w-0 basis-full flex-wrap justify-start gap-2 text-[10px] text-[#72807b] sm:basis-auto sm:shrink-0 sm:justify-end">
                    {source.chunkIndex !== undefined && (
                      <span>Chunk #{source.chunkIndex}</span>
                    )}
                    {source.retrievalSources &&
                      source.retrievalSources.length > 0 && (
                        <span>{source.retrievalSources.join(" / ")}</span>
                      )}
                    {source.vectorScore !== undefined && (
                      <span>Legacy Vector {source.vectorScore.toFixed(4)}</span>
                    )}
                    {source.fulltextScore !== undefined && (
                      <span>Legacy Fulltext {source.fulltextScore.toFixed(4)}</span>
                    )}
                    {source.denseScore !== undefined && (
                      <span>Dense {source.denseScore.toFixed(4)}</span>
                    )}
                    {source.sparseScore !== undefined && (
                      <span>Sparse {source.sparseScore.toFixed(4)}</span>
                    )}
                    {source.hybridScore !== undefined && (
                      <span>Hybrid {source.hybridScore.toFixed(4)}</span>
                    )}
                    {source.rerankScore !== undefined && (
                      <span>Rerank {source.rerankScore.toFixed(4)}</span>
                    )}
                    {source.rrfScore !== undefined && (
                      <span>RRF {source.rrfScore.toFixed(4)}</span>
                    )}
                    {source.metadata && <span>{source.metadata}</span>}
                  </div>
                )}
              </div>
              {source.content && (
                <p className="mt-1 max-h-10 overflow-hidden leading-5 text-[#64716d]">
                  {source.content}
                </p>
              )}
              {(sourceFileMeta || canPreviewSource) && (
                <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                  <p className="min-w-0 truncate text-[11px] text-[#72807b]">
                    {sourceFileMeta}
                  </p>
                  {canPreviewSource && (
                    <button
                      type="button"
                      onClick={() => onOpenSource(source)}
                      className="font-utility shrink-0 border border-[#8aa9a0] px-2.5 py-1 text-[10px] font-semibold uppercase text-[#176b62] transition hover:border-[#176b62] hover:bg-[#edf7f3]"
                    >
                      查看原文 →
                    </button>
                  )}
                </div>
              )}
              {isAdvancedMode && (
                <div className="mt-2 flex flex-wrap items-center justify-between gap-2 border-t border-[#e2e8e5] pt-2">
                  {sourceFeedbackRating &&
                  !isSourceFeedbackSubmitting ? (
                    <p
                      className={`font-utility text-[10px] font-semibold uppercase ${
                        sourceFeedbackRating === "useful"
                          ? "text-[#176b62]"
                          : "text-[#9b3c29]"
                      }`}
                    >
                      {sourceFeedbackLabel}
                    </p>
                  ) : (
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        disabled={isSourceFeedbackSubmitting}
                        onClick={() => {
                          void onSubmitFeedback({
                            sourceKey,
                            sourceIndex: currentSourceIndex,
                            rating: "useful",
                          });
                        }}
                        className="font-utility border border-[#cbd5d1] px-2 py-1 text-[10px] font-semibold uppercase text-[#64716d] transition hover:border-[#176b62] hover:text-[#176b62] disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {isSourceFeedbackSubmitting ? "保存中" : "引用有用"}
                      </button>
                      <button
                        type="button"
                        disabled={isSourceFeedbackSubmitting}
                        onClick={() => {
                          void onSubmitFeedback({
                            sourceKey,
                            sourceIndex: currentSourceIndex,
                            rating: "irrelevant",
                          });
                        }}
                        className="font-utility border border-[#cbd5d1] px-2 py-1 text-[10px] font-semibold uppercase text-[#64716d] transition hover:border-[#e36b4f] hover:text-[#9b3c29] disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {isSourceFeedbackSubmitting ? "保存中" : "引用无关"}
                      </button>
                    </div>
                  )}
                  {sourceFeedbackError && (
                    <p className="text-[11px] text-[#9b3c29]">
                      {sourceFeedbackError}
                    </p>
                  )}
                  {!sourceFeedbackError && sourceFeedbackMessage && (
                    <p className="text-[11px] text-[#176b62]">
                      {sourceFeedbackMessage}
                    </p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
