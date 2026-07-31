"use client";

import { type Dispatch, type SetStateAction, useEffect } from "react";
import * as chatApi from "./api";
import type { ChatSession, Message } from "./types";

type UseConversationMessageLoaderOptions = {
  activeSessionId: string;
  areActiveSessionMessagesLoaded: boolean;
  setSessionErrors: Dispatch<SetStateAction<Record<string, string>>>;
  setSessions: Dispatch<SetStateAction<ChatSession[]>>;
};

/**
 * 将已加载消息写回目标会话，同时保持其他会话引用不变。
 */
export function updateConversationMessages(
  sessions: ChatSession[],
  sessionId: string,
  messages: Message[],
) {
  return sessions.map((session) =>
    session.id === sessionId
      ? { ...session, messages, messagesLoaded: true }
      : session,
  );
}

/**
 * 将未知异常转换为会话消息加载使用的用户可见错误。
 */
export function getConversationMessageLoadError(error: unknown) {
  return error instanceof Error
    ? error.message
    : "读取会话消息失败，请稍后再试。";
}

/**
 * 按 active session 懒加载消息，并阻止切换会话后的旧响应写回。
 */
export function useConversationMessageLoader({
  activeSessionId,
  areActiveSessionMessagesLoaded,
  setSessionErrors,
  setSessions,
}: UseConversationMessageLoaderOptions) {
  useEffect(() => {
    let isCancelled = false;

    if (!activeSessionId || areActiveSessionMessagesLoaded) {
      return;
    }

    setSessionErrors((previous) => ({
      ...previous,
      [activeSessionId]: "",
    }));

    void chatApi
      .listConversationMessages(activeSessionId)
      .then((messages) => {
        if (!isCancelled) {
          setSessions((previous) =>
            updateConversationMessages(previous, activeSessionId, messages),
          );
        }
      })
      .catch((error) => {
        if (!isCancelled) {
          setSessionErrors((previous) => ({
            ...previous,
            [activeSessionId]: getConversationMessageLoadError(error),
          }));
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [
    activeSessionId,
    areActiveSessionMessagesLoaded,
    setSessionErrors,
    setSessions,
  ]);
}
