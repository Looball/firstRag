"use client";

import {
  type Dispatch,
  type SetStateAction,
  useCallback,
  useState,
} from "react";
import * as chatApi from "./api";
import type { ChatSession } from "./types";
import { useConversationMessageLoader } from "./use-conversation-message-loader";

type UseConversationActionsOptions = {
  activeSessionId: string;
  canCreateSession: boolean;
  onClearComposer: () => void;
  selectedKnowledgeBaseId: string;
  sessions: ChatSession[];
  setActiveSessionId: Dispatch<SetStateAction<string>>;
  setLoadingSessions: Dispatch<SetStateAction<Record<string, boolean>>>;
  setPageError: Dispatch<SetStateAction<string>>;
  setSessionErrors: Dispatch<SetStateAction<Record<string, string>>>;
  setSessions: Dispatch<SetStateAction<ChatSession[]>>;
};

export type DeleteSessionResult = {
  knowledgeBaseId: string;
  nextActiveSessionId: string;
  remainingSessions: ChatSession[];
  shouldClearComposer: boolean;
};

/**
 * 将未知异常转换为会话操作使用的用户可见错误。
 */
export function getConversationActionError(
  error: unknown,
  fallbackMessage: string,
) {
  return error instanceof Error ? error.message : fallbackMessage;
}

/**
 * 保留现有空标题回退规则。
 */
export function normalizeSessionTitle(title: string) {
  return title.trim() || "新对话";
}

/**
 * 更新目标会话标题，同时保持其他会话引用不变。
 */
export function renameSession(
  sessions: ChatSession[],
  sessionId: string,
  title: string,
) {
  return sessions.map((session) =>
    session.id === sessionId ? { ...session, title } : session,
  );
}

/**
 * 从按会话 ID 存储的状态记录中移除目标键。
 */
export function removeSessionRecord<T>(
  record: Record<string, T>,
  sessionId: string,
) {
  const nextRecord = { ...record };
  delete nextRecord[sessionId];
  return nextRecord;
}

/**
 * 计算删除后的会话列表、当前选择和 composer 清理行为。
 */
export function getDeleteSessionResult(
  sessions: ChatSession[],
  sessionId: string,
  selectedKnowledgeBaseId: string,
  activeSessionId: string,
): DeleteSessionResult {
  const deletedSession = sessions.find((session) => session.id === sessionId);
  const knowledgeBaseId =
    deletedSession?.knowledgeBaseId || selectedKnowledgeBaseId;
  const remainingSessions = sessions.filter(
    (session) => session.id !== sessionId,
  );
  const remainingVisibleSessions = remainingSessions.filter(
    (session) => session.knowledgeBaseId === knowledgeBaseId,
  );
  const deletedActiveSession = activeSessionId === sessionId;

  return {
    knowledgeBaseId,
    nextActiveSessionId:
      remainingVisibleSessions.length === 0
        ? ""
        : deletedActiveSession
          ? remainingVisibleSessions[0].id
          : activeSessionId,
    remainingSessions,
    shouldClearComposer:
      remainingVisibleSessions.length === 0 || deletedActiveSession,
  };
}

/**
 * 管理会话创建、选择、重命名和删除的请求与侧栏交互状态。
 *
 * sessions 和聊天流状态仍由页面持有；hook 仅通过 React setter 回写。
 */
export function useConversationActions({
  activeSessionId,
  canCreateSession,
  onClearComposer,
  selectedKnowledgeBaseId,
  sessions,
  setActiveSessionId,
  setLoadingSessions,
  setPageError,
  setSessionErrors,
  setSessions,
}: UseConversationActionsOptions) {
  const [editingSessionId, setEditingSessionId] = useState("");
  const [editingTitle, setEditingTitle] = useState("");
  const [renamingSessionId, setRenamingSessionId] = useState("");
  const [deletingSessionId, setDeletingSessionId] = useState("");
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const areActiveSessionMessagesLoaded =
    sessions.find((session) => session.id === activeSessionId)
      ?.messagesLoaded ?? true;

  useConversationMessageLoader({
    activeSessionId,
    areActiveSessionMessagesLoaded,
    setSessionErrors,
    setSessions,
  });

  const createSession = useCallback(
    async (knowledgeBaseId: string, title = "新对话") => {
      setIsCreatingSession(true);

      try {
        const newSession = await chatApi.createConversation(
          knowledgeBaseId,
          title,
        );
        setSessions((previous) => [newSession, ...previous]);
        setActiveSessionId(newSession.id);
        return newSession;
      } finally {
        setIsCreatingSession(false);
      }
    },
    [setActiveSessionId, setSessions],
  );

  const createSelectedSession = useCallback(async () => {
    if (!canCreateSession) {
      setPageError("请先选择一个知识库。");
      return;
    }

    setPageError("");

    try {
      await createSession(selectedKnowledgeBaseId);
      onClearComposer();
    } catch (error) {
      setPageError(
        getConversationActionError(
          error,
          "创建对话失败，请稍后再试。",
        ),
      );
    }
  }, [
    canCreateSession,
    createSession,
    onClearComposer,
    selectedKnowledgeBaseId,
    setPageError,
  ]);

  const selectSession = useCallback(
    (session: ChatSession) => {
      setActiveSessionId(session.id);
    },
    [setActiveSessionId],
  );

  const deleteSession = useCallback(
    async (sessionId: string) => {
      if (deletingSessionId) {
        return;
      }

      const deleteResult = getDeleteSessionResult(
        sessions,
        sessionId,
        selectedKnowledgeBaseId,
        activeSessionId,
      );

      setDeletingSessionId(sessionId);
      setPageError("");

      try {
        await chatApi.deleteConversation(
          deleteResult.knowledgeBaseId,
          sessionId,
        );
        setSessions(deleteResult.remainingSessions);
        setLoadingSessions((previous) =>
          removeSessionRecord(previous, sessionId),
        );
        setSessionErrors((previous) =>
          removeSessionRecord(previous, sessionId),
        );

        if (editingSessionId === sessionId) {
          setEditingSessionId("");
          setEditingTitle("");
        }

        setActiveSessionId(deleteResult.nextActiveSessionId);
        if (deleteResult.shouldClearComposer) {
          onClearComposer();
        }
      } catch (error) {
        setPageError(
          getConversationActionError(
            error,
            "删除会话失败，请稍后再试。",
          ),
        );
      } finally {
        setDeletingSessionId("");
      }
    },
    [
      activeSessionId,
      deletingSessionId,
      editingSessionId,
      onClearComposer,
      selectedKnowledgeBaseId,
      sessions,
      setActiveSessionId,
      setLoadingSessions,
      setPageError,
      setSessionErrors,
      setSessions,
    ],
  );

  const startRename = useCallback((session: ChatSession) => {
    setEditingSessionId(session.id);
    setEditingTitle(session.title);
  }, []);

  const saveRename = useCallback(async () => {
    if (!editingSessionId || renamingSessionId) {
      return;
    }

    const sessionId = editingSessionId;
    const normalizedTitle = normalizeSessionTitle(editingTitle);
    const session = sessions.find((candidate) => candidate.id === sessionId);
    const knowledgeBaseId =
      session?.knowledgeBaseId || selectedKnowledgeBaseId;

    setRenamingSessionId(sessionId);
    setSessionErrors((previous) => ({
      ...previous,
      [sessionId]: "",
    }));

    try {
      await chatApi.renameConversation(
        knowledgeBaseId,
        sessionId,
        normalizedTitle,
      );
      setSessions((previous) =>
        renameSession(previous, sessionId, normalizedTitle),
      );
      setEditingSessionId("");
      setEditingTitle("");
    } catch (error) {
      setSessionErrors((previous) => ({
        ...previous,
        [sessionId]: getConversationActionError(
          error,
          "重命名失败，请稍后再试。",
        ),
      }));
    } finally {
      setRenamingSessionId("");
    }
  }, [
    editingSessionId,
    editingTitle,
    renamingSessionId,
    selectedKnowledgeBaseId,
    sessions,
    setSessionErrors,
    setSessions,
  ]);

  const cancelRename = useCallback(() => {
    setEditingSessionId("");
    setEditingTitle("");
  }, []);

  return {
    cancelRename,
    createSelectedSession,
    createSession,
    deleteSession,
    deletingSessionId,
    editingSessionId,
    editingTitle,
    isCreatingSession,
    renamingSessionId,
    saveRename,
    selectSession,
    setEditingTitle,
    startRename,
  };
}
