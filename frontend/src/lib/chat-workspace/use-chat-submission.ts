"use client";

import {
  type Dispatch,
  type SetStateAction,
  useCallback,
  useRef,
  useState,
} from "react";
import { DEFAULT_KNOWLEDGE_BASE_ID } from "./constants";
import * as chatApi from "./api";
import { streamChatResponse } from "./chat-stream";
import type { PendingChatImage } from "./use-pending-chat-images";
import type {
  ChatSession,
  ChatSource,
  Message,
  MessageAttachment,
  RetrievalState,
} from "./types";
import { buildSessionTitle } from "./utils";

type UseChatSubmissionOptions = {
  clearPendingChatImages: () => void;
  createSession: (
    knowledgeBaseId: string,
    title?: string,
  ) => Promise<ChatSession>;
  currentSession: ChatSession | null;
  input: string;
  isAdvancedMode: boolean;
  isChatImageRateLimited: boolean;
  isChatRateLimited: boolean;
  isCreatingSession: boolean;
  isCurrentSessionLoading: boolean;
  loadDiagnostics: (
    conversationId: string,
    options?: { silent?: boolean },
  ) => Promise<void>;
  pendingChatImages: PendingChatImage[];
  selectedKnowledgeBaseId: string;
  setInput: Dispatch<SetStateAction<string>>;
  setLoadingSessions: Dispatch<
    SetStateAction<Record<string, boolean>>
  >;
  setPageError: Dispatch<SetStateAction<string>>;
  setSessionErrors: Dispatch<SetStateAction<Record<string, string>>>;
  setSessions: Dispatch<SetStateAction<ChatSession[]>>;
  startChatImageRateLimitCountdown: (error: unknown) => boolean;
  startChatRateLimitCountdown: (error: unknown) => boolean;
};

/**
 * 更新目标会话；目标不存在或 updater 无变更时保留原引用。
 */
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

/**
 * 更新最后一条 assistant message；不存在时按指定内容创建。
 */
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

/**
 * 将用户消息追加到目标会话，并在首条消息时更新标题。
 */
export function appendUserMessageToSessions(
  sessions: ChatSession[],
  sessionId: string,
  content: string,
  attachments: MessageAttachment[],
) {
  return updateTargetSession(sessions, sessionId, (session) => ({
    ...session,
    title:
      session.messages.length === 0
        ? buildSessionTitle(content)
        : session.title,
    messages: [
      ...session.messages,
      {
        role: "user",
        content,
        ...(attachments.length > 0 ? { attachments } : {}),
      },
    ],
  }));
}

/**
 * 将流式内容追加到最后一条 assistant message。
 */
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

/**
 * 将引用来源写入最后一条 assistant message。
 */
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

/**
 * 将 retrieval 状态写入最后一条 assistant message。
 */
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

/**
 * 将持久化 message ID 写入已存在的最后一条 assistant message。
 */
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

/**
 * 用最终 fallback 内容覆盖或创建最后一条 assistant message。
 */
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

/**
 * 将未知异常转换为聊天提交使用的用户可见错误。
 */
export function getChatSubmissionError(
  error: unknown,
  fallbackMessage: string,
) {
  return error instanceof Error ? error.message : fallbackMessage;
}

/**
 * 管理自动建会话、图片上传、用户消息、SSE 回写和发送状态。
 *
 * sessions、输入框与会话 loading/error 仍由页面持有，hook 通过 React
 * setter 回写；页面只负责装配和展示。
 */
export function useChatSubmission({
  clearPendingChatImages,
  createSession,
  currentSession,
  input,
  isAdvancedMode,
  isChatImageRateLimited,
  isChatRateLimited,
  isCreatingSession,
  isCurrentSessionLoading,
  loadDiagnostics,
  pendingChatImages,
  selectedKnowledgeBaseId,
  setInput,
  setLoadingSessions,
  setPageError,
  setSessionErrors,
  setSessions,
  startChatImageRateLimitCountdown,
  startChatRateLimitCountdown,
}: UseChatSubmissionOptions) {
  const [isUploadingChatImages, setIsUploadingChatImages] = useState(false);
  const isSubmittingRef = useRef(false);

  const submitChat = useCallback(
    async (overrideInput?: string) => {
      const isImageUploadRateLimited =
        pendingChatImages.length > 0 && isChatImageRateLimited;

      if (
        isSubmittingRef.current ||
        isCurrentSessionLoading ||
        isCreatingSession ||
        isUploadingChatImages ||
        isChatRateLimited ||
        isImageUploadRateLimited
      ) {
        return;
      }

      const messageContent = (overrideInput ?? input).trim();

      if (!messageContent) {
        if (currentSession) {
          setSessionErrors((previous) => ({
            ...previous,
            [currentSession.id]: "请先在下方输入问题。",
          }));
        } else {
          setPageError("请先在下方输入问题。");
        }
        return;
      }

      if (
        !selectedKnowledgeBaseId ||
        selectedKnowledgeBaseId === DEFAULT_KNOWLEDGE_BASE_ID
      ) {
        setPageError("请先选择一个知识库。");
        return;
      }

      isSubmittingRef.current = true;

      try {
        let activeSession = currentSession;

        if (!activeSession) {
          setPageError("");

          try {
            activeSession = await createSession(
              selectedKnowledgeBaseId,
              buildSessionTitle(messageContent),
            );
          } catch (error) {
            setPageError(
              getChatSubmissionError(
                error,
                "创建对话失败，请稍后再试。",
              ),
            );
            return;
          }
        }

        setPageError("");

        const imagesToSend = [...pendingChatImages];
        let uploadedAttachments: MessageAttachment[] = [];

        if (imagesToSend.length > 0) {
          setIsUploadingChatImages(true);

          try {
            uploadedAttachments = await chatApi.uploadChatAttachments(
              activeSession.id,
              imagesToSend.map((image) => image.file),
            );
          } catch (error) {
            startChatImageRateLimitCountdown(error);
            setSessionErrors((previous) => ({
              ...previous,
              [activeSession.id]: getChatSubmissionError(
                error,
                "上传图片失败，请稍后再试。",
              ),
            }));
            return;
          } finally {
            setIsUploadingChatImages(false);
          }
        }

        const activeSessionId = activeSession.id;
        const activeKnowledgeBaseId = activeSession.knowledgeBaseId;

        setSessions((previous) =>
          appendUserMessageToSessions(
            previous,
            activeSessionId,
            messageContent,
            uploadedAttachments,
          ),
        );
        setInput("");

        if (imagesToSend.length > 0) {
          clearPendingChatImages();
        }

        setSessionErrors((previous) => ({
          ...previous,
          [activeSessionId]: "",
        }));
        setLoadingSessions((previous) => ({
          ...previous,
          [activeSessionId]: true,
        }));

        try {
          const response = await chatApi.postChatMessage(
            activeSessionId,
            activeKnowledgeBaseId,
            messageContent,
            uploadedAttachments.map((attachment) => attachment.id),
          );

          await streamChatResponse(response, {
            appendAssistantContent: (content) => {
              setSessions((previous) =>
                appendAssistantContentToSessions(
                  previous,
                  activeSessionId,
                  content,
                ),
              );
            },
            setAssistantFallback: (content) => {
              setSessions((previous) =>
                setAssistantFallbackInSessions(
                  previous,
                  activeSessionId,
                  content,
                ),
              );
            },
            setAssistantMessageId: (messageId) => {
              setSessions((previous) =>
                setAssistantMessageIdInSessions(
                  previous,
                  activeSessionId,
                  messageId,
                ),
              );
            },
            setAssistantRetrieval: (retrieval) => {
              setSessions((previous) =>
                setAssistantRetrievalInSessions(
                  previous,
                  activeSessionId,
                  retrieval,
                ),
              );
            },
            setAssistantSources: (sources) => {
              setSessions((previous) =>
                setAssistantSourcesInSessions(
                  previous,
                  activeSessionId,
                  sources,
                ),
              );
            },
            onDone: () => {
              if (isAdvancedMode) {
                void loadDiagnostics(activeSessionId, { silent: true });
              }
            },
          });
        } catch (error) {
          console.error(error);
          startChatRateLimitCountdown(error);
          setSessionErrors((previous) => ({
            ...previous,
            [activeSessionId]: getChatSubmissionError(
              error,
              "请求失败了，请稍后再试。",
            ),
          }));
        } finally {
          setLoadingSessions((previous) => ({
            ...previous,
            [activeSessionId]: false,
          }));
        }
      } finally {
        isSubmittingRef.current = false;
      }
    },
    [
      clearPendingChatImages,
      createSession,
      currentSession,
      input,
      isAdvancedMode,
      isChatImageRateLimited,
      isChatRateLimited,
      isCreatingSession,
      isCurrentSessionLoading,
      isUploadingChatImages,
      loadDiagnostics,
      pendingChatImages,
      selectedKnowledgeBaseId,
      setInput,
      setLoadingSessions,
      setPageError,
      setSessionErrors,
      setSessions,
      startChatImageRateLimitCountdown,
      startChatRateLimitCountdown,
    ],
  );

  return {
    isUploadingChatImages,
    submitChat,
  };
}
