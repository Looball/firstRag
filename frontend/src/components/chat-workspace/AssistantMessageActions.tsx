"use client";

import { MessageDiagnosticsPanel } from "./MessageDiagnosticsPanel";
import type {
  MessageDiagnostic,
  MessageFeedbackRating,
  MessageFeedbackReason,
} from "../../lib/chat-workspace/types";

const MESSAGE_FEEDBACK_REASON_OPTIONS: Array<{
  value: MessageFeedbackReason;
  label: string;
}> = [
  { value: "missing_answer", label: "没有答到点" },
  { value: "irrelevant_sources", label: "引用不相关" },
  { value: "hallucination", label: "疑似幻觉" },
  { value: "outdated_or_wrong", label: "内容错误或过时" },
  { value: "too_slow", label: "回答太慢" },
  { value: "format_issue", label: "格式不好" },
  { value: "other", label: "其他" },
];

export type AssistantMessageActionsProps = {
  messageKey: string;
  feedbackRating?: MessageFeedbackRating;
  feedbackReason: MessageFeedbackReason;
  feedbackNote: string;
  isAdvancedMode: boolean;
  isFeedbackPanelOpen: boolean;
  isFeedbackSubmitting: boolean;
  feedbackError: string;
  feedbackMessage: string;
  canExportEvalDraft: boolean;
  isExportingEvalDraft: boolean;
  evalDraftError: string;
  isDiagnosticExpanded: boolean;
  diagnostic: MessageDiagnostic | null;
  isDiagnosticLoading: boolean;
  hasLoadedDiagnostics: boolean;
  diagnosticError: string;
  isCopied: boolean;
  onPositiveFeedback: () => void | Promise<void>;
  onToggleNegativeFeedback: () => void;
  onFeedbackReasonChange: (reason: MessageFeedbackReason) => void;
  onFeedbackNoteChange: (note: string) => void;
  onSubmitNegativeFeedback: () => void | Promise<void>;
  onExportEvalDraft: () => void | Promise<void>;
  onToggleDiagnostics: () => void;
  onCopy: () => void | Promise<void>;
};

/**
 * 展示回答反馈、Eval 草稿、diagnostics 和复制操作。
 *
 * API 请求、消息状态回写、诊断加载、文件导出和临时提示计时继续由页面层管理。
 */
export function AssistantMessageActions({
  messageKey,
  feedbackRating,
  feedbackReason,
  feedbackNote,
  isAdvancedMode,
  isFeedbackPanelOpen,
  isFeedbackSubmitting,
  feedbackError,
  feedbackMessage,
  canExportEvalDraft,
  isExportingEvalDraft,
  evalDraftError,
  isDiagnosticExpanded,
  diagnostic,
  isDiagnosticLoading,
  hasLoadedDiagnostics,
  diagnosticError,
  isCopied,
  onPositiveFeedback,
  onToggleNegativeFeedback,
  onFeedbackReasonChange,
  onFeedbackNoteChange,
  onSubmitNegativeFeedback,
  onExportEvalDraft,
  onToggleDiagnostics,
  onCopy,
}: AssistantMessageActionsProps) {
  const feedbackLabel =
    feedbackRating === "positive"
      ? "已标记：有用"
      : feedbackRating === "negative"
        ? "已标记：有问题"
        : "";

  return (
    <>
      {isAdvancedMode && isDiagnosticExpanded && (
        <MessageDiagnosticsPanel
          messageKey={messageKey}
          diagnostic={diagnostic}
          isLoading={isDiagnosticLoading}
          hasLoadedDiagnostics={hasLoadedDiagnostics}
          errorMessage={diagnosticError}
        />
      )}

      <div className="mt-4 border-t border-[#d6dedb] pt-3">
        <div
          className={`flex flex-wrap items-center gap-3 ${
            isAdvancedMode ? "justify-between" : "justify-end"
          }`}
        >
          {isAdvancedMode &&
            (feedbackRating && !isFeedbackSubmitting ? (
              <p
                className={`font-utility text-[10px] font-semibold uppercase ${
                  feedbackRating === "positive"
                    ? "text-[#176b62]"
                    : "text-[#9b3c29]"
                }`}
              >
                {feedbackLabel}
              </p>
            ) : (
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  disabled={isFeedbackSubmitting}
                  onClick={() => {
                    void onPositiveFeedback();
                  }}
                  className="font-utility border border-[#cbd5d1] px-2 py-1 text-[10px] font-semibold uppercase text-[#64716d] transition hover:border-[#176b62] hover:text-[#176b62] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isFeedbackSubmitting ? "保存中" : "有用"}
                </button>
                <button
                  type="button"
                  disabled={isFeedbackSubmitting}
                  onClick={onToggleNegativeFeedback}
                  className="font-utility border border-[#cbd5d1] px-2 py-1 text-[10px] font-semibold uppercase text-[#64716d] transition hover:border-[#e36b4f] hover:text-[#9b3c29] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  有问题
                </button>
              </div>
            ))}

          <div className="flex flex-wrap items-center gap-3">
            {canExportEvalDraft && (
              <button
                type="button"
                disabled={isExportingEvalDraft}
                onClick={() => {
                  void onExportEvalDraft();
                }}
                className="font-utility text-[10px] font-semibold uppercase text-[#64716d] transition hover:text-[#176b62] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isExportingEvalDraft ? "导出中" : "Eval 草稿"}
              </button>
            )}
            {isAdvancedMode && (
              <button
                type="button"
                onClick={onToggleDiagnostics}
                className="font-utility text-[10px] font-semibold uppercase text-[#64716d] transition hover:text-[#176b62]"
              >
                {isDiagnosticExpanded ? "收起诊断" : "诊断"}
              </button>
            )}
            <button
              type="button"
              onClick={() => {
                void onCopy();
              }}
              className="font-utility text-[10px] font-semibold uppercase text-[#64716d] transition hover:text-[#176b62]"
            >
              {isCopied ? "已复制" : "复制回答"}
            </button>
          </div>
        </div>

        {isAdvancedMode && isFeedbackPanelOpen && (
          <div className="mt-3 grid gap-2 border border-[#d5ded9] bg-[#fcfdfb] p-3">
            <div className="grid gap-2 md:grid-cols-[180px_minmax(0,1fr)]">
              <select
                value={feedbackReason}
                onChange={(event) =>
                  onFeedbackReasonChange(
                    event.target.value as MessageFeedbackReason,
                  )
                }
                className="border border-[#cbd5d1] bg-white px-2 py-2 text-xs text-[#26312f]"
              >
                {MESSAGE_FEEDBACK_REASON_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <input
                value={feedbackNote}
                onChange={(event) => onFeedbackNoteChange(event.target.value)}
                maxLength={1000}
                placeholder="可选补充说明"
                className="border border-[#cbd5d1] bg-white px-2 py-2 text-xs text-[#26312f]"
              />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-[#9b3c29]">{feedbackError}</p>
              <button
                type="button"
                disabled={isFeedbackSubmitting}
                onClick={() => {
                  void onSubmitNegativeFeedback();
                }}
                className="font-utility border border-[#e36b4f] px-3 py-2 text-[10px] font-semibold uppercase text-[#9b3c29] transition hover:bg-[#fff1ed] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isFeedbackSubmitting ? "保存中" : "提交反馈"}
              </button>
            </div>
          </div>
        )}

        {isAdvancedMode && !isFeedbackPanelOpen && feedbackError && (
          <p className="mt-2 text-xs text-[#9b3c29]">{feedbackError}</p>
        )}
        {isAdvancedMode &&
          !feedbackError &&
          feedbackMessage &&
          !feedbackRating && (
            <p className="mt-2 text-xs text-[#176b62]">{feedbackMessage}</p>
          )}
        {isAdvancedMode && evalDraftError && (
          <p className="mt-2 text-xs text-[#9b3c29]">{evalDraftError}</p>
        )}
      </div>
    </>
  );
}
