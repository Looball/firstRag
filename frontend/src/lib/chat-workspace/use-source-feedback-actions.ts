"use client";

import {
  type Dispatch,
  type SetStateAction,
  useCallback,
  useState,
} from "react";
import * as chatApi from "./api";
import type {
  ChatSession,
  MessageSourceFeedback,
  MessageSourceFeedbackRating,
} from "./types";

type SubmitSourceFeedbackOptions = {
  sessionId: string;
  messageId?: string;
  sourceKey: string;
  sourceIndex: number;
  rating: MessageSourceFeedbackRating;
};

type UseSourceFeedbackActionsOptions = {
  setSessions: Dispatch<SetStateAction<ChatSession[]>>;
};

/** 按持久化 source index 或数组位置回写引用反馈。 */
export function updateSourceFeedbackInSessions(
  sessions: ChatSession[],
  sessionId: string,
  messageId: string,
  sourceIndex: number,
  feedback: MessageSourceFeedback,
) {
  return sessions.map((session) =>
    session.id === sessionId
      ? {
          ...session,
          messages: session.messages.map((message) =>
            message.id === messageId
              ? {
                  ...message,
                  sources: message.sources?.map((source, position) => {
                    const currentSourceIndex = source.index ?? position;

                    return currentSourceIndex === sourceIndex
                      ? {
                          ...source,
                          feedback,
                        }
                      : source;
                  }),
                }
              : message,
          ),
        }
      : session,
  );
}

/** 管理 source feedback 提交、状态提示和目标引用回写。 */
export function useSourceFeedbackActions({
  setSessions,
}: UseSourceFeedbackActionsOptions) {
  const [submittingSourceFeedback, setSubmittingSourceFeedback] = useState<
    Record<string, boolean>
  >({});
  const [sourceFeedbackErrors, setSourceFeedbackErrors] = useState<
    Record<string, string>
  >({});
  const [sourceFeedbackMessages, setSourceFeedbackMessages] = useState<
    Record<string, string>
  >({});

  const submitSourceFeedback = useCallback(
    async ({
      sessionId,
      messageId,
      sourceKey,
      sourceIndex,
      rating,
    }: SubmitSourceFeedbackOptions) => {
      if (!messageId) {
        setSourceFeedbackErrors((previous) => ({
          ...previous,
          [sourceKey]: "这条回答还没有保存完成，稍后再标记引用。",
        }));
        return;
      }

      setSubmittingSourceFeedback((previous) => ({
        ...previous,
        [sourceKey]: true,
      }));
      setSourceFeedbackErrors((previous) => ({
        ...previous,
        [sourceKey]: "",
      }));
      setSourceFeedbackMessages((previous) => ({
        ...previous,
        [sourceKey]: "正在保存引用反馈...",
      }));

      try {
        const feedback = await chatApi.submitMessageSourceFeedback(
          messageId,
          sourceIndex,
          { rating },
        );

        setSessions((previous) =>
          updateSourceFeedbackInSessions(
            previous,
            sessionId,
            messageId,
            sourceIndex,
            feedback,
          ),
        );
        setSourceFeedbackMessages((previous) => ({
          ...previous,
          [sourceKey]:
            rating === "useful" ? "已标记引用有用" : "已标记引用无关",
        }));
        window.setTimeout(() => {
          setSourceFeedbackMessages((previous) => {
            if (
              previous[sourceKey] !== "已标记引用有用" &&
              previous[sourceKey] !== "已标记引用无关"
            ) {
              return previous;
            }

            const next = { ...previous };
            delete next[sourceKey];
            return next;
          });
        }, 2000);
      } catch (error) {
        setSourceFeedbackMessages((previous) => {
          const next = { ...previous };
          delete next[sourceKey];
          return next;
        });
        setSourceFeedbackErrors((previous) => ({
          ...previous,
          [sourceKey]:
            error instanceof Error
              ? error.message
              : "保存引用反馈失败，请稍后再试。",
        }));
      } finally {
        setSubmittingSourceFeedback((previous) => ({
          ...previous,
          [sourceKey]: false,
        }));
      }
    },
    [setSessions],
  );

  return {
    sourceFeedbackErrors,
    sourceFeedbackMessages,
    submitSourceFeedback,
    submittingSourceFeedback,
  };
}
