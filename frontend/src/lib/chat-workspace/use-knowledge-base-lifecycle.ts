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

type UseKnowledgeBaseLifecycleOptions = {
  hasCheckedAuth: boolean;
  selectedKnowledgeBaseId: string;
  sessions: ChatSession[];
  setActiveSessionId: Dispatch<SetStateAction<string>>;
  setKnowledgeBases: Dispatch<SetStateAction<KnowledgeBase[]>>;
  setPageError: Dispatch<SetStateAction<string>>;
  setSelectedKnowledgeBaseId: Dispatch<SetStateAction<string>>;
  setSessions: Dispatch<SetStateAction<ChatSession[]>>;
};

/**
 * 将未知异常转换为知识库生命周期使用的用户可见错误。
 */
export function getKnowledgeBaseLifecycleError(
  error: unknown,
  fallbackMessage: string,
) {
  return error instanceof Error ? error.message : fallbackMessage;
}

/**
 * 统一知识库创建和重命名的名称清理规则。
 */
export function normalizeKnowledgeBaseName(name: string) {
  return name.trim();
}

/**
 * 将新建知识库追加到列表，并移除可能存在的同 ID 旧记录。
 */
export function upsertKnowledgeBase(
  knowledgeBases: KnowledgeBase[],
  nextKnowledgeBase: KnowledgeBase,
) {
  return [
    ...knowledgeBases.filter(
      (knowledgeBase) => knowledgeBase.id !== nextKnowledgeBase.id,
    ),
    nextKnowledgeBase,
  ];
}

/**
 * 将重命名结果写回目标知识库。
 */
export function renameKnowledgeBaseInList(
  knowledgeBases: KnowledgeBase[],
  renamedKnowledgeBase: KnowledgeBase,
) {
  return knowledgeBases.map((knowledgeBase) =>
    knowledgeBase.id === renamedKnowledgeBase.id
      ? { ...knowledgeBase, name: renamedKnowledgeBase.name }
      : knowledgeBase,
  );
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
 * 管理知识库弹窗、回收站以及创建、重命名、删除和恢复流程。
 *
 * 知识库、会话和当前选择仍由页面持有；retrieval settings 保持独立。
 */
export function useKnowledgeBaseLifecycle({
  hasCheckedAuth,
  selectedKnowledgeBaseId,
  sessions,
  setActiveSessionId,
  setKnowledgeBases,
  setPageError,
  setSelectedKnowledgeBaseId,
  setSessions,
}: UseKnowledgeBaseLifecycleOptions) {
  const [isKnowledgeBaseManagerOpen, setIsKnowledgeBaseManagerOpen] =
    useState(false);
  const [newKnowledgeBaseName, setNewKnowledgeBaseName] = useState("");
  const [isCreatingKnowledgeBase, setIsCreatingKnowledgeBase] =
    useState(false);
  const [deletedKnowledgeBases, setDeletedKnowledgeBases] = useState<
    DeletedKnowledgeBase[]
  >([]);
  const [isLoadingDeletedKnowledgeBases, setIsLoadingDeletedKnowledgeBases] =
    useState(false);
  const [knowledgeBaseLifecycleError, setKnowledgeBaseLifecycleError] =
    useState("");
  const [knowledgeBaseLifecycleMessage, setKnowledgeBaseLifecycleMessage] =
    useState("");
  const [editingKnowledgeBaseId, setEditingKnowledgeBaseId] = useState("");
  const [editingKnowledgeBaseName, setEditingKnowledgeBaseName] = useState("");
  const [renamingKnowledgeBaseId, setRenamingKnowledgeBaseId] = useState("");
  const [deletingKnowledgeBaseId, setDeletingKnowledgeBaseId] = useState("");
  const [restoringKnowledgeBaseId, setRestoringKnowledgeBaseId] = useState("");

  useEffect(() => {
    if (!hasCheckedAuth || !isKnowledgeBaseManagerOpen) {
      return;
    }

    let isCancelled = false;
    setIsLoadingDeletedKnowledgeBases(true);
    setKnowledgeBaseLifecycleError("");

    void chatApi
      .listDeletedKnowledgeBases()
      .then((knowledgeBases) => {
        if (!isCancelled) {
          setDeletedKnowledgeBases(knowledgeBases);
        }
      })
      .catch((error) => {
        if (!isCancelled) {
          setKnowledgeBaseLifecycleError(
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
  }, [hasCheckedAuth, isKnowledgeBaseManagerOpen]);

  const openKnowledgeBaseManager = useCallback(() => {
    setIsKnowledgeBaseManagerOpen(true);
  }, []);

  const closeKnowledgeBaseManager = useCallback(() => {
    setIsKnowledgeBaseManagerOpen(false);
  }, []);

  const createKnowledgeBase = useCallback(async () => {
    const normalizedName = normalizeKnowledgeBaseName(newKnowledgeBaseName);

    if (!normalizedName || isCreatingKnowledgeBase) {
      return;
    }

    setIsCreatingKnowledgeBase(true);
    setPageError("");

    try {
      const knowledgeBase = await chatApi.createKnowledgeBase(normalizedName);
      setKnowledgeBases((previous) =>
        upsertKnowledgeBase(previous, knowledgeBase),
      );
      setSelectedKnowledgeBaseId(knowledgeBase.id);
      setNewKnowledgeBaseName("");
    } catch (error) {
      setPageError(
        getKnowledgeBaseLifecycleError(
          error,
          "创建知识库失败，请稍后再试。",
        ),
      );
    } finally {
      setIsCreatingKnowledgeBase(false);
    }
  }, [
    isCreatingKnowledgeBase,
    newKnowledgeBaseName,
    setKnowledgeBases,
    setPageError,
    setSelectedKnowledgeBaseId,
  ]);

  const refreshKnowledgeBaseCollections = useCallback(
    async (preferredKnowledgeBaseId?: string) => {
      const [
        {
          knowledgeBases: nextKnowledgeBases,
          sessions: nextSessions,
        },
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

  const startKnowledgeBaseRename = useCallback(
    (knowledgeBase: KnowledgeBase) => {
      setEditingKnowledgeBaseId(knowledgeBase.id);
      setEditingKnowledgeBaseName(knowledgeBase.name);
      setKnowledgeBaseLifecycleError("");
      setKnowledgeBaseLifecycleMessage("");
    },
    [],
  );

  const cancelKnowledgeBaseRename = useCallback(() => {
    setEditingKnowledgeBaseId("");
    setEditingKnowledgeBaseName("");
  }, []);

  const saveKnowledgeBaseRename = useCallback(async () => {
    const normalizedName = normalizeKnowledgeBaseName(
      editingKnowledgeBaseName,
    );
    if (!editingKnowledgeBaseId || !normalizedName || renamingKnowledgeBaseId) {
      return;
    }

    const knowledgeBaseId = editingKnowledgeBaseId;
    setRenamingKnowledgeBaseId(knowledgeBaseId);
    setKnowledgeBaseLifecycleError("");
    setKnowledgeBaseLifecycleMessage("");

    try {
      const renamedKnowledgeBase = await chatApi.renameKnowledgeBase(
        knowledgeBaseId,
        normalizedName,
      );
      setKnowledgeBases((previous) =>
        renameKnowledgeBaseInList(previous, renamedKnowledgeBase),
      );
      setEditingKnowledgeBaseId("");
      setEditingKnowledgeBaseName("");
      setKnowledgeBaseLifecycleMessage("知识库名称已更新。");
    } catch (error) {
      setKnowledgeBaseLifecycleError(
        getKnowledgeBaseLifecycleError(
          error,
          "重命名知识库失败，请稍后再试。",
        ),
      );
    } finally {
      setRenamingKnowledgeBaseId("");
    }
  }, [
    editingKnowledgeBaseId,
    editingKnowledgeBaseName,
    renamingKnowledgeBaseId,
    setKnowledgeBases,
  ]);

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
      setKnowledgeBaseLifecycleError("");
      setKnowledgeBaseLifecycleMessage("");

      try {
        await chatApi.deleteKnowledgeBase(knowledgeBase.id);
        await refreshKnowledgeBaseCollections();
        setEditingKnowledgeBaseId("");
        setEditingKnowledgeBaseName("");
        setKnowledgeBaseLifecycleMessage(
          "知识库已移入回收站，文件仍保留。",
        );
      } catch (error) {
        setKnowledgeBaseLifecycleError(
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
      deletingKnowledgeBaseId,
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
      setKnowledgeBaseLifecycleError("");
      setKnowledgeBaseLifecycleMessage("");

      try {
        await chatApi.restoreKnowledgeBase(knowledgeBaseId);
        await refreshKnowledgeBaseCollections(knowledgeBaseId);
        setKnowledgeBaseLifecycleMessage("知识库及其原会话已恢复。");
      } catch (error) {
        setKnowledgeBaseLifecycleError(
          getKnowledgeBaseLifecycleError(
            error,
            "恢复知识库失败，请稍后再试。",
          ),
        );
      } finally {
        setRestoringKnowledgeBaseId("");
      }
    },
    [refreshKnowledgeBaseCollections, restoringKnowledgeBaseId],
  );

  return {
    cancelKnowledgeBaseRename,
    closeKnowledgeBaseManager,
    createKnowledgeBase,
    deleteKnowledgeBase,
    deletedKnowledgeBases,
    deletingKnowledgeBaseId,
    editingKnowledgeBaseId,
    editingKnowledgeBaseName,
    isCreatingKnowledgeBase,
    isKnowledgeBaseManagerOpen,
    isLoadingDeletedKnowledgeBases,
    knowledgeBaseLifecycleError,
    knowledgeBaseLifecycleMessage,
    newKnowledgeBaseName,
    openKnowledgeBaseManager,
    renamingKnowledgeBaseId,
    restoreKnowledgeBase,
    restoringKnowledgeBaseId,
    saveKnowledgeBaseRename,
    setEditingKnowledgeBaseName,
    setNewKnowledgeBaseName,
    startKnowledgeBaseRename,
  };
}
