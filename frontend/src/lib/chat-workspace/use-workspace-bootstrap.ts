"use client";

import {
  type Dispatch,
  type SetStateAction,
  useEffect,
  useState,
} from "react";
import {
  AUTH_STORAGE_KEY,
  getAuthUsername,
  parseAuthState,
} from "../auth";
import { redirectToLogin } from "../frontend-api";
import * as chatApi from "./api";
import type {
  ChatSession,
  KnowledgeBase,
} from "./types";

type UseWorkspaceBootstrapOptions = {
  selectedKnowledgeBaseId: string;
  sessions: ChatSession[];
  setActiveSessionId: Dispatch<SetStateAction<string>>;
  setKnowledgeBases: Dispatch<SetStateAction<KnowledgeBase[]>>;
  setPageError: Dispatch<SetStateAction<string>>;
  setSelectedKnowledgeBaseId: Dispatch<SetStateAction<string>>;
  setSessions: Dispatch<SetStateAction<ChatSession[]>>;
};

type WorkspaceAuthStatus = {
  currentUsername: string;
  hasCheckedAuth: boolean;
};

/**
 * 解析工作区需要的本地认证信息；无效登录态返回 null。
 */
export function getWorkspaceAuthUsername(rawAuthState: string | null) {
  const authState = parseAuthState(rawAuthState);
  return authState ? getAuthUsername(authState) : null;
}

/**
 * 初次加载后优先选择默认知识库，其次选择首个知识库。
 */
export function chooseInitialKnowledgeBaseId(
  knowledgeBases: KnowledgeBase[],
) {
  return (
    knowledgeBases.find((knowledgeBase) => knowledgeBase.isDefault)?.id ||
    knowledgeBases[0]?.id ||
    ""
  );
}

/**
 * 保留目标知识库中仍可见的当前会话，否则回退首个可见会话。
 */
export function chooseVisibleSessionId(
  sessions: ChatSession[],
  knowledgeBaseId: string,
  currentSessionId: string,
) {
  const visibleSessions = sessions.filter(
    (session) => session.knowledgeBaseId === knowledgeBaseId,
  );

  return visibleSessions.some(
    (session) => session.id === currentSessionId,
  )
    ? currentSessionId
    : visibleSessions[0]?.id || "";
}

/**
 * 将未知异常转换为工作区初始化使用的用户可见错误。
 */
export function getWorkspaceBootstrapError(error: unknown) {
  return error instanceof Error
    ? error.message
    : "读取知识库列表失败，请稍后再试。";
}

/**
 * 管理认证检查、用户名、初始知识库/会话恢复和选择回退。
 *
 * knowledgeBases、sessions 和当前 ID 继续由页面持有，hook 只通过稳定
 * React setter 完成初始化与同步。
 */
export function useWorkspaceBootstrap({
  selectedKnowledgeBaseId,
  sessions,
  setActiveSessionId,
  setKnowledgeBases,
  setPageError,
  setSelectedKnowledgeBaseId,
  setSessions,
}: UseWorkspaceBootstrapOptions) {
  const [authStatus, setAuthStatus] = useState<WorkspaceAuthStatus>({
    currentUsername: "",
    hasCheckedAuth: false,
  });

  useEffect(() => {
    try {
      const currentUsername = getWorkspaceAuthUsername(
        localStorage.getItem(AUTH_STORAGE_KEY),
      );

      if (currentUsername === null) {
        redirectToLogin();
        return;
      }

      // eslint-disable-next-line react-hooks/set-state-in-effect -- 登录态只能在客户端挂载后读取。
      setAuthStatus({
        currentUsername,
        hasCheckedAuth: true,
      });
    } catch (error) {
      console.error("Failed to read auth state:", error);
      redirectToLogin();
    }
  }, []);

  useEffect(() => {
    if (!authStatus.hasCheckedAuth) {
      return;
    }

    let isCancelled = false;

    void chatApi
      .listKnowledgeBasesAndSessions()
      .then(
        ({
          knowledgeBases: nextKnowledgeBases,
          sessions: nextSessions,
        }) => {
          if (isCancelled) {
            return;
          }

          const initialKnowledgeBaseId =
            chooseInitialKnowledgeBaseId(nextKnowledgeBases);

          setKnowledgeBases(nextKnowledgeBases);
          setSessions(nextSessions);
          setSelectedKnowledgeBaseId(initialKnowledgeBaseId);
          setActiveSessionId(
            chooseVisibleSessionId(
              nextSessions,
              initialKnowledgeBaseId,
              "",
            ),
          );
          setPageError("");
        },
      )
      .catch((error) => {
        console.error("Failed to load knowledge bases:", error);

        if (!isCancelled) {
          setPageError(getWorkspaceBootstrapError(error));
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [
    authStatus.hasCheckedAuth,
    setActiveSessionId,
    setKnowledgeBases,
    setPageError,
    setSelectedKnowledgeBaseId,
    setSessions,
  ]);

  useEffect(() => {
    setActiveSessionId((currentSessionId) =>
      chooseVisibleSessionId(
        sessions,
        selectedKnowledgeBaseId,
        currentSessionId,
      ),
    );
  }, [
    selectedKnowledgeBaseId,
    sessions,
    setActiveSessionId,
  ]);

  return authStatus;
}
