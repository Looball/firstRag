"use client";

import { type Dispatch, type SetStateAction, useCallback, useState } from "react";
import * as chatApi from "./api";
import type { ChatSession, KnowledgeBase } from "./types";
import {
  getKnowledgeBaseLifecycleError,
  useKnowledgeBaseTrashActions,
} from "./use-knowledge-base-trash-actions";

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
 * 管理知识库弹窗、创建和重命名，并组合独立的回收站操作 hook。
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
  const [knowledgeBaseLifecycleError, setKnowledgeBaseLifecycleError] =
    useState("");
  const [knowledgeBaseLifecycleMessage, setKnowledgeBaseLifecycleMessage] =
    useState("");
  const [editingKnowledgeBaseId, setEditingKnowledgeBaseId] = useState("");
  const [editingKnowledgeBaseName, setEditingKnowledgeBaseName] = useState("");
  const [renamingKnowledgeBaseId, setRenamingKnowledgeBaseId] = useState("");

  const clearKnowledgeBaseLifecycleStatus = useCallback(() => {
    setKnowledgeBaseLifecycleError("");
    setKnowledgeBaseLifecycleMessage("");
  }, []);

  const resetKnowledgeBaseEditing = useCallback(() => {
    setEditingKnowledgeBaseId("");
    setEditingKnowledgeBaseName("");
  }, []);

  const {
    clearKnowledgeBaseTrashStatus,
    deleteKnowledgeBase,
    deletedKnowledgeBases,
    deletingKnowledgeBaseId,
    isLoadingDeletedKnowledgeBases,
    knowledgeBaseTrashError,
    knowledgeBaseTrashMessage,
    restoreKnowledgeBase,
    restoringKnowledgeBaseId,
  } = useKnowledgeBaseTrashActions({
    hasCheckedAuth,
    isKnowledgeBaseManagerOpen,
    selectedKnowledgeBaseId,
    sessions,
    onKnowledgeBaseDeleted: resetKnowledgeBaseEditing,
    onTrashActionStart: clearKnowledgeBaseLifecycleStatus,
    setActiveSessionId,
    setKnowledgeBases,
    setSelectedKnowledgeBaseId,
    setSessions,
  });

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

  const startKnowledgeBaseRename = useCallback(
    (knowledgeBase: KnowledgeBase) => {
      setEditingKnowledgeBaseId(knowledgeBase.id);
      setEditingKnowledgeBaseName(knowledgeBase.name);
      clearKnowledgeBaseLifecycleStatus();
      clearKnowledgeBaseTrashStatus();
    },
    [clearKnowledgeBaseLifecycleStatus, clearKnowledgeBaseTrashStatus],
  );

  const cancelKnowledgeBaseRename = useCallback(() => {
    resetKnowledgeBaseEditing();
  }, [resetKnowledgeBaseEditing]);

  const saveKnowledgeBaseRename = useCallback(async () => {
    const normalizedName = normalizeKnowledgeBaseName(
      editingKnowledgeBaseName,
    );
    if (!editingKnowledgeBaseId || !normalizedName || renamingKnowledgeBaseId) {
      return;
    }

    const knowledgeBaseId = editingKnowledgeBaseId;
    setRenamingKnowledgeBaseId(knowledgeBaseId);
    clearKnowledgeBaseLifecycleStatus();
    clearKnowledgeBaseTrashStatus();

    try {
      const renamedKnowledgeBase = await chatApi.renameKnowledgeBase(
        knowledgeBaseId,
        normalizedName,
      );
      setKnowledgeBases((previous) =>
        renameKnowledgeBaseInList(previous, renamedKnowledgeBase),
      );
      resetKnowledgeBaseEditing();
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
    clearKnowledgeBaseLifecycleStatus,
    clearKnowledgeBaseTrashStatus,
    editingKnowledgeBaseId,
    editingKnowledgeBaseName,
    renamingKnowledgeBaseId,
    resetKnowledgeBaseEditing,
    setKnowledgeBases,
  ]);

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
    knowledgeBaseLifecycleError:
      knowledgeBaseLifecycleError || knowledgeBaseTrashError,
    knowledgeBaseLifecycleMessage:
      knowledgeBaseLifecycleMessage || knowledgeBaseTrashMessage,
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
