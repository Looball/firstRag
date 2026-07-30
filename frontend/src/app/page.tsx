"use client";

import dynamic from "next/dynamic";
import { ChatComposer } from "@/components/chat-workspace/ChatComposer";
import { ChatWorkspaceHeader } from "@/components/chat-workspace/ChatWorkspaceHeader";
import { ConversationMessageItem } from "@/components/chat-workspace/ConversationMessageItem";
import { ConversationSidebar } from "@/components/chat-workspace/ConversationSidebar";
import { FileManagerDialog } from "@/components/chat-workspace/FileManagerDialog";
import { KnowledgeBaseManagerDialog } from "@/components/chat-workspace/KnowledgeBaseManagerDialog";
import { KnowledgeBaseSidebarControls } from "@/components/chat-workspace/KnowledgeBaseSidebarControls";
import { QualityDashboardPanel } from "@/components/chat-workspace/QualityDashboardPanel";
import { SidebarAccountModeControls } from "@/components/chat-workspace/SidebarAccountModeControls";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  AUTH_STORAGE_KEY,
  getAuthUsername,
  parseAuthState,
} from "@/lib/auth";
import { redirectToLogin } from "@/lib/frontend-api";
import {
  DEFAULT_KNOWLEDGE_BASE_ID,
  DEFAULT_RETRIEVAL_SETTINGS,
} from "@/lib/chat-workspace/constants";
import {
  getAdvancedModeDefault,
  readAdvancedModePreference,
  writeAdvancedModePreference,
} from "@/lib/chat-workspace/advanced-mode";
import * as chatApi from "@/lib/chat-workspace/api";
import { useConversationActions } from "@/lib/chat-workspace/use-conversation-actions";
import { useConversationDiagnostics } from "@/lib/chat-workspace/use-conversation-diagnostics";
import { useKnowledgeFiles } from "@/lib/chat-workspace/use-knowledge-files";
import { useMessageClipboard } from "@/lib/chat-workspace/use-message-clipboard";
import { useMessageQualityActions } from "@/lib/chat-workspace/use-message-quality-actions";
import { usePendingChatImages } from "@/lib/chat-workspace/use-pending-chat-images";
import { useQualityDashboard } from "@/lib/chat-workspace/use-quality-dashboard";
import { buildSessionTitle } from "@/lib/chat-workspace/utils";
import { streamChatResponse } from "@/lib/chat-workspace/chat-stream";
import { useRetryAfterCountdown } from "@/lib/use-retry-after-countdown";
import type {
  ChatSession,
  ChatSource,
  DeletedKnowledgeBase,
  KnowledgeBase,
  KnowledgeBaseRetrievalSettings,
  Message,
  MessageAttachment,
  RetrievalState,
} from "@/lib/chat-workspace/types";

const SourcePreviewDialog = dynamic(
  () =>
    import("@/components/chat-workspace/SourcePreviewDialog").then(
      (module) => module.SourcePreviewDialog,
    ),
  { ssr: false },
);

export default function Home() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState("");
  const [input, setInput] = useState("");
  const [isUploadingChatImages, setIsUploadingChatImages] = useState(false);
  const chatRateLimit = useRetryAfterCountdown();
  const chatImageRateLimit = useRetryAfterCountdown();
  const [isAdvancedMode, setIsAdvancedMode] = useState(getAdvancedModeDefault);
  const [loadingSessions, setLoadingSessions] = useState<Record<string, boolean>>(
    {}
  );
  const [sessionErrors, setSessionErrors] = useState<Record<string, string>>({});
  const [hasCheckedAuth, setHasCheckedAuth] = useState(false);
  const [isCreatingKnowledgeBase, setIsCreatingKnowledgeBase] =
    useState(false);
  const [pageError, setPageError] = useState("");
  const [currentUsername, setCurrentUsername] = useState("");
  const {
    chatImageInputRef,
    clearPendingChatImages,
    handlePasteChatImages,
    handleSelectChatImages,
    pendingChatImages,
    removePendingChatImage,
  } = usePendingChatImages({
    onError: setPageError,
  });
  const { copiedMessageKey, copyMessage } = useMessageClipboard();
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([
    {
      id: DEFAULT_KNOWLEDGE_BASE_ID,
      name: "默认知识库",
      isDefault: true,
      fileCount: 0,
    },
  ]);
  const [selectedKnowledgeBaseId, setSelectedKnowledgeBaseId] = useState(
    DEFAULT_KNOWLEDGE_BASE_ID
  );
  const clearComposerInput = useCallback(() => {
    setInput("");
  }, []);
  const {
    cancelRename: handleCancelRename,
    createSelectedSession: handleCreateSession,
    createSession,
    deleteSession: handleDeleteSession,
    deletingSessionId,
    editingSessionId,
    editingTitle,
    isCreatingSession,
    renamingSessionId,
    saveRename: handleSaveRename,
    selectSession: handleSelectSession,
    setEditingTitle,
    startRename: handleStartRename,
  } = useConversationActions({
    activeSessionId: currentSessionId,
    canCreateSession:
      Boolean(selectedKnowledgeBaseId) &&
      selectedKnowledgeBaseId !== DEFAULT_KNOWLEDGE_BASE_ID,
    onClearComposer: clearComposerInput,
    selectedKnowledgeBaseId,
    sessions,
    setActiveSessionId: setCurrentSessionId,
    setLoadingSessions,
    setPageError,
    setSessionErrors,
    setSessions,
  });
  const [
    retrievalSettingsByKnowledgeBaseId,
    setRetrievalSettingsByKnowledgeBaseId,
  ] = useState<Record<string, KnowledgeBaseRetrievalSettings>>({});
  const [isLoadingRetrievalSettings, setIsLoadingRetrievalSettings] =
    useState(false);
  const [isSavingRetrievalSettings, setIsSavingRetrievalSettings] =
    useState(false);
  const [retrievalSettingsMessage, setRetrievalSettingsMessage] =
    useState("");
  const [retrievalSettingsError, setRetrievalSettingsError] = useState("");
  const [isKnowledgeBaseManagerOpen, setIsKnowledgeBaseManagerOpen] =
    useState(false);
  const [newKnowledgeBaseName, setNewKnowledgeBaseName] = useState("");
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
  const [activeSourcePreview, setActiveSourcePreview] =
    useState<ChatSource | null>(null);
  const {
    getDiagnosticState,
    loadDiagnostics,
    toggleDiagnostics,
  } = useConversationDiagnostics({
    isAdvancedMode,
  });
  const {
    isLoadingQualityDashboard,
    isQualityDashboardOpen,
    qualityDashboard,
    qualityDashboardError,
    refreshQualityDashboard,
    toggleQualityDashboard,
  } = useQualityDashboard({
    isAdvancedMode,
  });
  const {
    activeFeedbackMessageKey,
    evalDraftErrors,
    exportingEvalDrafts,
    exportEvalDraft,
    feedbackErrors,
    feedbackMessages,
    feedbackNoteDrafts,
    feedbackReasonDrafts,
    sourceFeedbackErrors,
    sourceFeedbackMessages,
    submitMessageFeedback,
    submitSourceFeedback,
    submittingFeedback,
    submittingSourceFeedback,
    toggleFeedbackPanel,
    updateFeedbackNoteDraft,
    updateFeedbackReasonDraft,
  } = useMessageQualityActions({
    isAdvancedMode,
    setSessions,
  });

  const bottomRef = useRef<HTMLDivElement | null>(null);
  const messagesContainerRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const previousSessionIdRef = useRef("");
  const previousMessageCountRef = useRef(0);
  const previousLoadingRef = useRef(false);

  const visibleSessions = useMemo(
    () =>
      sessions.filter(
        (session) => session.knowledgeBaseId === selectedKnowledgeBaseId,
      ),
    [selectedKnowledgeBaseId, sessions],
  );
  const currentSession =
    visibleSessions.find((session) => session.id === currentSessionId) ||
    visibleSessions[0] ||
    null;
  const isCurrentSessionLoading = currentSession
    ? Boolean(loadingSessions[currentSession.id])
    : false;
  const currentSessionError = currentSession
    ? sessionErrors[currentSession.id] || ""
    : "";
  const currentSessionLastMessage = currentSession
    ? currentSession.messages[currentSession.messages.length - 1]
    : null;
  const shouldShowThinkingIndicator =
    isCurrentSessionLoading && currentSessionLastMessage?.role !== "assistant";
  const selectedKnowledgeBase = useMemo(
    () =>
      knowledgeBases.find(
        (knowledgeBase) => knowledgeBase.id === selectedKnowledgeBaseId,
      ) || knowledgeBases[0],
    [knowledgeBases, selectedKnowledgeBaseId],
  );
  const updateKnowledgeBaseFileCount = useCallback(
    (knowledgeBaseId: string, fileCount: number) => {
      setKnowledgeBases((prev) =>
        prev.map((knowledgeBase) =>
          knowledgeBase.id === knowledgeBaseId
            ? {
                ...knowledgeBase,
                fileCount,
              }
            : knowledgeBase
        )
      );
    },
    []
  );
  const {
    attachingKnowledgeFileId,
    clearCompletedVectorIndexJobs,
    deletingVectorFileId,
    detachingKnowledgeFileId,
    handleAttachKnowledgeFile,
    handleDeleteKnowledgeFileVectors,
    handlePermanentlyDeleteKnowledgeFile,
    handleIndexKnowledgeBase,
    handleIndexKnowledgeFile,
    handleOpenFileManager,
    handleRemoveKnowledgeFile,
    handleSelectFiles,
    isFileManagerOpen,
    isIndexingKnowledgeBase,
    isLoadingKnowledgeFiles,
    isLoadingReusableFiles,
    isLoadingVectorIndexHealth,
    isUploadingKnowledgeFiles,
    knowledgeBaseFiles,
    knowledgeFileAttachError,
    knowledgeFileDeleteError,
    knowledgeFileDetachError,
    knowledgeFileLoadError,
    knowledgeFileUploadError,
    loadVectorIndexHealth,
    permanentlyDeletingFileId,
    reusableFileLoadError,
    reusableKnowledgeFiles,
    selectedKnowledgeBaseFileCount,
    selectedKnowledgeFiles,
    setIsFileManagerOpen,
    vectorIndexError,
    vectorIndexHealth,
    vectorIndexHealthError,
    vectorIndexingFileIds,
    vectorIndexMessage,
    vectorIndexQueue,
    uploadRetryAfterSeconds,
    vectorIndexRetryAfterSeconds,
  } = useKnowledgeFiles({
    hasCheckedAuth,
    selectedKnowledgeBaseId,
    selectedKnowledgeBaseName: selectedKnowledgeBase?.name || "当前知识库",
    selectedKnowledgeBaseStoredFileCount: selectedKnowledgeBase?.fileCount || 0,
    fileInputRef,
    onKnowledgeBaseFileCountChange: updateKnowledgeBaseFileCount,
  });
  const selectedRetrievalSettings =
    retrievalSettingsByKnowledgeBaseId[selectedKnowledgeBaseId] ||
    DEFAULT_RETRIEVAL_SETTINGS;

  async function handleCreateKnowledgeBase() {
    const normalizedName = newKnowledgeBaseName.trim();

    if (!normalizedName || isCreatingKnowledgeBase) {
      return;
    }

    setIsCreatingKnowledgeBase(true);
    setPageError("");

    try {
      const knowledgeBase = await chatApi.createKnowledgeBase(normalizedName);

      setKnowledgeBases((prev) => [
        ...prev.filter((candidate) => candidate.id !== knowledgeBase.id),
        knowledgeBase,
      ]);
      setSelectedKnowledgeBaseId(knowledgeBase.id);
      setNewKnowledgeBaseName("");
    } catch (error) {
      setPageError(
        error instanceof Error
          ? error.message
          : "创建知识库失败，请稍后再试。"
      );
    } finally {
      setIsCreatingKnowledgeBase(false);
    }
  }

  /** 重新加载活动知识库、会话和回收站数据。 */
  async function refreshKnowledgeBaseCollections(
    preferredKnowledgeBaseId?: string,
  ) {
    const {
      knowledgeBases: nextKnowledgeBases,
      sessions: nextSessions,
    } = await loadBackendKnowledgeBases();
    const preferredKnowledgeBase = nextKnowledgeBases.find(
      (knowledgeBase) => knowledgeBase.id === preferredKnowledgeBaseId,
    );
    const currentKnowledgeBase = nextKnowledgeBases.find(
      (knowledgeBase) => knowledgeBase.id === selectedKnowledgeBaseId,
    );
    const nextSelectedKnowledgeBaseId =
      preferredKnowledgeBase?.id ||
      currentKnowledgeBase?.id ||
      nextKnowledgeBases.find((knowledgeBase) => knowledgeBase.isDefault)?.id ||
      nextKnowledgeBases[0]?.id ||
      "";

    setKnowledgeBases(nextKnowledgeBases);
    setSessions(nextSessions);
    setSelectedKnowledgeBaseId(nextSelectedKnowledgeBaseId);
    setCurrentSessionId((previousSessionId) => {
      const previousSessionStillVisible = nextSessions.some(
        (session) =>
          session.id === previousSessionId &&
          session.knowledgeBaseId === nextSelectedKnowledgeBaseId,
      );
      if (previousSessionStillVisible) {
        return previousSessionId;
      }
      return (
        nextSessions.find(
          (session) => session.knowledgeBaseId === nextSelectedKnowledgeBaseId,
        )?.id || ""
      );
    });
    setDeletedKnowledgeBases(await chatApi.listDeletedKnowledgeBases());
  }

  /** 进入知识库名称编辑状态。 */
  function handleStartKnowledgeBaseRename(knowledgeBase: KnowledgeBase) {
    setEditingKnowledgeBaseId(knowledgeBase.id);
    setEditingKnowledgeBaseName(knowledgeBase.name);
    setKnowledgeBaseLifecycleError("");
    setKnowledgeBaseLifecycleMessage("");
  }

  /** 保存知识库新名称并更新当前工作台状态。 */
  async function handleSaveKnowledgeBaseRename() {
    const normalizedName = editingKnowledgeBaseName.trim();
    if (!editingKnowledgeBaseId || !normalizedName || renamingKnowledgeBaseId) {
      return;
    }

    setRenamingKnowledgeBaseId(editingKnowledgeBaseId);
    setKnowledgeBaseLifecycleError("");
    setKnowledgeBaseLifecycleMessage("");
    try {
      const renamedKnowledgeBase = await chatApi.renameKnowledgeBase(
        editingKnowledgeBaseId,
        normalizedName,
      );
      setKnowledgeBases((previousKnowledgeBases) =>
        previousKnowledgeBases.map((knowledgeBase) =>
          knowledgeBase.id === renamedKnowledgeBase.id
            ? { ...knowledgeBase, name: renamedKnowledgeBase.name }
            : knowledgeBase,
        ),
      );
      setEditingKnowledgeBaseId("");
      setEditingKnowledgeBaseName("");
      setKnowledgeBaseLifecycleMessage("知识库名称已更新。");
    } catch (error) {
      setKnowledgeBaseLifecycleError(
        error instanceof Error
          ? error.message
          : "重命名知识库失败，请稍后再试。",
      );
    } finally {
      setRenamingKnowledgeBaseId("");
    }
  }

  /** 确认后将非默认知识库移入回收站。 */
  async function handleDeleteKnowledgeBase(knowledgeBase: KnowledgeBase) {
    if (knowledgeBase.isDefault || deletingKnowledgeBaseId) {
      return;
    }
    const conversationCount = sessions.filter(
      (session) => session.knowledgeBaseId === knowledgeBase.id,
    ).length;
    if (
      !window.confirm(
        `确认删除知识库“${knowledgeBase.name}”吗？${conversationCount} 个会话会暂时隐藏，但文件仍保留在文件库中，可从回收站恢复。`,
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
      setKnowledgeBaseLifecycleMessage("知识库已移入回收站，文件仍保留。");
    } catch (error) {
      setKnowledgeBaseLifecycleError(
        error instanceof Error
          ? error.message
          : "删除知识库失败，请稍后再试。",
      );
    } finally {
      setDeletingKnowledgeBaseId("");
    }
  }

  /** 恢复回收站知识库并重新加载原会话。 */
  async function handleRestoreKnowledgeBase(knowledgeBaseId: string) {
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
        error instanceof Error
          ? error.message
          : "恢复知识库失败，请稍后再试。",
      );
    } finally {
      setRestoringKnowledgeBaseId("");
    }
  }

  function updateSelectedRetrievalSettings(
    patch: Partial<KnowledgeBaseRetrievalSettings>
  ) {
    if (!selectedKnowledgeBaseId) {
      return;
    }

    setRetrievalSettingsByKnowledgeBaseId((prev) => ({
      ...prev,
      [selectedKnowledgeBaseId]: {
        ...(prev[selectedKnowledgeBaseId] || DEFAULT_RETRIEVAL_SETTINGS),
        ...patch,
      },
    }));
    setRetrievalSettingsMessage("");
    setRetrievalSettingsError("");
  }

  function handleAdvancedModeChange(enabled: boolean) {
    setIsAdvancedMode(enabled);
    writeAdvancedModePreference(enabled);
  }

  async function loadRetrievalSettings(knowledgeBaseId: string) {
    if (!knowledgeBaseId || knowledgeBaseId === DEFAULT_KNOWLEDGE_BASE_ID) {
      return;
    }

    setIsLoadingRetrievalSettings(true);
    setRetrievalSettingsError("");

    try {
      const settings = await chatApi.getRetrievalSettings(knowledgeBaseId);

      setRetrievalSettingsByKnowledgeBaseId((prev) => ({
        ...prev,
        [knowledgeBaseId]: settings,
      }));
    } catch (error) {
      setRetrievalSettingsError(
        error instanceof Error
          ? error.message
          : "读取检索设置失败，请稍后再试。"
      );
    } finally {
      setIsLoadingRetrievalSettings(false);
    }
  }

  async function handleSaveRetrievalSettings() {
    if (
      !selectedKnowledgeBaseId ||
      selectedKnowledgeBaseId === DEFAULT_KNOWLEDGE_BASE_ID ||
      isSavingRetrievalSettings
    ) {
      return;
    }

    setIsSavingRetrievalSettings(true);
    setRetrievalSettingsMessage("");
    setRetrievalSettingsError("");

    try {
      const settings = await chatApi.saveRetrievalSettings(
        selectedKnowledgeBaseId,
        selectedRetrievalSettings,
      );

      setRetrievalSettingsByKnowledgeBaseId((prev) => ({
        ...prev,
        [selectedKnowledgeBaseId]: settings,
      }));
      setRetrievalSettingsMessage("检索设置已保存，下一次提问生效。");
    } catch (error) {
      setRetrievalSettingsError(
        error instanceof Error
          ? error.message
          : "保存检索设置失败，请稍后再试。"
      );
    } finally {
      setIsSavingRetrievalSettings(false);
    }
  }

  async function loadBackendKnowledgeBases() {
    return chatApi.listKnowledgeBasesAndSessions();
  }

  useEffect(() => {
    try {
      const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

      if (!authState) {
        redirectToLogin();
        return;
      }

      setCurrentUsername(getAuthUsername(authState));
    } catch (error) {
      console.error("Failed to read auth state:", error);
      redirectToLogin();
      return;
    }

    setHasCheckedAuth(true);
  }, []);

  useEffect(() => {
    setIsAdvancedMode(readAdvancedModePreference());
  }, []);

  useEffect(() => {
    if (
      !hasCheckedAuth ||
      !isAdvancedMode ||
      !isKnowledgeBaseManagerOpen ||
      !selectedKnowledgeBaseId ||
      selectedKnowledgeBaseId === DEFAULT_KNOWLEDGE_BASE_ID
    ) {
      return;
    }

    void loadRetrievalSettings(selectedKnowledgeBaseId);
  }, [
    hasCheckedAuth,
    isAdvancedMode,
    isKnowledgeBaseManagerOpen,
    selectedKnowledgeBaseId,
  ]);

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
            error instanceof Error
              ? error.message
              : "读取知识库回收站失败，请稍后再试。",
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

  useEffect(() => {
    let isCancelled = false;

    async function restoreKnowledgeBases() {
      try {
        const {
          knowledgeBases: nextKnowledgeBases,
          sessions: nextSessions,
        } = await loadBackendKnowledgeBases();

        if (isCancelled) {
          return;
        }

        const defaultKnowledgeBaseId =
          nextKnowledgeBases.find(
            (knowledgeBase) => knowledgeBase.isDefault
          )?.id ||
          nextKnowledgeBases[0]?.id ||
          "";

        setKnowledgeBases(nextKnowledgeBases);
        setSessions(nextSessions);
        setSelectedKnowledgeBaseId(defaultKnowledgeBaseId);
        setCurrentSessionId(
          nextSessions.find(
            (session) =>
              session.knowledgeBaseId === defaultKnowledgeBaseId
          )?.id || ""
        );
        setPageError("");
      } catch (error) {
        console.error("Failed to load knowledge bases:", error);

        if (!isCancelled) {
          setPageError(
            error instanceof Error
              ? error.message
              : "读取知识库列表失败，请稍后再试。"
          );
        }
      }
    }

    if (hasCheckedAuth) {
      void restoreKnowledgeBases();
    }

    return () => {
      isCancelled = true;
    };
  }, [hasCheckedAuth]);

  useEffect(() => {
    const selectedSessions = sessions.filter(
      (session) => session.knowledgeBaseId === selectedKnowledgeBaseId
    );
    setCurrentSessionId((previousSessionId) =>
      selectedSessions.some(
        (session) => session.id === previousSessionId
      )
        ? previousSessionId
        : selectedSessions[0]?.id || ""
    );
  }, [selectedKnowledgeBaseId, sessions]);

  useEffect(() => {
    const currentMessageCount = currentSession?.messages.length ?? 0;
    const sessionChanged = previousSessionIdRef.current !== currentSession?.id;
    const messageCountIncreased =
      currentMessageCount > previousMessageCountRef.current;
    const loadingStarted = isCurrentSessionLoading && !previousLoadingRef.current;

    if (sessionChanged || messageCountIncreased || loadingStarted) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }

    previousSessionIdRef.current = currentSession?.id ?? "";
    previousMessageCountRef.current = currentMessageCount;
    previousLoadingRef.current = isCurrentSessionLoading;
  }, [currentSession?.id, currentSession?.messages.length, isCurrentSessionLoading]);

  function handleLogout() {
    redirectToLogin();
  }

  async function handleSubmit(overrideInput?: string) {
    const isImageUploadRateLimited =
      pendingChatImages.length > 0 && chatImageRateLimit.isRateLimited;

    if (
      isCurrentSessionLoading ||
      isCreatingSession ||
      isUploadingChatImages ||
      chatRateLimit.isRateLimited ||
      isImageUploadRateLimited
    ) {
      return;
    }

    const messageContent = (overrideInput ?? input).trim();

    if (!messageContent) {
      if (currentSession) {
        setSessionErrors((prev) => ({
          ...prev,
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

    let activeSession = currentSession;

    if (!activeSession) {
      setPageError("");

      try {
        activeSession = await createSession(
          selectedKnowledgeBaseId,
          buildSessionTitle(messageContent)
        );
      } catch (error) {
        setPageError(
          error instanceof Error
            ? error.message
            : "创建对话失败，请稍后再试。"
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
          imagesToSend.map((image) => image.file)
        );
      } catch (error) {
        chatImageRateLimit.startCountdownFromError(error);
        const message =
          error instanceof Error ? error.message : "上传图片失败，请稍后再试。";
        setSessionErrors((prev) => ({
          ...prev,
          [activeSession.id]: message,
        }));
        return;
      } finally {
        setIsUploadingChatImages(false);
      }
    }

    const userMessage: Message = {
      role: "user",
      content: messageContent,
      ...(uploadedAttachments.length > 0
        ? { attachments: uploadedAttachments }
        : {}),
    };

    const updatedMessages = [...activeSession.messages, userMessage];
    const activeSessionId = activeSession.id;
    const activeKnowledgeBaseId = activeSession.knowledgeBaseId;

    setSessions((prev) =>
      prev.map((session) =>
        session.id === activeSessionId
          ? {
              ...session,
              title:
                session.messages.length === 0
                  ? buildSessionTitle(messageContent)
                  : session.title,
              messages: updatedMessages,
            }
          : session
      )
    );

    setInput("");
    if (imagesToSend.length > 0) {
      clearPendingChatImages();
    }
    setSessionErrors((prev) => ({
      ...prev,
      [activeSessionId]: "",
    }));
    setLoadingSessions((prev) => ({
      ...prev,
      [activeSessionId]: true,
    }));

    const appendAssistantContent = (content: string) => {
      setSessions((prev) =>
        prev.map((session) => {
          if (session.id !== activeSessionId) {
            return session;
          }

          const messages = [...session.messages];
          const lastMessage = messages[messages.length - 1];

          if (lastMessage?.role === "assistant") {
            messages[messages.length - 1] = {
              ...lastMessage,
              content: lastMessage.content + content,
            };
          } else {
            messages.push({
              role: "assistant",
              content,
            });
          }

          return {
            ...session,
            messages,
          };
        })
      );
    };

    const setAssistantSources = (sources: ChatSource[]) => {
      if (sources.length === 0) {
        return;
      }

      setSessions((prev) =>
        prev.map((session) => {
          if (session.id !== activeSessionId) {
            return session;
          }

          const messages = [...session.messages];
          const lastMessage = messages[messages.length - 1];

          if (lastMessage?.role === "assistant") {
            messages[messages.length - 1] = {
              ...lastMessage,
              sources,
            };
          } else {
            messages.push({
              role: "assistant",
              content: "",
              sources,
            });
          }

          return {
            ...session,
            messages,
          };
        })
      );
    };

    const setAssistantRetrieval = (retrieval: RetrievalState) => {
      setSessions((prev) =>
        prev.map((session) => {
          if (session.id !== activeSessionId) {
            return session;
          }

          const messages = [...session.messages];
          const lastMessage = messages[messages.length - 1];

          if (lastMessage?.role === "assistant") {
            messages[messages.length - 1] = {
              ...lastMessage,
              retrieval,
            };
          } else {
            messages.push({
              role: "assistant",
              content: "",
              retrieval,
            });
          }

          return {
            ...session,
            messages,
          };
        })
      );
    };

    const setAssistantMessageId = (messageId: string) => {
      if (!messageId) {
        return;
      }

      setSessions((prev) =>
        prev.map((session) => {
          if (session.id !== activeSessionId) {
            return session;
          }

          const messages = [...session.messages];
          const lastMessage = messages[messages.length - 1];

          if (lastMessage?.role === "assistant") {
            messages[messages.length - 1] = {
              ...lastMessage,
              id: messageId,
            };
          }

          return {
            ...session,
            messages,
          };
        })
      );
    };

    const setAssistantFallback = (content: string) => {
      setSessions((prev) =>
        prev.map((session) => {
          if (session.id !== activeSessionId) {
            return session;
          }

          const messages = [...session.messages];
          const lastMessage = messages[messages.length - 1];

          if (lastMessage?.role === "assistant") {
            messages[messages.length - 1] = {
              ...lastMessage,
              content,
            };
          } else {
            messages.push({
              role: "assistant",
              content,
            });
          }

          return {
            ...session,
            messages,
          };
        })
      );
    };

    try {
      const response = await chatApi.postChatMessage(
        activeSessionId,
        activeKnowledgeBaseId,
        messageContent,
        uploadedAttachments.map((attachment) => attachment.id),
      );

      await streamChatResponse(response, {
        appendAssistantContent,
        setAssistantFallback,
        setAssistantMessageId,
        setAssistantRetrieval,
        setAssistantSources,
        onDone: () => {
          if (isAdvancedMode) {
            void loadDiagnostics(activeSessionId, { silent: true });
          }
        },
      });
    } catch (error) {
      console.error(error);
      chatRateLimit.startCountdownFromError(error);
      setSessionErrors((prev) => ({
        ...prev,
        [activeSessionId]:
          error instanceof Error ? error.message : "请求失败了，请稍后再试。",
      }));
    } finally {
      setLoadingSessions((prev) => ({
        ...prev,
        [activeSessionId]: false,
      }));
    }
  }

  if (!hasCheckedAuth) {
    return (
      <main className="research-canvas flex min-h-screen items-center justify-center px-4">
        <div className="font-utility flex items-center gap-3 text-xs font-semibold text-[#176b62]">
          <span className="h-2.5 w-2.5 animate-pulse bg-[#e36b4f]" />
          正在打开工作台...
        </div>
      </main>
    );
  }

  return (
    <main className="research-canvas min-h-screen px-3 py-3 md:px-5 md:py-5 lg:h-screen lg:overflow-hidden">
      <div className="mx-auto grid min-w-0 w-full max-w-[1440px] gap-4 lg:h-full lg:grid-cols-[304px_minmax(0,1fr)]">
        <aside className="research-enter flex min-w-0 max-h-[calc(100vh-1.5rem)] flex-col border border-[#bdcac5] bg-[#edf2ef] p-4 lg:sticky lg:top-5 lg:h-[calc(100vh-2.5rem)] lg:max-h-none">
          <SidebarAccountModeControls
            currentUsername={currentUsername}
            isAdvancedMode={isAdvancedMode}
            onLogout={handleLogout}
            onAdvancedModeChange={handleAdvancedModeChange}
          />

          {isAdvancedMode && (
            <QualityDashboardPanel
              isOpen={isQualityDashboardOpen}
              dashboard={qualityDashboard}
              isLoading={isLoadingQualityDashboard}
              error={qualityDashboardError}
              onToggle={toggleQualityDashboard}
              onRefresh={refreshQualityDashboard}
            />
          )}

          <KnowledgeBaseSidebarControls
            knowledgeBases={knowledgeBases}
            selectedKnowledgeBaseId={selectedKnowledgeBaseId}
            selectedFileCount={selectedKnowledgeBaseFileCount}
            isUploadingFiles={isUploadingKnowledgeFiles}
            uploadRetryAfterSeconds={uploadRetryAfterSeconds}
            fileInputRef={fileInputRef}
            onSelectedKnowledgeBaseChange={setSelectedKnowledgeBaseId}
            onOpenKnowledgeBaseManager={() =>
              setIsKnowledgeBaseManagerOpen(true)
            }
            onOpenFileManager={handleOpenFileManager}
            onFilesSelected={handleSelectFiles}
          />

          <ConversationSidebar
            sessions={visibleSessions}
            activeSessionId={currentSession?.id || ""}
            isCreatingSession={isCreatingSession}
            editingSessionId={editingSessionId}
            editingTitle={editingTitle}
            renamingSessionId={renamingSessionId}
            deletingSessionId={deletingSessionId}
            onCreateSession={handleCreateSession}
            onSelectSession={handleSelectSession}
            onStartRename={handleStartRename}
            onEditingTitleChange={setEditingTitle}
            onSaveRename={handleSaveRename}
            onCancelRename={handleCancelRename}
            onDeleteSession={handleDeleteSession}
          />
        </aside>

        <section className="research-paper research-enter min-w-0 border border-[#bdcac5] lg:flex lg:h-full lg:min-h-0 lg:flex-col lg:overflow-hidden">
          <ChatWorkspaceHeader
            knowledgeBaseName={selectedKnowledgeBase?.name}
            sessionTitle={currentSession?.title}
            messageCount={currentSession?.messages.length || 0}
            fileCount={selectedKnowledgeBaseFileCount}
          />

          <div
            ref={messagesContainerRef}
            className="research-scroll px-5 py-7 md:px-8 md:py-9 lg:min-h-0 lg:flex-1 lg:overflow-y-auto lg:overscroll-contain"
          >
            <div className="space-y-6">
              {!currentSession && (
                <div className="flex min-h-[240px] items-center justify-center text-center">
                  <p className="text-sm text-[#7b8884]">
                    输入问题，开始新的对话
                  </p>
                </div>
              )}

              {currentSession?.messages.length === 0 && (
                <div className="border-y border-[#cbd5d1] py-12 text-center">
                  <p className="font-utility text-[10px] font-semibold uppercase text-[#176b62]">
                    Chat
                  </p>
                  <h2 className="font-display mt-3 text-2xl font-semibold text-[#17201f]">
                    从一个明确的问题开始
                  </h2>
                  <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[#64716d]">
                    你的问题和 AI 回答会按顺序记录在这里，便于后续回顾与继续追问。
                  </p>
                </div>
              )}

              {currentSession?.messages.map((message, index) => {
                const messageKey = `${currentSession.id}-${index}`;

                return (
                  <ConversationMessageItem
                    key={messageKey}
                    messageKey={messageKey}
                    message={message}
                    position={index + 1}
                    isLatestMessage={
                      index === currentSession.messages.length - 1
                    }
                    isCurrentSessionLoading={isCurrentSessionLoading}
                    isAdvancedMode={isAdvancedMode}
                    isCopied={copiedMessageKey === messageKey}
                    feedbackState={{
                      reasonDraft: feedbackReasonDrafts[messageKey],
                      noteDraft: feedbackNoteDrafts[messageKey],
                      isPanelOpen: activeFeedbackMessageKey === messageKey,
                      isSubmitting: Boolean(submittingFeedback[messageKey]),
                      errorMessage: feedbackErrors[messageKey] || "",
                      successMessage: feedbackMessages[messageKey] || "",
                    }}
                    diagnosticState={getDiagnosticState(
                      currentSession.id,
                      messageKey,
                      message.id,
                    )}
                    evalDraftState={{
                      isExporting: Boolean(
                        exportingEvalDrafts[messageKey]
                      ),
                      errorMessage: evalDraftErrors[messageKey] || "",
                    }}
                    sourceFeedbackState={{
                      submitting: submittingSourceFeedback,
                      errors: sourceFeedbackErrors,
                      messages: sourceFeedbackMessages,
                    }}
                    onOpenSource={setActiveSourcePreview}
                    onSubmitSourceFeedback={({
                      sourceKey,
                      sourceIndex,
                      rating,
                    }) =>
                      submitSourceFeedback({
                        sessionId: currentSession.id,
                        messageId: message.id,
                        sourceKey,
                        sourceIndex,
                        rating,
                      })
                    }
                    onSubmitMessageFeedback={(request) =>
                      submitMessageFeedback({
                        sessionId: currentSession.id,
                        messageKey,
                        messageId: message.id,
                        ...request,
                      })
                    }
                    onToggleNegativeFeedback={() =>
                      toggleFeedbackPanel(messageKey)
                    }
                    onFeedbackReasonChange={(reason) =>
                      updateFeedbackReasonDraft(messageKey, reason)
                    }
                    onFeedbackNoteChange={(note) =>
                      updateFeedbackNoteDraft(messageKey, note)
                    }
                    onExportEvalDraft={() =>
                      exportEvalDraft(messageKey, message.id)
                    }
                    onToggleDiagnostics={() =>
                      toggleDiagnostics(currentSession.id, messageKey)
                    }
                    onCopy={() =>
                      copyMessage(messageKey, message.content)
                    }
                  />
                );
              })}

              {shouldShowThinkingIndicator && (
                <div className="grid gap-3 border-l-2 border-[#176b62] pl-5 md:grid-cols-[74px_minmax(0,1fr)] md:gap-5 md:pl-6">
                  <p className="font-utility pt-1 text-[10px] font-semibold uppercase text-[#72807b]">
                    Response
                  </p>
                  <div className="animate-pulse border border-[#d5ded9] bg-[#f5f8f6] px-5 py-4 text-sm text-[#64716d]">
                    正在检索资料并组织回答...
                  </div>
                </div>
              )}

              {currentSessionError && (
                <div className="border-l-4 border-[#e36b4f] bg-[#fff1ed] px-5 py-4 text-[#9b3c29]">
                  {currentSessionError}
                </div>
              )}

              {pageError && (
                <div className="border-l-4 border-[#e36b4f] bg-[#fff1ed] px-5 py-4 text-[#9b3c29]">
                  {pageError}
                </div>
              )}

              <div ref={bottomRef} />
            </div>
          </div>

          <ChatComposer
            input={input}
            pendingImages={pendingChatImages}
            imageInputRef={chatImageInputRef}
            isCurrentSessionLoading={isCurrentSessionLoading}
            isCreatingSession={isCreatingSession}
            isUploadingImages={isUploadingChatImages}
            isChatRateLimited={chatRateLimit.isRateLimited}
            chatRetryAfterSeconds={chatRateLimit.retryAfterSeconds}
            isImageRateLimited={chatImageRateLimit.isRateLimited}
            imageRetryAfterSeconds={chatImageRateLimit.retryAfterSeconds}
            canSendToKnowledgeBase={
              Boolean(selectedKnowledgeBaseId) &&
              selectedKnowledgeBaseId !== DEFAULT_KNOWLEDGE_BASE_ID
            }
            onInputChange={setInput}
            onPasteImages={handlePasteChatImages}
            onSelectImages={handleSelectChatImages}
            onRemoveImage={removePendingChatImage}
            onSubmit={handleSubmit}
          />
        </section>
      </div>

      {isKnowledgeBaseManagerOpen ? (
        <KnowledgeBaseManagerDialog
          selectedKnowledgeBaseName={selectedKnowledgeBase?.name || "暂无知识库"}
          selectedKnowledgeBaseId={selectedKnowledgeBaseId}
          knowledgeBases={knowledgeBases}
          knowledgeBaseFiles={knowledgeBaseFiles}
          sessions={sessions}
          deletedKnowledgeBases={deletedKnowledgeBases}
          isLoadingDeletedKnowledgeBases={isLoadingDeletedKnowledgeBases}
          knowledgeBaseLifecycleMessage={knowledgeBaseLifecycleMessage}
          knowledgeBaseLifecycleError={knowledgeBaseLifecycleError}
          editingKnowledgeBaseId={editingKnowledgeBaseId}
          editingKnowledgeBaseName={editingKnowledgeBaseName}
          renamingKnowledgeBaseId={renamingKnowledgeBaseId}
          deletingKnowledgeBaseId={deletingKnowledgeBaseId}
          restoringKnowledgeBaseId={restoringKnowledgeBaseId}
          isAdvancedMode={isAdvancedMode}
          selectedRetrievalSettings={selectedRetrievalSettings}
          isLoadingRetrievalSettings={isLoadingRetrievalSettings}
          isSavingRetrievalSettings={isSavingRetrievalSettings}
          retrievalSettingsMessage={retrievalSettingsMessage}
          retrievalSettingsError={retrievalSettingsError}
          newKnowledgeBaseName={newKnowledgeBaseName}
          isCreatingKnowledgeBase={isCreatingKnowledgeBase}
          onClose={() => setIsKnowledgeBaseManagerOpen(false)}
          onSelectKnowledgeBase={setSelectedKnowledgeBaseId}
          onStartRename={handleStartKnowledgeBaseRename}
          onEditingNameChange={setEditingKnowledgeBaseName}
          onCancelRename={() => {
            setEditingKnowledgeBaseId("");
            setEditingKnowledgeBaseName("");
          }}
          onSaveRename={handleSaveKnowledgeBaseRename}
          onDeleteKnowledgeBase={handleDeleteKnowledgeBase}
          onRestoreKnowledgeBase={handleRestoreKnowledgeBase}
          onUpdateRetrievalSettings={updateSelectedRetrievalSettings}
          onSaveRetrievalSettings={handleSaveRetrievalSettings}
          onNewKnowledgeBaseNameChange={setNewKnowledgeBaseName}
          onCreateKnowledgeBase={handleCreateKnowledgeBase}
        />
      ) : null}

      {isFileManagerOpen && (
        <FileManagerDialog
          knowledgeBaseName={selectedKnowledgeBase?.name || "暂无知识库"}
          selectedKnowledgeBaseId={selectedKnowledgeBaseId}
          selectedFiles={selectedKnowledgeFiles}
          reusableFiles={reusableKnowledgeFiles}
          vectorIndexingFileIds={vectorIndexingFileIds}
          vectorIndexQueue={vectorIndexQueue}
          vectorIndexHealth={vectorIndexHealth}
          vectorIndexHealthError={vectorIndexHealthError}
          isLoadingVectorIndexHealth={isLoadingVectorIndexHealth}
          isUploadingKnowledgeFiles={isUploadingKnowledgeFiles}
          isIndexingKnowledgeBase={isIndexingKnowledgeBase}
          isLoadingKnowledgeFiles={isLoadingKnowledgeFiles}
          isLoadingReusableFiles={isLoadingReusableFiles}
          deletingVectorFileId={deletingVectorFileId}
          permanentlyDeletingFileId={permanentlyDeletingFileId}
          detachingKnowledgeFileId={detachingKnowledgeFileId}
          attachingKnowledgeFileId={attachingKnowledgeFileId}
          knowledgeFileUploadError={knowledgeFileUploadError}
          knowledgeFileDetachError={knowledgeFileDetachError}
          knowledgeFileAttachError={knowledgeFileAttachError}
          knowledgeFileDeleteError={knowledgeFileDeleteError}
          knowledgeFileLoadError={knowledgeFileLoadError}
          reusableFileLoadError={reusableFileLoadError}
          vectorIndexMessage={vectorIndexMessage}
          vectorIndexError={vectorIndexError}
          uploadRetryAfterSeconds={uploadRetryAfterSeconds}
          vectorIndexRetryAfterSeconds={vectorIndexRetryAfterSeconds}
          onClose={() => setIsFileManagerOpen(false)}
          onUploadClick={() => fileInputRef.current?.click()}
          onIndexKnowledgeBase={handleIndexKnowledgeBase}
          onRefreshVectorHealth={loadVectorIndexHealth}
          onClearCompletedJobs={clearCompletedVectorIndexJobs}
          onIndexFile={handleIndexKnowledgeFile}
          onDeleteFileVectors={handleDeleteKnowledgeFileVectors}
          onPermanentlyDeleteFile={handlePermanentlyDeleteKnowledgeFile}
          onRemoveFile={handleRemoveKnowledgeFile}
          onAttachFile={handleAttachKnowledgeFile}
        />
      )}

      {activeSourcePreview && (
        <SourcePreviewDialog
          source={activeSourcePreview}
          onClose={() => setActiveSourcePreview(null)}
        />
      )}

      <button
        onClick={() => {
          if (window.matchMedia("(min-width: 1024px)").matches) {
            messagesContainerRef.current?.scrollTo({
              top: 0,
              behavior: "smooth",
            });
            return;
          }

          window.scrollTo({ top: 0, behavior: "smooth" });
        }}
        className="font-utility fixed bottom-5 right-5 border border-[#9bada6] bg-[#fcfdfb] px-3 py-2 text-[10px] font-semibold uppercase text-[#46514e] shadow-sm transition hover:border-[#176b62] hover:text-[#176b62]"
      >
        Top ↑
      </button>
    </main>
  );
}
