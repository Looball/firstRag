"use client";

import {
  MarkdownContent,
  MessageAttachmentGrid,
} from "./MessageContent";
import {
  MessageSourceList,
  type SourceFeedbackRequest,
} from "./MessageSourceList";
import { AssistantMessageActions } from "./AssistantMessageActions";
import type {
  ChatSource,
  Message,
  MessageDiagnostic,
  MessageFeedbackReason,
} from "../../lib/chat-workspace/types";

export type ConversationMessageFeedbackState = {
  reasonDraft?: MessageFeedbackReason;
  noteDraft?: string;
  isPanelOpen: boolean;
  isSubmitting: boolean;
  errorMessage: string;
  successMessage: string;
};

export type ConversationMessageDiagnosticState = {
  isExpanded: boolean;
  diagnostic: MessageDiagnostic | null;
  isLoading: boolean;
  hasLoaded: boolean;
  errorMessage: string;
};

export type ConversationMessageEvalDraftState = {
  isExporting: boolean;
  errorMessage: string;
};

export type ConversationMessageSourceFeedbackState = {
  submitting: Record<string, boolean>;
  errors: Record<string, string>;
  messages: Record<string, string>;
};

export type ConversationMessageFeedbackRequest = {
  rating: "positive" | "negative";
  reason?: MessageFeedbackReason;
  note?: string;
};

export type ConversationMessageItemProps = {
  messageKey: string;
  message: Message;
  position: number;
  isLatestMessage: boolean;
  isCurrentSessionLoading: boolean;
  isAdvancedMode: boolean;
  isCopied: boolean;
  feedbackState: ConversationMessageFeedbackState;
  diagnosticState: ConversationMessageDiagnosticState;
  evalDraftState: ConversationMessageEvalDraftState;
  sourceFeedbackState: ConversationMessageSourceFeedbackState;
  onOpenSource: (source: ChatSource) => void;
  onSubmitSourceFeedback: (
    request: SourceFeedbackRequest,
  ) => void | Promise<void>;
  onSubmitMessageFeedback: (
    request: ConversationMessageFeedbackRequest,
  ) => void | Promise<void>;
  onToggleNegativeFeedback: () => void;
  onFeedbackReasonChange: (reason: MessageFeedbackReason) => void;
  onFeedbackNoteChange: (note: string) => void;
  onExportEvalDraft: () => void | Promise<void>;
  onToggleDiagnostics: () => void;
  onCopy: () => void | Promise<void>;
};

const isDevelopmentEnvironment = process.env.NODE_ENV === "development";

/**
 * 组合单条会话消息的内容、附件、引用和回答操作。
 *
 * 组件只派生展示状态并转发 callbacks；请求、缓存、draft state 和计时副作用由上层编排与 hooks 管理。
 */
export function ConversationMessageItem({
  messageKey,
  message,
  position,
  isLatestMessage,
  isCurrentSessionLoading,
  isAdvancedMode,
  isCopied,
  feedbackState,
  diagnosticState,
  evalDraftState,
  sourceFeedbackState,
  onOpenSource,
  onSubmitSourceFeedback,
  onSubmitMessageFeedback,
  onToggleNegativeFeedback,
  onFeedbackReasonChange,
  onFeedbackNoteChange,
  onExportEvalDraft,
  onToggleDiagnostics,
  onCopy,
}: ConversationMessageItemProps) {
  const isUserMessage = message.role === "user";
  const isStreamingPlaceholder =
    !isUserMessage &&
    isLatestMessage &&
    isCurrentSessionLoading &&
    !message.content;
  const sourceCount = message.sources?.length ?? 0;
  const shouldShowSources = !isUserMessage && sourceCount > 0;
  const displaySourceCount =
    message.retrieval && message.retrieval.source_count > 0
      ? message.retrieval.source_count
      : sourceCount;
  const retrievedCount =
    message.retrieval && message.retrieval.retrieved_count > 0
      ? message.retrieval.retrieved_count
      : null;
  const shouldShowRetrievalEmptyHint =
    !isUserMessage &&
    message.retrieval?.need_retrieval === true &&
    message.retrieval.source_count === 0 &&
    !shouldShowSources;
  const feedbackReason =
    feedbackState.reasonDraft ||
    message.feedback?.reason ||
    "missing_answer";
  const feedbackNote =
    feedbackState.noteDraft ?? message.feedback?.note ?? "";
  const canExportEvalDraft =
    isAdvancedMode &&
    isDevelopmentEnvironment &&
    !isUserMessage &&
    message.feedback?.rating === "negative";

  return (
    <div
      className={`relative grid min-w-0 gap-3 border-l-2 pl-5 md:grid-cols-[74px_minmax(0,1fr)] md:gap-5 md:pl-6 ${
        isUserMessage ? "border-[#e36b4f]" : "border-[#176b62]"
      }`}
    >
      <div className="font-utility pt-1 text-[10px] font-semibold uppercase text-[#72807b]">
        <span className="block text-[#17201f]">
          {String(position).padStart(2, "0")}
        </span>
        {isUserMessage ? "问题" : "回答"}
      </div>
      <article
        className={`min-w-0 px-5 py-4 ${
          isUserMessage
            ? "bg-[#17201f] text-white"
            : "border border-[#d5ded9] bg-[#f5f8f6] text-[#26312f]"
        }`}
      >
        <MarkdownContent
          content={
            isStreamingPlaceholder ? "AI 正在思考中..." : message.content
          }
          isUserMessage={isUserMessage}
        />

        {message.attachments && message.attachments.length > 0 && (
          <MessageAttachmentGrid
            attachments={message.attachments}
            isUserMessage={isUserMessage}
          />
        )}

        {shouldShowRetrievalEmptyHint && (
          <div className="mt-4 border-t border-[#d6dedb] pt-3">
            <p className="text-xs leading-5 text-[#64716d]">
              已检索知识库，但没有找到高相关引用
            </p>
          </div>
        )}

        {shouldShowSources && message.sources && (
          <MessageSourceList
            messageKey={messageKey}
            sources={message.sources}
            displaySourceCount={displaySourceCount}
            retrievedCount={retrievedCount}
            isAdvancedMode={isAdvancedMode}
            submittingFeedback={sourceFeedbackState.submitting}
            feedbackErrors={sourceFeedbackState.errors}
            feedbackMessages={sourceFeedbackState.messages}
            onOpenSource={onOpenSource}
            onSubmitFeedback={onSubmitSourceFeedback}
          />
        )}

        {!isUserMessage && message.content && (
          <AssistantMessageActions
            messageKey={messageKey}
            feedbackRating={message.feedback?.rating}
            feedbackReason={feedbackReason}
            feedbackNote={feedbackNote}
            isAdvancedMode={isAdvancedMode}
            isFeedbackPanelOpen={feedbackState.isPanelOpen}
            isFeedbackSubmitting={feedbackState.isSubmitting}
            feedbackError={feedbackState.errorMessage}
            feedbackMessage={feedbackState.successMessage}
            canExportEvalDraft={canExportEvalDraft}
            isExportingEvalDraft={evalDraftState.isExporting}
            evalDraftError={
              isDevelopmentEnvironment ? evalDraftState.errorMessage : ""
            }
            isDiagnosticExpanded={diagnosticState.isExpanded}
            diagnostic={diagnosticState.diagnostic}
            isDiagnosticLoading={diagnosticState.isLoading}
            hasLoadedDiagnostics={diagnosticState.hasLoaded}
            diagnosticError={diagnosticState.errorMessage}
            isCopied={isCopied}
            onPositiveFeedback={() =>
              onSubmitMessageFeedback({ rating: "positive" })
            }
            onToggleNegativeFeedback={onToggleNegativeFeedback}
            onFeedbackReasonChange={onFeedbackReasonChange}
            onFeedbackNoteChange={onFeedbackNoteChange}
            onSubmitNegativeFeedback={() =>
              onSubmitMessageFeedback({
                rating: "negative",
                reason: feedbackReason,
                note: feedbackNote,
              })
            }
            onExportEvalDraft={onExportEvalDraft}
            onToggleDiagnostics={onToggleDiagnostics}
            onCopy={onCopy}
          />
        )}
      </article>
    </div>
  );
}
