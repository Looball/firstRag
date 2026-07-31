"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  DEFAULT_KNOWLEDGE_BASE_ID,
  DEFAULT_RETRIEVAL_SETTINGS,
} from "./constants";
import * as chatApi from "./api";
import type { KnowledgeBaseRetrievalSettings } from "./types";

type RetrievalSettingsCache = Record<
  string,
  KnowledgeBaseRetrievalSettings
>;

type UseKnowledgeBaseRetrievalSettingsOptions = {
  hasCheckedAuth: boolean;
  isAdvancedMode: boolean;
  isKnowledgeBaseManagerOpen: boolean;
  selectedKnowledgeBaseId: string;
};

/**
 * 判断当前知识库是否允许加载 retrieval settings。
 */
export function shouldLoadKnowledgeBaseRetrievalSettings({
  hasCheckedAuth,
  isAdvancedMode,
  isKnowledgeBaseManagerOpen,
  knowledgeBaseId,
}: {
  hasCheckedAuth: boolean;
  isAdvancedMode: boolean;
  isKnowledgeBaseManagerOpen: boolean;
  knowledgeBaseId: string;
}) {
  return (
    hasCheckedAuth &&
    isAdvancedMode &&
    isKnowledgeBaseManagerOpen &&
    Boolean(knowledgeBaseId) &&
    knowledgeBaseId !== DEFAULT_KNOWLEDGE_BASE_ID
  );
}

/**
 * 读取目标知识库缓存；未加载时返回一份默认设置。
 */
export function getCachedRetrievalSettings(
  cache: RetrievalSettingsCache,
  knowledgeBaseId: string,
) {
  return cache[knowledgeBaseId] || { ...DEFAULT_RETRIEVAL_SETTINGS };
}

/**
 * 将完整 retrieval settings 写入目标知识库缓存。
 */
export function cacheRetrievalSettings(
  cache: RetrievalSettingsCache,
  knowledgeBaseId: string,
  settings: KnowledgeBaseRetrievalSettings,
) {
  return {
    ...cache,
    [knowledgeBaseId]: settings,
  };
}

/**
 * 将局部编辑合并到目标知识库的 retrieval settings。
 */
export function updateCachedRetrievalSettings(
  cache: RetrievalSettingsCache,
  knowledgeBaseId: string,
  patch: Partial<KnowledgeBaseRetrievalSettings>,
) {
  return cacheRetrievalSettings(cache, knowledgeBaseId, {
    ...getCachedRetrievalSettings(cache, knowledgeBaseId),
    ...patch,
  });
}

/**
 * 将未知异常转换为 retrieval settings 使用的用户可见错误。
 */
export function getRetrievalSettingsError(
  error: unknown,
  fallbackMessage: string,
) {
  return error instanceof Error ? error.message : fallbackMessage;
}

/**
 * 管理知识库 retrieval settings 的缓存、加载、编辑、保存和提示状态。
 */
export function useKnowledgeBaseRetrievalSettings({
  hasCheckedAuth,
  isAdvancedMode,
  isKnowledgeBaseManagerOpen,
  selectedKnowledgeBaseId,
}: UseKnowledgeBaseRetrievalSettingsOptions) {
  const [retrievalSettingsByKnowledgeBaseId, setRetrievalSettingsCache] =
    useState<RetrievalSettingsCache>({});
  const [isLoadingRetrievalSettings, setIsLoadingRetrievalSettings] =
    useState(false);
  const [isSavingRetrievalSettings, setIsSavingRetrievalSettings] =
    useState(false);
  const [retrievalSettingsMessage, setRetrievalSettingsMessage] =
    useState("");
  const [retrievalSettingsError, setRetrievalSettingsError] = useState("");
  const loadRequestIdRef = useRef(0);

  const selectedRetrievalSettings = getCachedRetrievalSettings(
    retrievalSettingsByKnowledgeBaseId,
    selectedKnowledgeBaseId,
  );

  const updateSelectedRetrievalSettings = useCallback(
    (patch: Partial<KnowledgeBaseRetrievalSettings>) => {
      if (!selectedKnowledgeBaseId) {
        return;
      }

      setRetrievalSettingsCache((previous) =>
        updateCachedRetrievalSettings(
          previous,
          selectedKnowledgeBaseId,
          patch,
        ),
      );
      setRetrievalSettingsMessage("");
      setRetrievalSettingsError("");
    },
    [selectedKnowledgeBaseId],
  );

  const loadRetrievalSettings = useCallback(
    async (knowledgeBaseId: string) => {
      const requestId = loadRequestIdRef.current + 1;
      loadRequestIdRef.current = requestId;
      setIsLoadingRetrievalSettings(true);
      setRetrievalSettingsError("");

      try {
        const settings = await chatApi.getRetrievalSettings(knowledgeBaseId);

        if (requestId === loadRequestIdRef.current) {
          setRetrievalSettingsCache((previous) =>
            cacheRetrievalSettings(previous, knowledgeBaseId, settings),
          );
        }
      } catch (error) {
        if (requestId === loadRequestIdRef.current) {
          setRetrievalSettingsError(
            getRetrievalSettingsError(
              error,
              "读取检索设置失败，请稍后再试。",
            ),
          );
        }
      } finally {
        if (requestId === loadRequestIdRef.current) {
          setIsLoadingRetrievalSettings(false);
        }
      }
    },
    [],
  );

  useEffect(() => {
    const shouldLoad = shouldLoadKnowledgeBaseRetrievalSettings({
      hasCheckedAuth,
      isAdvancedMode,
      isKnowledgeBaseManagerOpen,
      knowledgeBaseId: selectedKnowledgeBaseId,
    });

    if (!shouldLoad) {
      loadRequestIdRef.current += 1;
      setIsLoadingRetrievalSettings(false);
      return;
    }

    void loadRetrievalSettings(selectedKnowledgeBaseId);
  }, [
    hasCheckedAuth,
    isAdvancedMode,
    isKnowledgeBaseManagerOpen,
    loadRetrievalSettings,
    selectedKnowledgeBaseId,
  ]);

  const saveSelectedRetrievalSettings = useCallback(async () => {
    if (
      !selectedKnowledgeBaseId ||
      selectedKnowledgeBaseId === DEFAULT_KNOWLEDGE_BASE_ID ||
      isSavingRetrievalSettings
    ) {
      return;
    }

    const knowledgeBaseId = selectedKnowledgeBaseId;
    const settingsToSave = selectedRetrievalSettings;
    setIsSavingRetrievalSettings(true);
    setRetrievalSettingsMessage("");
    setRetrievalSettingsError("");

    try {
      const settings = await chatApi.saveRetrievalSettings(
        knowledgeBaseId,
        settingsToSave,
      );

      setRetrievalSettingsCache((previous) =>
        cacheRetrievalSettings(previous, knowledgeBaseId, settings),
      );
      setRetrievalSettingsMessage("检索设置已保存，下一次提问生效。");
    } catch (error) {
      setRetrievalSettingsError(
        getRetrievalSettingsError(
          error,
          "保存检索设置失败，请稍后再试。",
        ),
      );
    } finally {
      setIsSavingRetrievalSettings(false);
    }
  }, [
    isSavingRetrievalSettings,
    selectedKnowledgeBaseId,
    selectedRetrievalSettings,
  ]);

  return {
    isLoadingRetrievalSettings,
    isSavingRetrievalSettings,
    retrievalSettingsError,
    retrievalSettingsMessage,
    saveSelectedRetrievalSettings,
    selectedRetrievalSettings,
    updateSelectedRetrievalSettings,
  };
}
