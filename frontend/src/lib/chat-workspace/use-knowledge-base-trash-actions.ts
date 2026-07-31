"use client";

import {
  type Dispatch,
  type SetStateAction,
  useCallback,
  useEffect,
  useState,
} from "react";
import * as chatApi from "./api";
import type {
  ChatSession,
  DeletedKnowledgeBase,
  KnowledgeBase,
} from "./types";

type UseKnowledgeBaseTrashActionsOptions = {
  hasCheckedAuth: boolean;
  isKnowledgeBaseManagerOpen: boolean;
  selectedKnowledgeBaseId: string;
  sessions: ChatSession[];
  onKnowledgeBaseDeleted: () => void;
  onTrashActionStart: () => void;
  setActiveSessionId: Dispatch<SetStateAction<string>>;
  setKnowledgeBases: Dispatch<SetStateAction<KnowledgeBase[]>>;
  setSelectedKnowledgeBaseId: Dispatch<SetStateAction<string>>;
  setSessions: Dispatch<SetStateAction<ChatSession[]>>;
};

/**
 * 将未知异常转换为知识库操作使用的用户可见错误。
 */
export function getKnowledgeBaseLifecycleError(
  error: unknown,
  fallbackMessage: string,
) {
  return error instanceof Error ? error.message : fallbackMessage;
}

/**
 * 刷新后优先选择指定知识库，其次保留当前选择，最后回退默认项。
 */
export function chooseRefreshedKnowledgeBaseId(
  knowledgeBases: KnowledgeBase[],
  preferredKnowledgeBaseId: string | undefined,
  currentKnowledgeBaseId: string,
) {
  return (
    knowledgeBases.find(
      (knowledgeBase) => knowledgeBase.id === preferredKnowledgeBaseId,
    )?.id ||
    knowledgeBases.find(
      (knowledgeBase) => knowledgeBase.id === currentKnowledgeBaseId,
    )?.id ||
    knowledgeBases.find((knowledgeBase) => knowledgeBase.isDefault)?.id ||
    knowledgeBases[0]?.id ||
    ""
  );
}

/**
 * 刷新后保留仍属于目标知识库的当前会话，否则选择首个可见会话。
 */
export function chooseRefreshedSessionId(
  sessions: ChatSession[],
  knowledgeBaseId: string,
  currentSessionId: string,
) {
  return sessions.some(
    (session) =>
      session.id === currentSessionId &&
      session.knowledgeBaseId === knowledgeBaseId,
  )
    ? currentSessionId
    : sessions.find(
        (session) => session.knowledgeBaseId === knowledgeBaseId,
      )?.id || "";
}

/**
 * 生成包含受影响会话数量的知识库删除确认文案。
 */
export function buildKnowledgeBaseDeleteConfirmation(
  knowledgeBase: KnowledgeBase,
  sessions: ChatSession[],
) {
  const conversationCount = sessions.filter(
    (session) => session.knowledgeBaseId === knowledgeBase.id,
  ).length;

  return `确认删除知识库“${knowledgeBase.name}”吗？${conversationCount} 个会话会暂时隐藏，但文件仍保留在文件库中，可从回收站恢复。`;
}

/**
 * 管理知识库回收站加载、软删除、恢复和刷新后的选择回退。
 */
export function useKnowledgeBaseTrashActions({
  hasCheckedAuth,
  isKnowledgeBaseManagerOpen,
  selectedKnowledgeBaseId,
  sessions,
  onKnowledgeBaseDeleted,
  onTrashActionStart,
  setActiveSessionId,
  setKnowledgeBases,
  setSelectedKnowledgeBaseId,
  setSessions,
}: UseKnowledgeBaseTrashActionsOptions) {
  const [deletedKnowledgeBases, setDeletedKnowledgeBases] = useState<
    DeletedKnowledgeBase[]
  >([]);
  const [isLoadingDeletedKnowledgeBases, setIsLoadingDeletedKnowledgeBases] =
    useState(false);
  const [knowledgeBaseTrashError, setKnowledgeBaseTrashError] = useState("");
  const [knowledgeBaseTrashMessage, setKnowledgeBaseTrashMessage] =
    useState("");
  const [deletingKnowledgeBaseId, setDeletingKnowledgeBaseId] = useState("");
  const [restoringKnowledgeBaseId, setRestoringKnowledgeBaseId] = useState("");

  useEffect(() => {
    if (!hasCheckedAuth || !isKnowledgeBaseManagerOpen) {
      return;
    }

    let isCancelled = false;
    setIsLoadingDeletedKnowledgeBases(true);
    setKnowledgeBaseTrashError("");
    onTrashActionStart();

    void chatApi
      .listDeletedKnowledgeBases()
      .then((knowledgeBases) => {
        if (!isCancelled) {
          setDeletedKnowledgeBases(knowledgeBases);
        }
      })
      .catch((error) => {
        if (!isCancelled) {
          setKnowledgeBaseTrashError(
            getKnowledgeBaseLifecycleError(
              error,
              "读取知识库回收站失败，请稍后再试。",
            ),
          );
        }
      })
      .finally(() => {
        if (!isCancelled) {
          setIsLoadingDeletedKnowledgeBases(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [hasCheckedAuth, isKnowledgeBaseManagerOpen, onTrashActionStart]);

  const clearKnowledgeBaseTrashStatus = useCallback(() => {
    setKnowledgeBaseTrashError("");
    setKnowledgeBaseTrashMessage("");
  }, []);

  const refreshKnowledgeBaseCollections = useCallback(
    async (preferredKnowledgeBaseId?: string) => {
      const [
        { knowledgeBases: nextKnowledgeBases, sessions: nextSessions },
        nextDeletedKnowledgeBases,
      ] = await Promise.all([
        chatApi.listKnowledgeBasesAndSessions(),
        chatApi.listDeletedKnowledgeBases(),
      ]);
      const nextSelectedKnowledgeBaseId = chooseRefreshedKnowledgeBaseId(
        nextKnowledgeBases,
        preferredKnowledgeBaseId,
        selectedKnowledgeBaseId,
      );

      setKnowledgeBases(nextKnowledgeBases);
      setSessions(nextSessions);
      setSelectedKnowledgeBaseId(nextSelectedKnowledgeBaseId);
      setActiveSessionId((previousSessionId) =>
        chooseRefreshedSessionId(
          nextSessions,
          nextSelectedKnowledgeBaseId,
          previousSessionId,
        ),
      );
      setDeletedKnowledgeBases(nextDeletedKnowledgeBases);
    },
    [
      selectedKnowledgeBaseId,
      setActiveSessionId,
      setKnowledgeBases,
      setSelectedKnowledgeBaseId,
      setSessions,
    ],
  );

  const deleteKnowledgeBase = useCallback(
    async (knowledgeBase: KnowledgeBase) => {
      if (knowledgeBase.isDefault || deletingKnowledgeBaseId) {
        return;
      }
      if (
        !window.confirm(
          buildKnowledgeBaseDeleteConfirmation(knowledgeBase, sessions),
        )
      ) {
        return;
      }

      setDeletingKnowledgeBaseId(knowledgeBase.id);
      clearKnowledgeBaseTrashStatus();
      onTrashActionStart();

      try {
        await chatApi.deleteKnowledgeBase(knowledgeBase.id);
        await refreshKnowledgeBaseCollections();
        onKnowledgeBaseDeleted();
        setKnowledgeBaseTrashMessage("知识库已移入回收站，文件仍保留。");
      } catch (error) {
        setKnowledgeBaseTrashError(
          getKnowledgeBaseLifecycleError(
            error,
            "删除知识库失败，请稍后再试。",
          ),
        );
      } finally {
        setDeletingKnowledgeBaseId("");
      }
    },
    [
      clearKnowledgeBaseTrashStatus,
      deletingKnowledgeBaseId,
      onKnowledgeBaseDeleted,
      onTrashActionStart,
      refreshKnowledgeBaseCollections,
      sessions,
    ],
  );

  const restoreKnowledgeBase = useCallback(
    async (knowledgeBaseId: string) => {
      if (!knowledgeBaseId || restoringKnowledgeBaseId) {
        return;
      }

      setRestoringKnowledgeBaseId(knowledgeBaseId);
      clearKnowledgeBaseTrashStatus();
      onTrashActionStart();

      try {
        await chatApi.restoreKnowledgeBase(knowledgeBaseId);
        await refreshKnowledgeBaseCollections(knowledgeBaseId);
        setKnowledgeBaseTrashMessage("知识库及其原会话已恢复。");
      } catch (error) {
        setKnowledgeBaseTrashError(
          getKnowledgeBaseLifecycleError(
            error,
            "恢复知识库失败，请稍后再试。",
          ),
        );
      } finally {
        setRestoringKnowledgeBaseId("");
      }
    },
    [
      clearKnowledgeBaseTrashStatus,
      onTrashActionStart,
      refreshKnowledgeBaseCollections,
      restoringKnowledgeBaseId,
    ],
  );

  return {
    clearKnowledgeBaseTrashStatus,
    deleteKnowledgeBase,
    deletedKnowledgeBases,
    deletingKnowledgeBaseId,
    isLoadingDeletedKnowledgeBases,
    knowledgeBaseTrashError,
    knowledgeBaseTrashMessage,
    restoreKnowledgeBase,
    restoringKnowledgeBaseId,
  };
}
