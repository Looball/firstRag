"use client";

import {
  type Dispatch,
  type SetStateAction,
  useCallback,
  useEffect,
  useState,
} from "react";
import * as chatApi from "./api";
import { useSourceFeedbackActions } from "./use-source-feedback-actions";
import type {
  ChatSession,
  MessageFeedback,
  MessageFeedbackRating,
  MessageFeedbackReason,
} from "./types";

type SubmitMessageFeedbackOptions = {
  sessionId: string;
  messageKey: string;
  messageId?: string;
  rating: MessageFeedbackRating;
  reason?: MessageFeedbackReason | null;
  note?: string | null;
};

type UseMessageQualityActionsOptions = {
  isAdvancedMode: boolean;
  setSessions: Dispatch<SetStateAction<ChatSession[]>>;
};

export type EvalCaseDraftDownload = {
  fileName: string;
  content: string;
};

/**
 * 将回答反馈写回目标 session/message，同时保持其他会话引用不变。
 */
export function updateMessageFeedbackInSessions(
  sessions: ChatSession[],
  sessionId: string,
  messageId: string,
  feedback: MessageFeedback,
) {
  return sessions.map((session) =>
    session.id === sessionId
      ? {
          ...session,
          messages: session.messages.map((message) =>
            message.id === messageId
              ? {
                  ...message,
                  feedback,
                }
              : message,
          ),
        }
      : session,
  );
}

/**
 * 生成 Eval 草稿下载所需的安全文件名和格式化 JSON。
 */
export function serializeEvalCaseDraft(
  draft: Record<string, unknown>,
  messageId: string,
): EvalCaseDraftDownload {
  const draftId =
    typeof draft.id === "string" && draft.id.trim()
      ? draft.id.trim()
      : `draft_message_${messageId}`;

  return {
    fileName: `${draftId}.json`,
    content: `${JSON.stringify(draft, null, 2)}\n`,
  };
}

/**
 * 管理回答反馈与 Eval 草稿导出，并组合 source feedback actions。
 *
 * session 数据仍由页面持有；hook 只通过稳定的 React setter 回写目标消息。
 */
export function useMessageQualityActions({
  isAdvancedMode,
  setSessions,
}: UseMessageQualityActionsOptions) {
  const [activeFeedbackMessageKey, setActiveFeedbackMessageKey] = useState("");
  const [feedbackReasonDrafts, setFeedbackReasonDrafts] = useState<
    Record<string, MessageFeedbackReason>
  >({});
  const [feedbackNoteDrafts, setFeedbackNoteDrafts] = useState<
    Record<string, string>
  >({});
  const [submittingFeedback, setSubmittingFeedback] = useState<
    Record<string, boolean>
  >({});
  const [feedbackErrors, setFeedbackErrors] = useState<Record<string, string>>(
    {},
  );
  const [feedbackMessages, setFeedbackMessages] = useState<
    Record<string, string>
  >({});
  const [exportingEvalDrafts, setExportingEvalDrafts] = useState<
    Record<string, boolean>
  >({});
  const [evalDraftErrors, setEvalDraftErrors] = useState<Record<string, string>>(
    {},
  );
  const {
    sourceFeedbackErrors,
    sourceFeedbackMessages,
    submitSourceFeedback,
    submittingSourceFeedback,
  } = useSourceFeedbackActions({ setSessions });

  useEffect(() => {
    if (!isAdvancedMode) {
      setActiveFeedbackMessageKey("");
    }
  }, [isAdvancedMode]);

  const toggleFeedbackPanel = useCallback((messageKey: string) => {
    setActiveFeedbackMessageKey((current) =>
      current === messageKey ? "" : messageKey,
    );
  }, []);

  const updateFeedbackReasonDraft = useCallback(
    (messageKey: string, reason: MessageFeedbackReason) => {
      setFeedbackReasonDrafts((previous) => ({
        ...previous,
        [messageKey]: reason,
      }));
    },
    [],
  );

  const updateFeedbackNoteDraft = useCallback(
    (messageKey: string, note: string) => {
      setFeedbackNoteDrafts((previous) => ({
        ...previous,
        [messageKey]: note,
      }));
    },
    [],
  );

  const submitMessageFeedback = useCallback(
    async ({
      sessionId,
      messageKey,
      messageId,
      rating,
      reason,
      note,
    }: SubmitMessageFeedbackOptions) => {
      if (!messageId) {
        setFeedbackErrors((previous) => ({
          ...previous,
          [messageKey]: "这条回答还没有保存完成，稍后再反馈。",
        }));
        return;
      }

      setSubmittingFeedback((previous) => ({
        ...previous,
        [messageKey]: true,
      }));
      setFeedbackErrors((previous) => ({
        ...previous,
        [messageKey]: "",
      }));
      setFeedbackMessages((previous) => ({
        ...previous,
        [messageKey]: "正在保存反馈...",
      }));

      try {
        const feedback = await chatApi.submitMessageFeedback(messageId, {
          rating,
          reason: rating === "negative" ? reason || "other" : null,
          note: rating === "negative" ? note?.trim() || null : null,
        });

        setSessions((previous) =>
          updateMessageFeedbackInSessions(
            previous,
            sessionId,
            messageId,
            feedback,
          ),
        );
        setActiveFeedbackMessageKey((current) =>
          current === messageKey ? "" : current,
        );
        setFeedbackMessages((previous) => ({
          ...previous,
          [messageKey]:
            rating === "positive" ? "已标记为有用" : "已记录问题反馈",
        }));
        window.setTimeout(() => {
          setFeedbackMessages((previous) => {
            if (
              previous[messageKey] !== "已标记为有用" &&
              previous[messageKey] !== "已记录问题反馈"
            ) {
              return previous;
            }

            const next = { ...previous };
            delete next[messageKey];
            return next;
          });
        }, 2000);
      } catch (error) {
        setFeedbackMessages((previous) => {
          const next = { ...previous };
          delete next[messageKey];
          return next;
        });
        setFeedbackErrors((previous) => ({
          ...previous,
          [messageKey]:
            error instanceof Error ? error.message : "保存反馈失败，请稍后再试。",
        }));
      } finally {
        setSubmittingFeedback((previous) => ({
          ...previous,
          [messageKey]: false,
        }));
      }
    },
    [setSessions],
  );

  const exportEvalDraft = useCallback(
    async (messageKey: string, messageId?: string) => {
      if (!isAdvancedMode) {
        return;
      }

      if (!messageId) {
        setEvalDraftErrors((previous) => ({
          ...previous,
          [messageKey]: "这条回答还没有保存完成，稍后再导出。",
        }));
        return;
      }

      setExportingEvalDrafts((previous) => ({
        ...previous,
        [messageKey]: true,
      }));
      setEvalDraftErrors((previous) => ({
        ...previous,
        [messageKey]: "",
      }));

      try {
        const draft = await chatApi.exportEvalCaseDraft(messageId);
        const download = serializeEvalCaseDraft(draft, messageId);
        const blob = new Blob([download.content], {
          type: "application/json;charset=utf-8",
        });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");

        link.href = url;
        link.download = download.fileName;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
      } catch (error) {
        setEvalDraftErrors((previous) => ({
          ...previous,
          [messageKey]:
            error instanceof Error
              ? error.message
              : "导出 eval case 草稿失败，请稍后再试。",
        }));
      } finally {
        setExportingEvalDrafts((previous) => ({
          ...previous,
          [messageKey]: false,
        }));
      }
    },
    [isAdvancedMode],
  );

  return {
    activeFeedbackMessageKey,
    feedbackReasonDrafts,
    feedbackNoteDrafts,
    submittingFeedback,
    feedbackErrors,
    feedbackMessages,
    submittingSourceFeedback,
    sourceFeedbackErrors,
    sourceFeedbackMessages,
    exportingEvalDrafts,
    evalDraftErrors,
    toggleFeedbackPanel,
    updateFeedbackReasonDraft,
    updateFeedbackNoteDraft,
    submitMessageFeedback,
    submitSourceFeedback,
    exportEvalDraft,
  };
}
