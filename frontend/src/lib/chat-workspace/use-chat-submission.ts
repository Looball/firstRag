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
import { useChatResponseStream } from "./use-chat-response-stream";
import type { PendingChatImage } from "./use-pending-chat-images";
import type {
  ChatSession,
  MessageAttachment,
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
 * 将用户消息追加到目标会话，并在首条消息时更新标题。
 */
export function appendUserMessageToSessions(
  sessions: ChatSession[],
  sessionId: string,
  content: string,
  attachments: MessageAttachment[],
) {
  let hasChanged = false;
  const nextSessions = sessions.map((session) => {
    if (session.id !== sessionId) {
      return session;
    }

    hasChanged = true;
    return {
      ...session,
      title:
        session.messages.length === 0
          ? buildSessionTitle(content)
          : session.title,
      messages: [
        ...session.messages,
        {
          role: "user" as const,
          content,
          ...(attachments.length > 0 ? { attachments } : {}),
        },
      ],
    };
  });

  return hasChanged ? nextSessions : sessions;
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
 * 管理自动建会话、图片上传、用户消息事务和提交互斥状态。
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
  const { submitChatResponse } = useChatResponseStream({
    isAdvancedMode,
    loadDiagnostics,
    setLoadingSessions,
    setSessionErrors,
    setSessions,
    startChatRateLimitCountdown,
  });

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

        await submitChatResponse(
          activeSessionId,
          activeKnowledgeBaseId,
          messageContent,
          uploadedAttachments.map((attachment) => attachment.id),
        );
      } finally {
        isSubmittingRef.current = false;
      }
    },
    [
      clearPendingChatImages,
      createSession,
      currentSession,
      input,
      isChatImageRateLimited,
      isChatRateLimited,
      isCreatingSession,
      isCurrentSessionLoading,
      isUploadingChatImages,
      pendingChatImages,
      selectedKnowledgeBaseId,
      setInput,
      setPageError,
      setSessionErrors,
      setSessions,
      startChatImageRateLimitCountdown,
      submitChatResponse,
    ],
  );

  return {
    isUploadingChatImages,
    submitChat,
  };
}
