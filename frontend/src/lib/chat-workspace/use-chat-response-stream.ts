"use client";

import {
  type Dispatch,
  type SetStateAction,
  useCallback,
} from "react";
import * as chatApi from "./api";
import { streamChatResponse } from "./chat-stream";
import type {
  ChatSession,
  ChatSource,
  Message,
  RetrievalState,
} from "./types";

type UseChatResponseStreamOptions = {
  isAdvancedMode: boolean;
  loadDiagnostics: (
    conversationId: string,
    options?: { silent?: boolean },
  ) => Promise<void>;
  setLoadingSessions: Dispatch<
    SetStateAction<Record<string, boolean>>
  >;
  setSessionErrors: Dispatch<SetStateAction<Record<string, string>>>;
  setSessions: Dispatch<SetStateAction<ChatSession[]>>;
  startChatRateLimitCountdown: (error: unknown) => boolean;
};

/** 更新目标会话；目标不存在或 updater 无变更时保留原引用。 */
function updateTargetSession(
  sessions: ChatSession[],
  sessionId: string,
  updater: (session: ChatSession) => ChatSession,
) {
  let hasChanged = false;
  const nextSessions = sessions.map((session) => {
    if (session.id !== sessionId) {
      return session;
    }

    const nextSession = updater(session);
    hasChanged ||= nextSession !== session;
    return nextSession;
  });

  return hasChanged ? nextSessions : sessions;
}

/** 更新最后一条 assistant message；不存在时按指定内容创建。 */
function upsertLastAssistantMessage(
  messages: Message[],
  createMessage: () => Message,
  updater: (message: Message) => Message,
) {
  const lastMessage = messages[messages.length - 1];

  if (lastMessage?.role !== "assistant") {
    return [...messages, createMessage()];
  }

  const nextMessages = [...messages];
  nextMessages[nextMessages.length - 1] = updater(lastMessage);
  return nextMessages;
}

/** 将流式内容追加到最后一条 assistant message。 */
export function appendAssistantContentToSessions(
  sessions: ChatSession[],
  sessionId: string,
  content: string,
) {
  return updateTargetSession(sessions, sessionId, (session) => ({
    ...session,
    messages: upsertLastAssistantMessage(
      session.messages,
      () => ({ role: "assistant", content }),
      (message) => ({
        ...message,
        content: message.content + content,
      }),
    ),
  }));
}

/** 将引用来源写入最后一条 assistant message。 */
export function setAssistantSourcesInSessions(
  sessions: ChatSession[],
  sessionId: string,
  sources: ChatSource[],
) {
  if (sources.length === 0) {
    return sessions;
  }

  return updateTargetSession(sessions, sessionId, (session) => ({
    ...session,
    messages: upsertLastAssistantMessage(
      session.messages,
      () => ({ role: "assistant", content: "", sources }),
      (message) => ({ ...message, sources }),
    ),
  }));
}

/** 将 retrieval 状态写入最后一条 assistant message。 */
export function setAssistantRetrievalInSessions(
  sessions: ChatSession[],
  sessionId: string,
  retrieval: RetrievalState,
) {
  return updateTargetSession(sessions, sessionId, (session) => ({
    ...session,
    messages: upsertLastAssistantMessage(
      session.messages,
      () => ({ role: "assistant", content: "", retrieval }),
      (message) => ({ ...message, retrieval }),
    ),
  }));
}

/** 将持久化 message ID 写入已存在的最后一条 assistant message。 */
export function setAssistantMessageIdInSessions(
  sessions: ChatSession[],
  sessionId: string,
  messageId: string,
) {
  if (!messageId) {
    return sessions;
  }

  return updateTargetSession(sessions, sessionId, (session) => {
    const lastMessage = session.messages[session.messages.length - 1];

    if (lastMessage?.role !== "assistant") {
      return session;
    }

    const messages = [...session.messages];
    messages[messages.length - 1] = {
      ...lastMessage,
      id: messageId,
    };
    return { ...session, messages };
  });
}

/** 用最终 fallback 内容覆盖或创建最后一条 assistant message。 */
export function setAssistantFallbackInSessions(
  sessions: ChatSession[],
  sessionId: string,
  content: string,
) {
  return updateTargetSession(sessions, sessionId, (session) => ({
    ...session,
    messages: upsertLastAssistantMessage(
      session.messages,
      () => ({ role: "assistant", content }),
      (message) => ({ ...message, content }),
    ),
  }));
}

/** 管理 chat 请求、SSE assistant 回写、错误限流和 diagnostics preload。 */
export function useChatResponseStream({
  isAdvancedMode,
  loadDiagnostics,
  setLoadingSessions,
  setSessionErrors,
  setSessions,
  startChatRateLimitCountdown,
}: UseChatResponseStreamOptions) {
  const submitChatResponse = useCallback(
    async (
      sessionId: string,
      knowledgeBaseId: string,
      messageContent: string,
      attachmentIds: string[],
    ) => {
      setSessionErrors((previous) => ({
        ...previous,
        [sessionId]: "",
      }));
      setLoadingSessions((previous) => ({
        ...previous,
        [sessionId]: true,
      }));

      try {
        const response = await chatApi.postChatMessage(
          sessionId,
          knowledgeBaseId,
          messageContent,
          attachmentIds,
        );

        await streamChatResponse(response, {
          appendAssistantContent: (content) => {
            setSessions((previous) =>
              appendAssistantContentToSessions(
                previous,
                sessionId,
                content,
              ),
            );
          },
          setAssistantFallback: (content) => {
            setSessions((previous) =>
              setAssistantFallbackInSessions(
                previous,
                sessionId,
                content,
              ),
            );
          },
          setAssistantMessageId: (messageId) => {
            setSessions((previous) =>
              setAssistantMessageIdInSessions(
                previous,
                sessionId,
                messageId,
              ),
            );
          },
          setAssistantRetrieval: (retrieval) => {
            setSessions((previous) =>
              setAssistantRetrievalInSessions(
                previous,
                sessionId,
                retrieval,
              ),
            );
          },
          setAssistantSources: (sources) => {
            setSessions((previous) =>
              setAssistantSourcesInSessions(
                previous,
                sessionId,
                sources,
              ),
            );
          },
          onDone: () => {
            if (isAdvancedMode) {
              void loadDiagnostics(sessionId, { silent: true });
            }
          },
        });
      } catch (error) {
        console.error(error);
        startChatRateLimitCountdown(error);
        setSessionErrors((previous) => ({
          ...previous,
          [sessionId]:
            error instanceof Error
              ? error.message
              : "请求失败了，请稍后再试。",
        }));
      } finally {
        setLoadingSessions((previous) => ({
          ...previous,
          [sessionId]: false,
        }));
      }
    },
    [
      isAdvancedMode,
      loadDiagnostics,
      setLoadingSessions,
      setSessionErrors,
      setSessions,
      startChatRateLimitCountdown,
    ],
  );

  return {
    submitChatResponse,
  };
}
