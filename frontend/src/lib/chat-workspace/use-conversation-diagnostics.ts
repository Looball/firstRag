"use client";

import { useCallback, useEffect, useState } from "react";
import * as chatApi from "./api";
import type { MessageDiagnostic } from "./types";

type LoadConversationDiagnosticsOptions = {
  silent?: boolean;
};

type UseConversationDiagnosticsOptions = {
  isAdvancedMode: boolean;
};

/**
 * 为会话中的单条消息生成唯一 diagnostics 面板键。
 */
export function buildDiagnosticPanelKey(
  conversationId: string,
  messageKey: string,
) {
  return `${conversationId}:${messageKey}`;
}

/**
 * 从会话级 diagnostics 缓存中查找目标持久化消息的诊断信息。
 */
export function findMessageDiagnostic(
  diagnostics: MessageDiagnostic[] | undefined,
  messageId?: string,
) {
  if (!messageId) {
    return null;
  }

  return (
    diagnostics?.find((diagnostic) => diagnostic.messageId === messageId) ??
    null
  );
}

/**
 * 判断展开动作是否需要触发首次 diagnostics 请求。
 */
export function shouldLoadConversationDiagnostics(
  shouldOpen: boolean,
  diagnostics: MessageDiagnostic[] | undefined,
  isLoading: boolean,
) {
  return shouldOpen && diagnostics === undefined && !isLoading;
}

/**
 * 管理会话 diagnostics 的缓存、加载、错误和消息面板展开状态。
 */
export function useConversationDiagnostics({
  isAdvancedMode,
}: UseConversationDiagnosticsOptions) {
  const [conversationDiagnostics, setConversationDiagnostics] = useState<
    Record<string, MessageDiagnostic[]>
  >({});
  const [expandedDiagnosticPanels, setExpandedDiagnosticPanels] = useState<
    Record<string, boolean>
  >({});
  const [loadingDiagnostics, setLoadingDiagnostics] = useState<
    Record<string, boolean>
  >({});
  const [diagnosticErrors, setDiagnosticErrors] = useState<
    Record<string, string>
  >({});

  useEffect(() => {
    if (!isAdvancedMode) {
      setExpandedDiagnosticPanels({});
    }
  }, [isAdvancedMode]);

  const loadDiagnostics = useCallback(
    async (
      conversationId: string,
      options: LoadConversationDiagnosticsOptions = {},
    ) => {
      if (!options.silent) {
        setLoadingDiagnostics((previous) => ({
          ...previous,
          [conversationId]: true,
        }));
        setDiagnosticErrors((previous) => ({
          ...previous,
          [conversationId]: "",
        }));
      }

      try {
        const diagnostics =
          await chatApi.loadConversationDiagnostics(conversationId);

        setConversationDiagnostics((previous) => ({
          ...previous,
          [conversationId]: diagnostics,
        }));
      } catch (error) {
        if (!options.silent) {
          setDiagnosticErrors((previous) => ({
            ...previous,
            [conversationId]:
              error instanceof Error
                ? error.message
                : "加载诊断信息失败，请稍后再试。",
          }));
        }
      } finally {
        if (!options.silent) {
          setLoadingDiagnostics((previous) => ({
            ...previous,
            [conversationId]: false,
          }));
        }
      }
    },
    [],
  );

  const toggleDiagnostics = useCallback(
    (conversationId: string, messageKey: string) => {
      if (!isAdvancedMode) {
        return;
      }

      const panelKey = buildDiagnosticPanelKey(conversationId, messageKey);
      const shouldOpen = !expandedDiagnosticPanels[panelKey];

      setExpandedDiagnosticPanels((previous) => ({
        ...previous,
        [panelKey]: shouldOpen,
      }));

      if (
        shouldLoadConversationDiagnostics(
          shouldOpen,
          conversationDiagnostics[conversationId],
          Boolean(loadingDiagnostics[conversationId]),
        )
      ) {
        void loadDiagnostics(conversationId);
      }
    },
    [
      conversationDiagnostics,
      expandedDiagnosticPanels,
      isAdvancedMode,
      loadDiagnostics,
      loadingDiagnostics,
    ],
  );

  const getDiagnosticState = useCallback(
    (conversationId: string, messageKey: string, messageId?: string) => {
      const diagnostics = conversationDiagnostics[conversationId];
      const panelKey = buildDiagnosticPanelKey(conversationId, messageKey);

      return {
        isExpanded: Boolean(expandedDiagnosticPanels[panelKey]),
        diagnostic: findMessageDiagnostic(diagnostics, messageId),
        isLoading: Boolean(loadingDiagnostics[conversationId]),
        hasLoaded: diagnostics !== undefined,
        errorMessage: diagnosticErrors[conversationId] || "",
      };
    },
    [
      conversationDiagnostics,
      diagnosticErrors,
      expandedDiagnosticPanels,
      loadingDiagnostics,
    ],
  );

  return {
    getDiagnosticState,
    loadDiagnostics,
    toggleDiagnostics,
  };
}
