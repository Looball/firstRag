"use client";

import Link from "next/link";
import { FileManagerDialog } from "@/components/chat-workspace/FileManagerDialog";
import { MessageDiagnosticsPanel } from "@/components/chat-workspace/MessageDiagnosticsPanel";
import {
  type ReactNode,
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
import {
  redirectToLogin,
} from "@/lib/frontend-api";
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
import { useKnowledgeFiles } from "@/lib/chat-workspace/use-knowledge-files";
import {
  buildSessionTitle,
} from "@/lib/chat-workspace/utils";
import { streamChatResponse } from "@/lib/chat-workspace/chat-stream";
import type {
  ChatSession,
  ChatSource,
  KnowledgeBase,
  KnowledgeBaseRetrievalSettings,
  Message,
  MessageFeedbackReason,
  MessageFeedbackRating,
  MessageDiagnostic,
  MessageSourceFeedbackRating,
  QualityDashboard,
  RetrievalMode,
  RetrievalState,
} from "@/lib/chat-workspace/types";

const MESSAGE_FEEDBACK_REASON_OPTIONS: Array<{
  value: MessageFeedbackReason;
  label: string;
}> = [
  { value: "missing_answer", label: "没有答到点" },
  { value: "irrelevant_sources", label: "引用不相关" },
  { value: "hallucination", label: "疑似幻觉" },
  { value: "outdated_or_wrong", label: "内容错误或过时" },
  { value: "too_slow", label: "回答太慢" },
  { value: "format_issue", label: "格式不好" },
  { value: "other", label: "其他" },
];

const isDevelopmentEnvironment = process.env.NODE_ENV === "development";

function formatPercent(value: number | null) {
  return typeof value === "number" && Number.isFinite(value)
    ? `${Math.round(value * 100)}%`
    : "—";
}

function formatMetricNumber(value: number | null, digits = 1) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "—";
  }

  return value.toFixed(digits);
}

function formatMetricMs(value: number | null) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "—";
  }

  return value >= 1000
    ? `${(value / 1000).toFixed(2)}s`
    : `${value.toFixed(0)}ms`;
}

function renderInlineMarkdown(
  text: string,
  keyPrefix: string,
  isUserMessage: boolean
) {
  const nodes: ReactNode[] = [];
  const pattern = /(`[^`]*`|\*\*[^*]+\*\*)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let partIndex = 0;

  while ((match = pattern.exec(text))) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }

    const token = match[0];

    if (token.startsWith("`")) {
      nodes.push(
        <code
          key={`${keyPrefix}-code-${partIndex}`}
          className={`rounded px-1.5 py-0.5 font-mono text-[0.92em] ${
            isUserMessage
              ? "bg-white/15 text-white"
              : "bg-[#dfe9e5] text-[#105149]"
          }`}
        >
          {token.slice(1, -1)}
        </code>
      );
    } else {
      nodes.push(
        <strong key={`${keyPrefix}-strong-${partIndex}`} className="font-semibold">
          {token.slice(2, -2)}
        </strong>
      );
    }

    partIndex += 1;
    lastIndex = pattern.lastIndex;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes;
}

function isMarkdownBlockStart(line: string) {
  return (
    /^```/.test(line) ||
    /^#{1,6}\s+/.test(line) ||
    /^\s*\d+\.\s+/.test(line) ||
    /^\s*[-*]\s+/.test(line)
  );
}

function MarkdownContent({
  content,
  isUserMessage,
}: {
  content: string;
  isUserMessage: boolean;
}) {
  const lines = content.split("\n");
  const blocks: ReactNode[] = [];
  let index = 0;
  let blockIndex = 0;

  const inline = (text: string, suffix: string) =>
    renderInlineMarkdown(text, `md-${blockIndex}-${suffix}`, isUserMessage);

  while (index < lines.length) {
    const line = lines[index];

    if (!line.trim()) {
      index += 1;
      continue;
    }

    const codeFenceMatch = line.match(/^```(\w+)?\s*$/);

    if (codeFenceMatch) {
      const codeLines: string[] = [];
      index += 1;

      while (index < lines.length && !/^```\s*$/.test(lines[index])) {
        codeLines.push(lines[index]);
        index += 1;
      }

      if (index < lines.length) {
        index += 1;
      }

      blocks.push(
        <pre
          key={`code-${blockIndex}`}
          className={`overflow-x-auto rounded-xl px-4 py-3 text-sm ${
            isUserMessage
              ? "bg-black/25 text-white"
              : "bg-[#17201f] text-[#eef5f2]"
          }`}
        >
          <code>{codeLines.join("\n")}</code>
        </pre>
      );
      blockIndex += 1;
      continue;
    }

    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);

    if (headingMatch) {
      const level = headingMatch[1].length;
      const text = headingMatch[2];
      const headingClass =
        level <= 1
          ? "text-2xl font-semibold leading-8"
          : level === 2
            ? "text-xl font-semibold leading-8"
            : "text-lg font-semibold leading-7";

      if (level <= 1) {
        blocks.push(
          <h2 key={`heading-${blockIndex}`} className={headingClass}>
            {inline(text, "heading")}
          </h2>
        );
      } else if (level === 2) {
        blocks.push(
          <h3 key={`heading-${blockIndex}`} className={headingClass}>
            {inline(text, "heading")}
          </h3>
        );
      } else {
        blocks.push(
          <h4 key={`heading-${blockIndex}`} className={headingClass}>
            {inline(text, "heading")}
          </h4>
        );
      }

      index += 1;
      blockIndex += 1;
      continue;
    }

    const orderedMatch = line.match(/^\s*\d+\.\s+(.+)$/);

    if (orderedMatch) {
      const items: string[] = [];

      while (index < lines.length) {
        const itemMatch = lines[index].match(/^\s*\d+\.\s+(.+)$/);

        if (!itemMatch) {
          break;
        }

        const itemLines = [itemMatch[1]];
        index += 1;

        while (
          index < lines.length &&
          lines[index].trim() &&
          !isMarkdownBlockStart(lines[index])
        ) {
          itemLines.push(lines[index].trim());
          index += 1;
        }

        items.push(itemLines.join("\n"));
      }

      blocks.push(
        <ol key={`ol-${blockIndex}`} className="list-decimal space-y-2 pl-6">
          {items.map((item, itemIndex) => (
            <li
              key={`ol-${blockIndex}-${itemIndex}`}
              className="whitespace-pre-wrap pl-1"
            >
              {renderInlineMarkdown(
                item,
                `md-${blockIndex}-ol-${itemIndex}`,
                isUserMessage
              )}
            </li>
          ))}
        </ol>
      );
      blockIndex += 1;
      continue;
    }

    const unorderedMatch = line.match(/^\s*[-*]\s+(.+)$/);

    if (unorderedMatch) {
      const items: string[] = [];

      while (index < lines.length) {
        const itemMatch = lines[index].match(/^\s*[-*]\s+(.+)$/);

        if (!itemMatch) {
          break;
        }

        const itemLines = [itemMatch[1]];
        index += 1;

        while (
          index < lines.length &&
          lines[index].trim() &&
          !isMarkdownBlockStart(lines[index])
        ) {
          itemLines.push(lines[index].trim());
          index += 1;
        }

        items.push(itemLines.join("\n"));
      }

      blocks.push(
        <ul key={`ul-${blockIndex}`} className="list-disc space-y-2 pl-6">
          {items.map((item, itemIndex) => (
            <li
              key={`ul-${blockIndex}-${itemIndex}`}
              className="whitespace-pre-wrap pl-1"
            >
              {renderInlineMarkdown(
                item,
                `md-${blockIndex}-ul-${itemIndex}`,
                isUserMessage
              )}
            </li>
          ))}
        </ul>
      );
      blockIndex += 1;
      continue;
    }

    const paragraphLines: string[] = [];

    while (
      index < lines.length &&
      lines[index].trim() &&
      !isMarkdownBlockStart(lines[index])
    ) {
      paragraphLines.push(lines[index]);
      index += 1;
    }

    blocks.push(
      <p key={`p-${blockIndex}`} className="whitespace-pre-wrap">
        {inline(paragraphLines.join("\n"), "paragraph")}
      </p>
    );
    blockIndex += 1;
  }

  return <div className="space-y-3 leading-7 break-words">{blocks}</div>;
}

export default function Home() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState("");
  const [input, setInput] = useState("");
  const [isAdvancedMode, setIsAdvancedMode] = useState(getAdvancedModeDefault);
  const [editingSessionId, setEditingSessionId] = useState("");
  const [editingTitle, setEditingTitle] = useState("");
  const [renamingSessionId, setRenamingSessionId] = useState("");
  const [deletingSessionId, setDeletingSessionId] = useState("");
  const [copiedMessageKey, setCopiedMessageKey] = useState("");
  const [loadingSessions, setLoadingSessions] = useState<Record<string, boolean>>(
    {}
  );
  const [sessionErrors, setSessionErrors] = useState<Record<string, string>>({});
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
  const [hasCheckedAuth, setHasCheckedAuth] = useState(false);
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const [isCreatingKnowledgeBase, setIsCreatingKnowledgeBase] =
    useState(false);
  const [pageError, setPageError] = useState("");
  const [currentUsername, setCurrentUsername] = useState("");
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
  const [activeFeedbackMessageKey, setActiveFeedbackMessageKey] = useState("");
  const [feedbackReasonDrafts, setFeedbackReasonDrafts] = useState<
    Record<string, MessageFeedbackReason>
  >({});
  const [feedbackNoteDrafts, setFeedbackNoteDrafts] = useState<
    Record<string, string>
  >({});
  const [submittingFeedback, setSubmittingFeedback] = useState<
    Record<string, boolean>
  >({});
  const [feedbackErrors, setFeedbackErrors] = useState<Record<string, string>>({});
  const [feedbackMessages, setFeedbackMessages] = useState<Record<string, string>>(
    {}
  );
  const [submittingSourceFeedback, setSubmittingSourceFeedback] = useState<
    Record<string, boolean>
  >({});
  const [sourceFeedbackErrors, setSourceFeedbackErrors] = useState<
    Record<string, string>
  >({});
  const [sourceFeedbackMessages, setSourceFeedbackMessages] = useState<
    Record<string, string>
  >({});
  const [exportingEvalDrafts, setExportingEvalDrafts] = useState<
    Record<string, boolean>
  >({});
  const [evalDraftErrors, setEvalDraftErrors] = useState<Record<string, string>>(
    {},
  );
  const [isQualityDashboardOpen, setIsQualityDashboardOpen] = useState(false);
  const [qualityDashboard, setQualityDashboard] =
    useState<QualityDashboard | null>(null);
  const [isLoadingQualityDashboard, setIsLoadingQualityDashboard] =
    useState(false);
  const [qualityDashboardError, setQualityDashboardError] = useState("");

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
  const currentSessionMessageId = currentSession?.id || "";
  const areCurrentSessionMessagesLoaded =
    currentSession?.messagesLoaded ?? true;
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
    knowledgeFileDetachError,
    knowledgeFileLoadError,
    knowledgeFileUploadError,
    loadVectorIndexHealth,
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

  async function createBackendSession(
    knowledgeBaseId: string,
    title = "新对话"
  ) {
    return chatApi.createConversation(knowledgeBaseId, title);
  }

  async function loadBackendMessages(conversationId: string) {
    return chatApi.listConversationMessages(conversationId);
  }

  async function handleSelectSession(session: ChatSession) {
    setCurrentSessionId(session.id);

    if (session.messagesLoaded) {
      return;
    }

    setSessionErrors((prev) => ({ ...prev, [session.id]: "" }));

    try {
      const messages = await loadBackendMessages(session.id);
      setSessions((prev) =>
        prev.map((candidate) =>
          candidate.id === session.id
            ? { ...candidate, messages, messagesLoaded: true }
            : candidate
        )
      );
    } catch (error) {
      setSessionErrors((prev) => ({
        ...prev,
        [session.id]:
          error instanceof Error
            ? error.message
            : "读取会话消息失败，请稍后再试。",
      }));
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
    if (isAdvancedMode) {
      return;
    }

    setIsQualityDashboardOpen(false);
    setExpandedDiagnosticPanels({});
    setActiveFeedbackMessageKey("");
  }, [isAdvancedMode]);

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
    let isCancelled = false;

    if (currentSessionMessageId && !areCurrentSessionMessagesLoaded) {
      const sessionId = currentSessionMessageId;

      void loadBackendMessages(sessionId)
        .then((messages) => {
          if (isCancelled) {
            return;
          }

          setSessions((previousSessions) =>
            previousSessions.map((session) =>
              session.id === sessionId
                ? { ...session, messages, messagesLoaded: true }
                : session
            )
          );
        })
        .catch((error) => {
          if (isCancelled) {
            return;
          }

          setSessionErrors((previousErrors) => ({
            ...previousErrors,
            [sessionId]:
              error instanceof Error
                ? error.message
                : "读取会话消息失败，请稍后再试。",
          }));
        });
    }

    return () => {
      isCancelled = true;
    };
  }, [areCurrentSessionMessagesLoaded, currentSessionMessageId]);

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

  async function handleCreateSession() {
    if (
      !selectedKnowledgeBaseId ||
      selectedKnowledgeBaseId === DEFAULT_KNOWLEDGE_BASE_ID
    ) {
      setPageError("请先选择一个知识库。");
      return;
    }

    setIsCreatingSession(true);
    setPageError("");

    try {
      const newSession = await createBackendSession(selectedKnowledgeBaseId);

      setSessions((prev) => [newSession, ...prev]);
      setCurrentSessionId(newSession.id);
      setInput("");
    } catch (error) {
      setPageError(
        error instanceof Error ? error.message : "创建对话失败，请稍后再试。"
      );
    } finally {
      setIsCreatingSession(false);
    }
  }

  async function handleDeleteSession(sessionId: string) {
    if (deletingSessionId) {
      return;
    }

    setDeletingSessionId(sessionId);
    setPageError("");

    try {
      const session = sessions.find(
        (candidate) => candidate.id === sessionId
      );
      const knowledgeBaseId =
        session?.knowledgeBaseId || selectedKnowledgeBaseId;
      await chatApi.deleteConversation(knowledgeBaseId, sessionId);

      const allRemainingSessions = sessions.filter(
        (session) => session.id !== sessionId
      );
      const remainingVisibleSessions = allRemainingSessions.filter(
        (session) => session.knowledgeBaseId === knowledgeBaseId
      );

      setSessions(allRemainingSessions);
      setLoadingSessions((prev) => {
        const next = { ...prev };
        delete next[sessionId];
        return next;
      });
      setSessionErrors((prev) => {
        const next = { ...prev };
        delete next[sessionId];
        return next;
      });

      if (editingSessionId === sessionId) {
        setEditingSessionId("");
        setEditingTitle("");
      }

      if (remainingVisibleSessions.length === 0) {
        setCurrentSessionId("");
        setInput("");
      } else if (currentSessionId === sessionId) {
        setCurrentSessionId(remainingVisibleSessions[0].id);
        setInput("");
      }
    } catch (error) {
      setPageError(
        error instanceof Error ? error.message : "删除会话失败，请稍后再试。"
      );
    } finally {
      setDeletingSessionId("");
    }
  }

  function handleStartRename(session: ChatSession) {
    setEditingSessionId(session.id);
    setEditingTitle(session.title);
  }

  async function handleSaveRename() {
    if (!editingSessionId || renamingSessionId) {
      return;
    }

    const normalizedTitle = editingTitle.trim() || "新对话";
    const session = sessions.find(
      (candidate) => candidate.id === editingSessionId
    );
    const knowledgeBaseId =
      session?.knowledgeBaseId || selectedKnowledgeBaseId;

    setRenamingSessionId(editingSessionId);
    setSessionErrors((prev) => ({
      ...prev,
      [editingSessionId]: "",
    }));

    try {
      await chatApi.renameConversation(
        knowledgeBaseId,
        editingSessionId,
        normalizedTitle,
      );

      setSessions((prev) =>
        prev.map((session) =>
          session.id === editingSessionId
            ? {
                ...session,
                title: normalizedTitle,
              }
            : session
        )
      );

      setEditingSessionId("");
      setEditingTitle("");
    } catch (error) {
      setSessionErrors((prev) => ({
        ...prev,
        [editingSessionId]:
          error instanceof Error ? error.message : "重命名失败，请稍后再试。",
      }));
    } finally {
      setRenamingSessionId("");
    }
  }

  function handleCancelRename() {
    setEditingSessionId("");
    setEditingTitle("");
  }

  async function handleCopyMessage(messageKey: string, content: string) {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(content);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = content;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      }

      setCopiedMessageKey(messageKey);

      window.setTimeout(() => {
        setCopiedMessageKey((current) =>
          current === messageKey ? "" : current
        );
      }, 1500);
    } catch (error) {
      console.error("Failed to copy message:", error);

      try {
        const textarea = document.createElement("textarea");
        textarea.value = content;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);

        setCopiedMessageKey(messageKey);

        window.setTimeout(() => {
          setCopiedMessageKey((current) =>
            current === messageKey ? "" : current
          );
        }, 1500);
      } catch (fallbackError) {
        console.error("Fallback copy also failed:", fallbackError);
      }
    }
  }

  async function handleSubmitMessageFeedback({
    sessionId,
    messageKey,
    messageId,
    rating,
    reason,
    note,
  }: {
    sessionId: string;
    messageKey: string;
    messageId?: string;
    rating: MessageFeedbackRating;
    reason?: MessageFeedbackReason | null;
    note?: string | null;
  }) {
    if (!messageId) {
      setFeedbackErrors((prev) => ({
        ...prev,
        [messageKey]: "这条回答还没有保存完成，稍后再反馈。",
      }));
      return;
    }

    setSubmittingFeedback((prev) => ({
      ...prev,
      [messageKey]: true,
    }));
    setFeedbackErrors((prev) => ({
      ...prev,
      [messageKey]: "",
    }));
    setFeedbackMessages((prev) => ({
      ...prev,
      [messageKey]: "正在保存反馈...",
    }));

    try {
      const feedback = await chatApi.submitMessageFeedback(messageId, {
        rating,
        reason: rating === "negative" ? reason || "other" : null,
        note: rating === "negative" ? note?.trim() || null : null,
      });

      setSessions((prev) =>
        prev.map((session) =>
          session.id === sessionId
            ? {
                ...session,
                messages: session.messages.map((message) =>
                  message.id === messageId
                    ? {
                        ...message,
                        feedback,
                      }
                    : message
                ),
              }
            : session
        )
      );
      setActiveFeedbackMessageKey((current) =>
        current === messageKey ? "" : current
      );
      setFeedbackMessages((prev) => ({
        ...prev,
        [messageKey]:
          rating === "positive" ? "已标记为有用" : "已记录问题反馈",
      }));
      window.setTimeout(() => {
        setFeedbackMessages((prev) => {
          if (
            prev[messageKey] !== "已标记为有用" &&
            prev[messageKey] !== "已记录问题反馈"
          ) {
            return prev;
          }

          const next = { ...prev };
          delete next[messageKey];
          return next;
        });
      }, 2000);
    } catch (error) {
      setFeedbackMessages((prev) => {
        const next = { ...prev };
        delete next[messageKey];
        return next;
      });
      setFeedbackErrors((prev) => ({
        ...prev,
        [messageKey]:
          error instanceof Error ? error.message : "保存反馈失败，请稍后再试。",
      }));
    } finally {
      setSubmittingFeedback((prev) => ({
        ...prev,
        [messageKey]: false,
      }));
    }
  }

  async function handleSubmitSourceFeedback({
    sessionId,
    messageId,
    sourceKey,
    sourceIndex,
    rating,
  }: {
    sessionId: string;
    messageId?: string;
    sourceKey: string;
    sourceIndex: number;
    rating: MessageSourceFeedbackRating;
  }) {
    if (!messageId) {
      setSourceFeedbackErrors((prev) => ({
        ...prev,
        [sourceKey]: "这条回答还没有保存完成，稍后再标记引用。",
      }));
      return;
    }

    setSubmittingSourceFeedback((prev) => ({
      ...prev,
      [sourceKey]: true,
    }));
    setSourceFeedbackErrors((prev) => ({
      ...prev,
      [sourceKey]: "",
    }));
    setSourceFeedbackMessages((prev) => ({
      ...prev,
      [sourceKey]: "正在保存引用反馈...",
    }));

    try {
      const feedback = await chatApi.submitMessageSourceFeedback(
        messageId,
        sourceIndex,
        { rating },
      );

      setSessions((prev) =>
        prev.map((session) =>
          session.id === sessionId
            ? {
                ...session,
                messages: session.messages.map((message) =>
                  message.id === messageId
                    ? {
                        ...message,
                        sources: message.sources?.map((source, position) => {
                          const currentSourceIndex = source.index ?? position;

                          return currentSourceIndex === sourceIndex
                            ? {
                                ...source,
                                feedback,
                              }
                            : source;
                        }),
                      }
                    : message
                ),
              }
            : session
        )
      );
      setSourceFeedbackMessages((prev) => ({
        ...prev,
        [sourceKey]:
          rating === "useful" ? "已标记引用有用" : "已标记引用无关",
      }));
      window.setTimeout(() => {
        setSourceFeedbackMessages((prev) => {
          if (
            prev[sourceKey] !== "已标记引用有用" &&
            prev[sourceKey] !== "已标记引用无关"
          ) {
            return prev;
          }

          const next = { ...prev };
          delete next[sourceKey];
          return next;
        });
      }, 2000);
    } catch (error) {
      setSourceFeedbackMessages((prev) => {
        const next = { ...prev };
        delete next[sourceKey];
        return next;
      });
      setSourceFeedbackErrors((prev) => ({
        ...prev,
        [sourceKey]:
          error instanceof Error
            ? error.message
            : "保存引用反馈失败，请稍后再试。",
      }));
    } finally {
      setSubmittingSourceFeedback((prev) => ({
        ...prev,
        [sourceKey]: false,
      }));
    }
  }

  async function handleExportEvalDraft(messageKey: string, messageId?: string) {
    if (!isAdvancedMode) {
      return;
    }

    if (!messageId) {
      setEvalDraftErrors((prev) => ({
        ...prev,
        [messageKey]: "这条回答还没有保存完成，稍后再导出。",
      }));
      return;
    }

    setExportingEvalDrafts((prev) => ({
      ...prev,
      [messageKey]: true,
    }));
    setEvalDraftErrors((prev) => ({
      ...prev,
      [messageKey]: "",
    }));

    try {
      const draft = await chatApi.exportEvalCaseDraft(messageId);
      const draftId =
        typeof draft.id === "string" && draft.id.trim()
          ? draft.id.trim()
          : `draft_message_${messageId}`;
      const blob = new Blob([`${JSON.stringify(draft, null, 2)}\n`], {
        type: "application/json;charset=utf-8",
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");

      link.href = url;
      link.download = `${draftId}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (error) {
      setEvalDraftErrors((prev) => ({
        ...prev,
        [messageKey]:
          error instanceof Error
            ? error.message
            : "导出 eval case 草稿失败，请稍后再试。",
      }));
    } finally {
      setExportingEvalDrafts((prev) => ({
        ...prev,
        [messageKey]: false,
      }));
    }
  }

  async function handleToggleQualityDashboard() {
    if (!isAdvancedMode) {
      return;
    }

    const shouldOpen = !isQualityDashboardOpen;

    setIsQualityDashboardOpen(shouldOpen);
    if (!shouldOpen || qualityDashboard || isLoadingQualityDashboard) {
      return;
    }

    setIsLoadingQualityDashboard(true);
    setQualityDashboardError("");

    try {
      const dashboard = await chatApi.loadQualityDashboard(7);
      setQualityDashboard(dashboard);
    } catch (error) {
      setQualityDashboardError(
        error instanceof Error ? error.message : "加载质量看板失败，请稍后再试。",
      );
    } finally {
      setIsLoadingQualityDashboard(false);
    }
  }

  async function handleRefreshQualityDashboard() {
    if (!isAdvancedMode) {
      return;
    }

    setIsLoadingQualityDashboard(true);
    setQualityDashboardError("");

    try {
      const dashboard = await chatApi.loadQualityDashboard(7);
      setQualityDashboard(dashboard);
    } catch (error) {
      setQualityDashboardError(
        error instanceof Error ? error.message : "加载质量看板失败，请稍后再试。",
      );
    } finally {
      setIsLoadingQualityDashboard(false);
    }
  }

  async function loadConversationDiagnostics(
    conversationId: string,
    options: { silent?: boolean } = {}
  ) {
    if (!options.silent) {
      setLoadingDiagnostics((prev) => ({
        ...prev,
        [conversationId]: true,
      }));
      setDiagnosticErrors((prev) => ({
        ...prev,
        [conversationId]: "",
      }));
    }

    try {
      const diagnostics = await chatApi.loadConversationDiagnostics(conversationId);

      setConversationDiagnostics((prev) => ({
        ...prev,
        [conversationId]: diagnostics,
      }));
    } catch (error) {
      if (!options.silent) {
        setDiagnosticErrors((prev) => ({
          ...prev,
          [conversationId]:
            error instanceof Error
              ? error.message
              : "加载诊断信息失败，请稍后再试。",
        }));
      }
    } finally {
      if (!options.silent) {
        setLoadingDiagnostics((prev) => ({
          ...prev,
          [conversationId]: false,
        }));
      }
    }
  }

  function handleToggleDiagnostics(conversationId: string, messageKey: string) {
    if (!isAdvancedMode) {
      return;
    }

    const panelKey = `${conversationId}:${messageKey}`;
    const shouldOpen = !expandedDiagnosticPanels[panelKey];

    setExpandedDiagnosticPanels((prev) => ({
      ...prev,
      [panelKey]: shouldOpen,
    }));

    if (
      shouldOpen &&
      conversationDiagnostics[conversationId] === undefined &&
      !loadingDiagnostics[conversationId]
    ) {
      void loadConversationDiagnostics(conversationId);
    }
  }

  async function handleSubmit(overrideInput?: string) {
    if (isCurrentSessionLoading || isCreatingSession) {
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
      setIsCreatingSession(true);
      setPageError("");

      try {
        const newSession = await createBackendSession(
          selectedKnowledgeBaseId,
          buildSessionTitle(messageContent)
        );
        activeSession = newSession;
        setSessions((prev) => [newSession, ...prev]);
        setCurrentSessionId(newSession.id);
      } catch (error) {
        setPageError(
          error instanceof Error
            ? error.message
            : "创建对话失败，请稍后再试。"
        );
        return;
      } finally {
        setIsCreatingSession(false);
      }
    }

    setPageError("");

    const userMessage: Message = {
      role: "user",
      content: messageContent,
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
      );

      await streamChatResponse(response, {
        appendAssistantContent,
        setAssistantFallback,
        setAssistantMessageId,
        setAssistantRetrieval,
        setAssistantSources,
        onDone: () => {
          if (isAdvancedMode) {
            void loadConversationDiagnostics(activeSessionId, { silent: true });
          }
        },
      });
    } catch (error) {
      console.error(error);
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
          <div className="flex items-center justify-between gap-3 border-b border-[#c7d1cd] px-1 pb-4">
            <div className="min-w-0">
              <p className="font-utility text-[10px] font-semibold uppercase text-[#72807b]">
                FirstRAG
              </p>
              <Link
                href="/settings"
                title="打开用户设置"
                className="font-display mt-1 block truncate text-lg font-semibold text-[#17201f] underline decoration-[#d5a83b] decoration-2 underline-offset-4 transition hover:text-[#176b62]"
              >
                {currentUsername || "已登录"}
              </Link>
            </div>
            <button
              type="button"
              onClick={handleLogout}
              className="font-utility shrink-0 border-b border-[#9eaaa6] px-1 py-1 text-[11px] font-semibold text-[#64716d] transition hover:border-[#e36b4f] hover:text-[#9b3c29]"
            >
              退出
            </button>
          </div>

          <div className="border-b border-[#c7d1cd] py-4">
            <div className="flex items-center justify-between gap-3">
              <p className="font-utility text-[10px] font-semibold uppercase text-[#72807b]">
                模式
              </p>
              <div className="grid grid-cols-2 border border-[#cbd5d1] bg-[#f8faf8] p-0.5 text-[11px] font-semibold text-[#64716d]">
                <button
                  type="button"
                  aria-pressed={!isAdvancedMode}
                  onClick={() => handleAdvancedModeChange(false)}
                  className={`px-2 py-1 transition ${
                    !isAdvancedMode
                      ? "bg-[#176b62] text-white"
                      : "hover:text-[#176b62]"
                  }`}
                >
                  普通
                </button>
                <button
                  type="button"
                  aria-pressed={isAdvancedMode}
                  onClick={() => handleAdvancedModeChange(true)}
                  className={`px-2 py-1 transition ${
                    isAdvancedMode
                      ? "bg-[#176b62] text-white"
                      : "hover:text-[#176b62]"
                  }`}
                >
                  高级
                </button>
              </div>
            </div>
          </div>

          {isAdvancedMode && (
            <div className="border-b border-[#c7d1cd] py-4">
              <div className="flex items-center justify-between gap-3">
                <p className="font-utility text-[10px] font-semibold uppercase text-[#72807b]">
                  Quality
                </p>
                <button
                  type="button"
                  onClick={() => {
                    void handleToggleQualityDashboard();
                  }}
                  className="text-xs font-semibold text-[#176b62] underline decoration-[#d5a83b] decoration-2 underline-offset-4"
                >
                  {isQualityDashboardOpen ? "收起" : "质量看板"}
                </button>
              </div>

              {isQualityDashboardOpen && (
                <div className="mt-3 border border-[#d5ded9] bg-[#f8faf8] p-3 text-xs text-[#46514e]">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-utility text-[10px] font-semibold uppercase text-[#64716d]">
                      最近 {qualityDashboard?.windowDays ?? 7} 天
                    </p>
                    <button
                      type="button"
                      disabled={isLoadingQualityDashboard}
                      onClick={() => {
                        void handleRefreshQualityDashboard();
                      }}
                      className="font-utility text-[10px] font-semibold uppercase text-[#176b62] disabled:opacity-60"
                    >
                      {isLoadingQualityDashboard ? "加载中" : "刷新"}
                    </button>
                  </div>

                {qualityDashboardError && (
                  <p className="mt-3 text-[#9b3c29]">{qualityDashboardError}</p>
                )}

                {!qualityDashboardError &&
                  !isLoadingQualityDashboard &&
                  !qualityDashboard?.hasFeedback && (
                    <p className="mt-3 leading-5 text-[#64716d]">
                      还没有回答或引用反馈。这里不会把空数据当成质量良好。
                    </p>
                  )}

                {qualityDashboard && qualityDashboard.hasFeedback && (
                  <div className="mt-3 grid gap-3">
                    <div className="grid grid-cols-3 gap-2">
                      <div>
                        <p className="text-[10px] text-[#72807b]">反馈</p>
                        <p className="font-display text-lg font-semibold text-[#17201f]">
                          {qualityDashboard.messageFeedback.total}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-[#72807b]">负反馈</p>
                        <p className="font-display text-lg font-semibold text-[#9b3c29]">
                          {formatPercent(
                            qualityDashboard.messageFeedback.negativeRate,
                          )}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-[#72807b]">引用无关</p>
                        <p className="font-display text-lg font-semibold text-[#9b3c29]">
                          {formatPercent(
                            qualityDashboard.sourceFeedback.irrelevantRate,
                          )}
                        </p>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2 border-t border-[#d5ded9] pt-3">
                      <div>
                        <p className="text-[10px] text-[#72807b]">平均引用</p>
                        <p className="font-semibold text-[#17201f]">
                          {formatMetricNumber(
                            qualityDashboard.retrieval.averageSources,
                          )}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-[#72807b]">首 token</p>
                        <p className="font-semibold text-[#17201f]">
                          {formatMetricMs(
                            qualityDashboard.retrieval.averageFirstTokenMs,
                          )}
                        </p>
                      </div>
                    </div>
                    {qualityDashboard.messageFeedback.reasonDistribution.length >
                      0 && (
                      <div className="border-t border-[#d5ded9] pt-3">
                        <p className="font-utility text-[10px] font-semibold uppercase text-[#64716d]">
                          负反馈原因
                        </p>
                        <div className="mt-2 space-y-1">
                          {qualityDashboard.messageFeedback.reasonDistribution.map(
                            (item) => (
                              <p
                                key={item.reason}
                                className="flex justify-between gap-3"
                              >
                                <span className="truncate">{item.reason}</span>
                                <span>{item.count}</span>
                              </p>
                            ),
                          )}
                        </div>
                      </div>
                    )}
                    {qualityDashboard.sourceFeedback.topIrrelevantFiles.length >
                      0 && (
                      <div className="border-t border-[#d5ded9] pt-3">
                        <p className="font-utility text-[10px] font-semibold uppercase text-[#64716d]">
                          无关引用来源
                        </p>
                        <div className="mt-2 space-y-1">
                          {qualityDashboard.sourceFeedback.topIrrelevantFiles.map(
                            (item) => (
                              <p
                                key={item.fileName}
                                className="flex justify-between gap-3"
                              >
                                <span className="truncate">{item.fileName}</span>
                                <span>{item.count}</span>
                              </p>
                            ),
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
          )}

          <div className="border-b border-[#c7d1cd] py-4">
            <div className="flex items-center justify-between gap-3">
              <label
                htmlFor="knowledge-base"
                className="font-utility text-[10px] font-semibold uppercase text-[#72807b]"
              >
                Knowledge Base
              </label>
              <button
                type="button"
                onClick={() => setIsKnowledgeBaseManagerOpen(true)}
                className="text-xs font-semibold text-[#176b62] underline decoration-[#d5a83b] decoration-2 underline-offset-4"
              >
                管理
              </button>
            </div>

            <select
              id="knowledge-base"
              value={selectedKnowledgeBaseId}
              onChange={(event) =>
                setSelectedKnowledgeBaseId(event.target.value)
              }
              className="research-focus mt-2 w-full border border-[#b7c4bf] bg-[#fcfdfb] px-3 py-2.5 text-sm font-semibold text-[#17201f]"
            >
              {knowledgeBases.length === 0 && (
                <option value="">暂无知识库</option>
              )}
              {knowledgeBases.map((knowledgeBase) => (
                <option key={knowledgeBase.id} value={knowledgeBase.id}>
                  {knowledgeBase.name}
                </option>
              ))}
            </select>

            <div className="mt-3 grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={
                  !selectedKnowledgeBaseId || isUploadingKnowledgeFiles
                }
                className="bg-[#176b62] px-3 py-2.5 text-xs font-semibold text-white transition hover:bg-[#105149] disabled:bg-[#91aaa4]"
              >
                {isUploadingKnowledgeFiles ? "上传中..." : "上传文件"}
              </button>
              <button
                type="button"
                onClick={() => {
                  void handleOpenFileManager();
                }}
                className="border border-[#aebdb7] bg-[#fcfdfb] px-3 py-2.5 text-xs font-semibold text-[#46514e] transition hover:border-[#176b62] hover:text-[#176b62]"
              >
                文件 {selectedKnowledgeBaseFileCount}
              </button>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".txt,.md,.csv,.json,.pdf,.png,.jpg,.jpeg,.webp,.gif"
              onChange={(event) => {
                void handleSelectFiles(event.target.files);
              }}
              className="hidden"
            />
          </div>

          <button
            onClick={() => {
              void handleCreateSession();
            }}
            disabled={isCreatingSession}
            className="mt-4 w-full border border-[#17201f] bg-[#17201f] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#2d3936] disabled:border-[#9ba8a3] disabled:bg-[#9ba8a3]"
          >
            {isCreatingSession ? "创建中..." : "＋ 新建研究会话"}
          </button>

          <div className="mt-4 flex items-center justify-between px-1">
            <p className="font-utility text-[10px] font-semibold uppercase text-[#72807b]">
              Conversation Index
            </p>
            <p className="font-utility text-[10px] text-[#72807b]">
              {String(visibleSessions.length).padStart(2, "0")}
            </p>
          </div>

          <div className="mt-2 min-h-0 min-w-0 flex-1 space-y-2 overflow-y-auto pr-1">
            {visibleSessions.length === 0 && (
              <p className="px-1 py-2 text-xs text-[#7b8884]">
                暂无会话，发送问题即可开始
              </p>
            )}
            {visibleSessions.map((session) => {
              const isActive = session.id === currentSession?.id;

              return (
                <div
                  key={session.id}
                  className={`min-w-0 w-full border-l-4 px-3 py-3 text-left text-sm transition ${
                    isActive
                      ? "border-[#e36b4f] bg-[#17201f] text-white"
                      : "border-transparent bg-[#fcfdfb] text-[#46514e] hover:border-[#d5a83b] hover:bg-white"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      {editingSessionId === session.id ? (
                        <div className="space-y-2">
                          <input
                            value={editingTitle}
                            onChange={(e) => setEditingTitle(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") {
                                e.preventDefault();
                                void handleSaveRename();
                              }

                              if (e.key === "Escape") {
                                handleCancelRename();
                              }
                            }}
                            autoFocus
                            className="research-focus w-full border border-[#b7c4bf] bg-white px-3 py-2 text-sm text-[#17201f]"
                          />
                          <div className="flex gap-2">
                            <button
                              onClick={() => {
                                void handleSaveRename();
                              }}
                              disabled={renamingSessionId === session.id}
                              className="bg-[#176b62] px-2 py-1 text-xs text-white transition hover:bg-[#105149]"
                            >
                              {renamingSessionId === session.id
                                ? "保存中..."
                                : "保存"}
                            </button>
                            <button
                              onClick={handleCancelRename}
                              className="px-2 py-1 text-xs transition hover:bg-[#dfe7e3] hover:text-[#17201f]"
                            >
                              取消
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button
                          onClick={() => {
                            void handleSelectSession(session);
                          }}
                          className="min-w-0 w-full text-left"
                        >
                          <div className="truncate font-semibold">{session.title}</div>
                          <div
                            className={`mt-1 truncate text-xs ${
                              isActive ? "text-[#b8c8c3]" : "text-[#7b8884]"
                            }`}
                          >
                            {session.messages[session.messages.length - 1]?.content ||
                              "暂无消息"}
                          </div>
                        </button>
                      )}
                    </div>

                    {editingSessionId !== session.id && (
                      <div className="flex shrink-0 gap-1">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleStartRename(session);
                          }}
                          className={`rounded-lg px-2 py-1 text-xs transition ${
                            isActive
                              ? "text-[#b8c8c3] hover:bg-white/10 hover:text-white"
                              : "text-[#73807c] hover:bg-[#dfe7e3] hover:text-[#17201f]"
                          }`}
                        >
                          重命名
                        </button>

                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            void handleDeleteSession(session.id);
                          }}
                          disabled={deletingSessionId === session.id}
                          className={`rounded-lg px-2 py-1 text-xs transition ${
                            isActive
                              ? "text-[#b8c8c3] hover:bg-white/10 hover:text-white"
                              : "text-[#73807c] hover:bg-[#fff1ed] hover:text-[#9b3c29]"
                          }`}
                        >
                          {deletingSessionId === session.id
                            ? "删除中..."
                            : "删除"}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </aside>

        <section className="research-paper research-enter min-w-0 border border-[#bdcac5] lg:flex lg:h-full lg:min-h-0 lg:flex-col lg:overflow-hidden">
          <header className="shrink-0 border-b border-[#cbd5d1] bg-[#fcfdfb] px-5 py-5 md:px-8 md:py-6">
            <div className="flex flex-col justify-between gap-5 md:flex-row md:items-end">
              <div className="min-w-0">
                <div className="flex items-center gap-3">
                  <span className="font-utility bg-[#d5a83b] px-2 py-1 text-[10px] font-bold uppercase text-[#17201f]">
                    Live Research
                  </span>
                  <span className="font-utility text-[10px] font-semibold uppercase text-[#72807b]">
                    {selectedKnowledgeBase?.name || "暂无知识库"}
                  </span>
                </div>
                <h1 className="font-display mt-4 truncate text-3xl font-semibold text-[#17201f] md:text-4xl">
                  {currentSession?.title || "聊天工作台"}
                </h1>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-[#64716d]">
                  基于当前知识库继续提问，回答与上下文会保存在此会话中。
                </p>
              </div>
              <div className="font-utility flex shrink-0 gap-5 border-t border-[#d6dedb] pt-4 text-[10px] uppercase text-[#72807b] md:border-l md:border-t-0 md:pl-5 md:pt-0">
                <span>
                  消息
                  <strong className="mt-1 block text-base text-[#17201f]">
                    {String(currentSession?.messages.length || 0).padStart(2, "0")}
                  </strong>
                </span>
                <span>
                  文件
                  <strong className="mt-1 block text-base text-[#17201f]">
                    {String(selectedKnowledgeBaseFileCount).padStart(2, "0")}
                  </strong>
                </span>
              </div>
            </div>
          </header>

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
                const diagnosticPanelKey = `${currentSession.id}:${messageKey}`;
                const isDiagnosticExpanded = Boolean(
                  expandedDiagnosticPanels[diagnosticPanelKey]
                );
                const cachedDiagnostics =
                  conversationDiagnostics[currentSession.id];
                const diagnostic = message.id
                  ? (cachedDiagnostics?.find(
                      (item) => item.messageId === message.id
                    ) ?? null)
                  : null;
                const isDiagnosticLoading = Boolean(
                  loadingDiagnostics[currentSession.id]
                );
                const diagnosticError =
                  diagnosticErrors[currentSession.id] || "";
                const isStreamingPlaceholder =
                  message.role === "assistant" &&
                  index === currentSession.messages.length - 1 &&
                  isCurrentSessionLoading &&
                  !message.content;
                const sourceCount = message.sources?.length ?? 0;
                const shouldShowSources =
                  message.role === "assistant" && sourceCount > 0;
                const displaySourceCount =
                  message.retrieval && message.retrieval.source_count > 0
                    ? message.retrieval.source_count
                    : sourceCount;
                const retrievedCount =
                  message.retrieval && message.retrieval.retrieved_count > 0
                    ? message.retrieval.retrieved_count
                    : null;
                const shouldShowRetrievalEmptyHint =
                  message.role === "assistant" &&
                  message.retrieval?.need_retrieval === true &&
                  message.retrieval.source_count === 0 &&
                  !shouldShowSources;
                const feedbackReason =
                  feedbackReasonDrafts[messageKey] ||
                  message.feedback?.reason ||
                  "missing_answer";
                const feedbackNote =
                  feedbackNoteDrafts[messageKey] ?? message.feedback?.note ?? "";
                const isFeedbackPanelOpen =
                  activeFeedbackMessageKey === messageKey;
                const isFeedbackSubmitting = Boolean(
                  submittingFeedback[messageKey]
                );
                const feedbackError = feedbackErrors[messageKey] || "";
                const feedbackMessage = feedbackMessages[messageKey] || "";
                const messageFeedbackRating = message.feedback?.rating;
                const messageFeedbackLabel =
                  messageFeedbackRating === "positive"
                    ? "已标记：有用"
                    : messageFeedbackRating === "negative"
                      ? "已标记：有问题"
                      : "";
                const isExportingEvalDraft = Boolean(
                  exportingEvalDrafts[messageKey]
                );
                const evalDraftError = evalDraftErrors[messageKey] || "";
                const canExportEvalDraft =
                  isAdvancedMode &&
                  isDevelopmentEnvironment &&
                  message.role === "assistant" &&
                  message.feedback?.rating === "negative";

                return (
                  <div
                    key={messageKey}
                    className={`relative grid min-w-0 gap-3 border-l-2 pl-5 md:grid-cols-[74px_minmax(0,1fr)] md:gap-5 md:pl-6 ${
                      message.role === "user"
                        ? "border-[#e36b4f]"
                        : "border-[#176b62]"
                    }`}
                  >
                    <div className="font-utility pt-1 text-[10px] font-semibold uppercase text-[#72807b]">
                      <span className="block text-[#17201f]">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                      {message.role === "user" ? "问题" : "回答"}
                    </div>
                    <article
                      className={`min-w-0 px-5 py-4 ${
                        message.role === "user"
                          ? "bg-[#17201f] text-white"
                          : "border border-[#d5ded9] bg-[#f5f8f6] text-[#26312f]"
                      }`}
                    >
                      <MarkdownContent
                        content={
                          isStreamingPlaceholder
                            ? "AI 正在思考中..."
                            : message.content
                        }
                        isUserMessage={message.role === "user"}
                      />

                      {shouldShowRetrievalEmptyHint && (
                        <div className="mt-4 border-t border-[#d6dedb] pt-3">
                          <p className="text-xs leading-5 text-[#64716d]">
                            已检索知识库，但没有找到高相关引用
                          </p>
                        </div>
                      )}

                      {shouldShowSources && message.sources && (
                        <div className="mt-4 border-t border-[#d6dedb] pt-3">
                          <div className="flex flex-wrap items-baseline justify-between gap-2">
                            <p className="font-utility text-[10px] font-semibold uppercase text-[#64716d]">
                              引用来源
                            </p>
                            <p className="text-xs text-[#64716d]">
                              可展示 {displaySourceCount} 条
                              {isAdvancedMode && retrievedCount !== null
                                ? ` · 召回 ${retrievedCount} 段`
                                : ""}
                            </p>
                          </div>
                          <div className="mt-2 space-y-2">
                            {message.sources.map((source, sourceIndex) => {
                              const currentSourceIndex =
                                source.index ?? sourceIndex;
                              const sourceKey = `${messageKey}-source-${currentSourceIndex}`;
                              const isSourceFeedbackSubmitting = Boolean(
                                submittingSourceFeedback[sourceKey]
                              );
                              const sourceFeedbackError =
                                sourceFeedbackErrors[sourceKey] || "";
                              const sourceFeedbackMessage =
                                sourceFeedbackMessages[sourceKey] || "";
                              const sourceFeedbackRating =
                                source.feedback?.rating;
                              const sourceFeedbackLabel =
                                sourceFeedbackRating === "useful"
                                  ? "已标记：引用有用"
                                  : sourceFeedbackRating === "irrelevant"
                                    ? "已标记：引用无关"
                                    : "";
                              const sourceFileMeta = [
                                source.fileName !== source.title
                                  ? source.fileName
                                  : "",
                                source.fileType,
                                isAdvancedMode ? source.fileId : "",
                              ]
                                .filter(Boolean)
                                .join(" · ");

                              return (
                                <div
                                  key={sourceKey}
                                  className="border border-[#d5ded9] bg-[#fcfdfb] px-3 py-2 text-xs text-[#46514e]"
                                >
                                  <div className="flex items-start justify-between gap-3">
                                    <p className="min-w-0 truncate font-semibold text-[#17201f]">
                                      {source.title}
                                    </p>
                                    {isAdvancedMode && (
                                    <div className="font-utility flex shrink-0 flex-wrap justify-end gap-2 text-[10px] text-[#72807b]">
                                      {source.chunkIndex !== undefined && (
                                        <span>
                                          Chunk #{source.chunkIndex}
                                        </span>
                                      )}
                                      {source.retrievalSources &&
                                        source.retrievalSources.length > 0 && (
                                          <span>
                                            {source.retrievalSources.join(" / ")}
                                          </span>
                                        )}
                                      {source.vectorScore !== undefined && (
                                        <span>
                                          Vector {source.vectorScore.toFixed(4)}
                                        </span>
                                      )}
                                      {source.fulltextScore !== undefined && (
                                        <span>
                                          Fulltext{" "}
                                          {source.fulltextScore.toFixed(4)}
                                        </span>
                                      )}
                                      {source.rerankScore !== undefined && (
                                        <span>
                                          Rerank {source.rerankScore.toFixed(4)}
                                        </span>
                                      )}
                                      {source.rrfScore !== undefined && (
                                        <span>
                                          RRF {source.rrfScore.toFixed(4)}
                                        </span>
                                      )}
                                      {source.metadata && (
                                        <span>{source.metadata}</span>
                                      )}
                                    </div>
                                    )}
                                  </div>
                                  {source.content && (
                                    <p className="mt-1 max-h-10 overflow-hidden leading-5 text-[#64716d]">
                                      {source.content}
                                    </p>
                                  )}
                                  {sourceFileMeta && (
                                    <p className="mt-1 truncate text-[11px] text-[#72807b]">
                                      {sourceFileMeta}
                                    </p>
                                  )}
                                  {isAdvancedMode && (
                                  <div className="mt-2 flex flex-wrap items-center justify-between gap-2 border-t border-[#e2e8e5] pt-2">
                                    {sourceFeedbackRating &&
                                    !isSourceFeedbackSubmitting ? (
                                      <p
                                        className={`font-utility text-[10px] font-semibold uppercase ${
                                          sourceFeedbackRating === "useful"
                                            ? "text-[#176b62]"
                                            : "text-[#9b3c29]"
                                        }`}
                                      >
                                        {sourceFeedbackLabel}
                                      </p>
                                    ) : (
                                      <div className="flex flex-wrap items-center gap-2">
                                        <button
                                          type="button"
                                          disabled={isSourceFeedbackSubmitting}
                                          onClick={() =>
                                            handleSubmitSourceFeedback({
                                              sessionId: currentSession.id,
                                              messageId: message.id,
                                              sourceKey,
                                              sourceIndex: currentSourceIndex,
                                              rating: "useful",
                                            })
                                          }
                                          className="font-utility border border-[#cbd5d1] px-2 py-1 text-[10px] font-semibold uppercase text-[#64716d] transition hover:border-[#176b62] hover:text-[#176b62] disabled:cursor-not-allowed disabled:opacity-60"
                                        >
                                          {isSourceFeedbackSubmitting
                                            ? "保存中"
                                            : "引用有用"}
                                        </button>
                                        <button
                                          type="button"
                                          disabled={isSourceFeedbackSubmitting}
                                          onClick={() =>
                                            handleSubmitSourceFeedback({
                                              sessionId: currentSession.id,
                                              messageId: message.id,
                                              sourceKey,
                                              sourceIndex: currentSourceIndex,
                                              rating: "irrelevant",
                                            })
                                          }
                                          className="font-utility border border-[#cbd5d1] px-2 py-1 text-[10px] font-semibold uppercase text-[#64716d] transition hover:border-[#e36b4f] hover:text-[#9b3c29] disabled:cursor-not-allowed disabled:opacity-60"
                                        >
                                          {isSourceFeedbackSubmitting
                                            ? "保存中"
                                            : "引用无关"}
                                        </button>
                                      </div>
                                    )}
                                    {sourceFeedbackError && (
                                      <p className="text-[11px] text-[#9b3c29]">
                                        {sourceFeedbackError}
                                      </p>
                                    )}
                                    {!sourceFeedbackError &&
                                      sourceFeedbackMessage && (
                                        <p className="text-[11px] text-[#176b62]">
                                          {sourceFeedbackMessage}
                                        </p>
                                      )}
                                  </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {message.role === "assistant" &&
                        isAdvancedMode &&
                        isDiagnosticExpanded && (
                          <MessageDiagnosticsPanel
                            messageKey={messageKey}
                            diagnostic={diagnostic}
                            isLoading={isDiagnosticLoading}
                            hasLoadedDiagnostics={Boolean(cachedDiagnostics)}
                            errorMessage={diagnosticError}
                          />
                        )}

                      {message.role === "assistant" && message.content && (
                        <div className="mt-4 border-t border-[#d6dedb] pt-3">
                          <div
                            className={`flex flex-wrap items-center gap-3 ${
                              isAdvancedMode ? "justify-between" : "justify-end"
                            }`}
                          >
                            {isAdvancedMode &&
                              (messageFeedbackRating &&
                              !isFeedbackSubmitting ? (
                              <p
                                className={`font-utility text-[10px] font-semibold uppercase ${
                                  messageFeedbackRating === "positive"
                                    ? "text-[#176b62]"
                                    : "text-[#9b3c29]"
                                }`}
                              >
                                {messageFeedbackLabel}
                              </p>
                            ) : (
                              <div className="flex flex-wrap items-center gap-2">
                                <button
                                  type="button"
                                  disabled={isFeedbackSubmitting}
                                  onClick={() =>
                                    handleSubmitMessageFeedback({
                                      sessionId: currentSession.id,
                                      messageKey,
                                      messageId: message.id,
                                      rating: "positive",
                                    })
                                  }
                                  className="font-utility border border-[#cbd5d1] px-2 py-1 text-[10px] font-semibold uppercase text-[#64716d] transition hover:border-[#176b62] hover:text-[#176b62] disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                  {isFeedbackSubmitting ? "保存中" : "有用"}
                                </button>
                                <button
                                  type="button"
                                  disabled={isFeedbackSubmitting}
                                  onClick={() =>
                                    setActiveFeedbackMessageKey((current) =>
                                      current === messageKey ? "" : messageKey
                                    )
                                  }
                                  className="font-utility border border-[#cbd5d1] px-2 py-1 text-[10px] font-semibold uppercase text-[#64716d] transition hover:border-[#e36b4f] hover:text-[#9b3c29] disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                  有问题
                                </button>
                              </div>
                            ))}
                            <div className="flex flex-wrap items-center gap-3">
                              {canExportEvalDraft && (
                                <button
                                  type="button"
                                  disabled={isExportingEvalDraft}
                                  onClick={() =>
                                    handleExportEvalDraft(
                                      messageKey,
                                      message.id
                                    )
                                  }
                                  className="font-utility text-[10px] font-semibold uppercase text-[#64716d] transition hover:text-[#176b62] disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                  {isExportingEvalDraft
                                    ? "导出中"
                                    : "Eval 草稿"}
                                </button>
                              )}
                              {isAdvancedMode && (
                              <button
                                type="button"
                                onClick={() =>
                                  handleToggleDiagnostics(
                                    currentSession.id,
                                    messageKey
                                  )
                                }
                                className="font-utility text-[10px] font-semibold uppercase text-[#64716d] transition hover:text-[#176b62]"
                              >
                                {isDiagnosticExpanded ? "收起诊断" : "诊断"}
                              </button>
                              )}
                              <button
                                type="button"
                                onClick={() =>
                                  handleCopyMessage(messageKey, message.content)
                                }
                                className="font-utility text-[10px] font-semibold uppercase text-[#64716d] transition hover:text-[#176b62]"
                              >
                                {copiedMessageKey === messageKey
                                  ? "已复制"
                                  : "复制回答"}
                              </button>
                            </div>
                          </div>
                          {isAdvancedMode && isFeedbackPanelOpen && (
                            <div className="mt-3 grid gap-2 border border-[#d5ded9] bg-[#fcfdfb] p-3">
                              <div className="grid gap-2 md:grid-cols-[180px_minmax(0,1fr)]">
                                <select
                                  value={feedbackReason}
                                  onChange={(event) =>
                                    setFeedbackReasonDrafts((prev) => ({
                                      ...prev,
                                      [messageKey]: event.target
                                        .value as MessageFeedbackReason,
                                    }))
                                  }
                                  className="border border-[#cbd5d1] bg-white px-2 py-2 text-xs text-[#26312f]"
                                >
                                  {MESSAGE_FEEDBACK_REASON_OPTIONS.map(
                                    (option) => (
                                      <option
                                        key={option.value}
                                        value={option.value}
                                      >
                                        {option.label}
                                      </option>
                                    )
                                  )}
                                </select>
                                <input
                                  value={feedbackNote}
                                  onChange={(event) =>
                                    setFeedbackNoteDrafts((prev) => ({
                                      ...prev,
                                      [messageKey]: event.target.value,
                                    }))
                                  }
                                  maxLength={1000}
                                  placeholder="可选补充说明"
                                  className="border border-[#cbd5d1] bg-white px-2 py-2 text-xs text-[#26312f]"
                                />
                              </div>
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <p className="text-xs text-[#9b3c29]">
                                  {feedbackError}
                                </p>
                                <button
                                  type="button"
                                  disabled={isFeedbackSubmitting}
                                  onClick={() =>
                                    handleSubmitMessageFeedback({
                                      sessionId: currentSession.id,
                                      messageKey,
                                      messageId: message.id,
                                      rating: "negative",
                                      reason: feedbackReason,
                                      note: feedbackNote,
                                    })
                                  }
                                  className="font-utility border border-[#e36b4f] px-3 py-2 text-[10px] font-semibold uppercase text-[#9b3c29] transition hover:bg-[#fff1ed] disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                  {isFeedbackSubmitting ? "保存中" : "提交反馈"}
                                </button>
                              </div>
                            </div>
                          )}
                          {isAdvancedMode && !isFeedbackPanelOpen && feedbackError && (
                            <p className="mt-2 text-xs text-[#9b3c29]">
                              {feedbackError}
                            </p>
                          )}
                          {isAdvancedMode &&
                            !feedbackError &&
                            feedbackMessage &&
                            !messageFeedbackRating && (
                            <p className="mt-2 text-xs text-[#176b62]">
                              {feedbackMessage}
                            </p>
                          )}
                          {isAdvancedMode &&
                            isDevelopmentEnvironment &&
                            evalDraftError && (
                            <p className="mt-2 text-xs text-[#9b3c29]">
                              {evalDraftError}
                            </p>
                          )}
                        </div>
                      )}
                    </article>
                  </div>
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

          <div className="shrink-0 border-t border-[#cbd5d1] bg-[#eef3f0] px-5 py-5 md:px-8 md:py-6">
            <div className="flex items-center justify-between gap-4">
              <label
                htmlFor="question"
                className="font-utility block text-[10px] font-semibold uppercase text-[#176b62]"
              >
                Add To Research Log
              </label>
              <span className="font-utility text-[10px] text-[#7b8884]">
                Enter 发送 · Shift + Enter 换行
              </span>
            </div>
            <div className="mt-3 flex flex-col gap-3 md:flex-row md:items-end">
              <textarea
                id="question"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (
                    e.key === "Enter" &&
                    !e.shiftKey &&
                    !isCurrentSessionLoading
                  ) {
                    e.preventDefault();
                    void handleSubmit();
                  }
                }}
                placeholder="输入一个需要结合当前知识库回答的问题..."
                className="research-focus min-h-[104px] min-w-0 flex-1 resize-y border border-[#aebdb7] bg-[#fcfdfb] px-4 py-3 text-[#17201f]"
              />

              <button
                onClick={() => {
                  void handleSubmit();
                }}
                disabled={
                  isCurrentSessionLoading ||
                  isCreatingSession ||
                  !selectedKnowledgeBaseId ||
                  selectedKnowledgeBaseId === DEFAULT_KNOWLEDGE_BASE_ID
                }
                className="h-12 shrink-0 bg-[#176b62] px-6 text-sm font-semibold text-white transition hover:bg-[#105149] disabled:bg-[#91aaa4] md:h-[104px] md:w-32"
              >
                {isCreatingSession
                  ? "创建中..."
                  : isCurrentSessionLoading
                    ? "思考中..."
                    : "发送问题"}
              </button>
            </div>
          </div>
        </section>
      </div>

      {isKnowledgeBaseManagerOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-[#17201f]/55 px-4 py-8 backdrop-blur-[2px]"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setIsKnowledgeBaseManagerOpen(false);
            }
          }}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="knowledge-base-manager-title"
            className="research-paper max-h-full w-full max-w-lg overflow-y-auto border border-[#bdcac5]"
          >
            <div className="flex items-center justify-between border-b border-[#cbd5d1] px-6 py-5">
              <div>
                <p className="font-utility text-[10px] font-semibold uppercase text-[#176b62]">
                  Library Index
                </p>
                <h2
                  id="knowledge-base-manager-title"
                  className="font-display mt-2 text-2xl font-semibold text-[#17201f]"
                >
                  知识库管理
                </h2>
                <p className="mt-1 text-sm text-[#64716d]">
                  当前：{selectedKnowledgeBase?.name || "暂无知识库"}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsKnowledgeBaseManagerOpen(false)}
                aria-label="关闭知识库管理"
                className="flex h-9 w-9 items-center justify-center text-xl text-[#64716d] transition hover:bg-[#e1e9e5] hover:text-[#17201f]"
              >
                ×
              </button>
            </div>

            <div className="px-6 py-5">
              <div className="divide-y divide-[#d5ded9] border-y border-[#cbd5d1]">
                {knowledgeBases.map((knowledgeBase) => {
                  const localFileCount = knowledgeBaseFiles.filter(
                    (association) =>
                      association.knowledgeBaseId === knowledgeBase.id
                  ).length;
                  const fileCount =
                    localFileCount || knowledgeBase.fileCount || 0;
                  const conversationCount =
                    sessions.filter(
                      (session) =>
                        session.knowledgeBaseId === knowledgeBase.id
                    ).length;

                  return (
                    <button
                      key={knowledgeBase.id}
                      type="button"
                      onClick={() => {
                        setSelectedKnowledgeBaseId(knowledgeBase.id);
                        setIsKnowledgeBaseManagerOpen(false);
                      }}
                      className="flex w-full items-center justify-between gap-4 px-2 py-4 text-left transition hover:bg-[#eef3f0]"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="truncate text-sm font-semibold text-[#17201f]">
                            {knowledgeBase.name}
                          </p>
                          {knowledgeBase.isDefault && (
                            <span className="font-utility bg-[#e0ebe7] px-1.5 py-0.5 text-[10px] font-semibold text-[#176b62]">
                              默认
                            </span>
                          )}
                        </div>
                        <p className="mt-1 text-xs text-[#72807b]">
                          {fileCount} 个文件 · {conversationCount} 个会话
                        </p>
                      </div>
                      <span className="text-sm font-semibold text-[#176b62]">
                        选择
                      </span>
                    </button>
                  );
                })}
              </div>

              {isAdvancedMode && (
              <div className="mt-6 border border-[#cbd5d1] bg-[#f7faf8] px-4 py-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="font-utility text-[10px] font-semibold uppercase text-[#176b62]">
                      Retrieval Policy
                    </p>
                    <h3 className="mt-1 text-sm font-semibold text-[#17201f]">
                      当前知识库检索策略
                    </h3>
                    <p className="mt-1 text-xs leading-5 text-[#72807b]">
                      调整后会影响下一次聊天，不会重建已有向量。
                    </p>
                  </div>
                  {isLoadingRetrievalSettings && (
                    <span className="text-xs text-[#72807b]">读取中...</span>
                  )}
                </div>

                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  <label className="block text-xs font-semibold text-[#46514e]">
                    检索模式
                    <select
                      value={selectedRetrievalSettings.retrievalMode}
                      onChange={(event) =>
                        updateSelectedRetrievalSettings({
                          retrievalMode: event.target.value as RetrievalMode,
                        })
                      }
                      disabled={
                        !selectedKnowledgeBaseId ||
                        selectedKnowledgeBaseId === DEFAULT_KNOWLEDGE_BASE_ID
                      }
                      className="research-focus mt-1 w-full border border-[#b7c4bf] bg-white px-3 py-2 text-sm text-[#17201f]"
                    >
                      <option value="auto">自动判断</option>
                      <option value="always">强制检索</option>
                      <option value="never">永不检索</option>
                    </select>
                  </label>

                  <label className="block text-xs font-semibold text-[#46514e]">
                    引用阈值
                    <input
                      type="number"
                      step="0.1"
                      min="-20"
                      max="20"
                      value={selectedRetrievalSettings.rerankScoreThreshold}
                      onChange={(event) =>
                        updateSelectedRetrievalSettings({
                          rerankScoreThreshold: Number(event.target.value),
                        })
                      }
                      className="research-focus mt-1 w-full border border-[#b7c4bf] bg-white px-3 py-2 text-sm text-[#17201f]"
                    />
                  </label>

                  <label className="flex items-center gap-2 text-xs font-semibold text-[#46514e]">
                    <input
                      type="checkbox"
                      checked={selectedRetrievalSettings.enableQueryRouter}
                      onChange={(event) =>
                        updateSelectedRetrievalSettings({
                          enableQueryRouter: event.target.checked,
                        })
                      }
                      className="h-4 w-4 accent-[#176b62]"
                    />
                    启用 Query Router
                  </label>

                  <label className="flex items-center gap-2 text-xs font-semibold text-[#46514e]">
                    <input
                      type="checkbox"
                      checked={selectedRetrievalSettings.enableRerank}
                      onChange={(event) =>
                        updateSelectedRetrievalSettings({
                          enableRerank: event.target.checked,
                        })
                      }
                      className="h-4 w-4 accent-[#176b62]"
                    />
                    启用 Rerank 精排
                  </label>
                </div>

                <div className="mt-3 grid gap-3 md:grid-cols-4">
                  {[
                    ["topK", "最终引用", 1, 20],
                    ["vectorTopK", "Vector 召回", 1, 100],
                    ["fulltextTopK", "Fulltext 召回", 1, 100],
                    ["rrfK", "RRF 候选", 1, 100],
                  ].map(([field, label, min, max]) => (
                    <label
                      key={field}
                      className="block text-xs font-semibold text-[#46514e]"
                    >
                      {label}
                      <input
                        type="number"
                        min={min}
                        max={max}
                        value={
                          selectedRetrievalSettings[
                            field as keyof KnowledgeBaseRetrievalSettings
                          ] as number
                        }
                        onChange={(event) =>
                          updateSelectedRetrievalSettings({
                            [field]: Number(event.target.value),
                          } as Partial<KnowledgeBaseRetrievalSettings>)
                        }
                        className="research-focus mt-1 w-full border border-[#b7c4bf] bg-white px-2 py-2 text-sm text-[#17201f]"
                      />
                    </label>
                  ))}
                </div>

                {retrievalSettingsMessage && (
                  <p className="mt-3 border-l-4 border-[#176b62] bg-[#edf7f3] px-3 py-2 text-xs text-[#176b62]">
                    {retrievalSettingsMessage}
                  </p>
                )}

                {retrievalSettingsError && (
                  <p className="mt-3 border-l-4 border-[#e36b4f] bg-[#fff1ed] px-3 py-2 text-xs text-[#9b3c29]">
                    {retrievalSettingsError}
                  </p>
                )}

                <button
                  type="button"
                  onClick={() => {
                    void handleSaveRetrievalSettings();
                  }}
                  disabled={
                    !selectedKnowledgeBaseId ||
                    selectedKnowledgeBaseId === DEFAULT_KNOWLEDGE_BASE_ID ||
                    isSavingRetrievalSettings
                  }
                  className="mt-4 w-full bg-[#176b62] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#105149] disabled:bg-[#a7b8b2]"
                >
                  {isSavingRetrievalSettings ? "保存中..." : "保存检索设置"}
                </button>
              </div>
              )}

              <div className="mt-6">
                <label
                  htmlFor="new-knowledge-base-name"
                  className="font-utility block text-[10px] font-semibold uppercase text-[#72807b]"
                >
                  新建知识库
                </label>
                <div className="mt-2 flex gap-2">
                  <input
                    id="new-knowledge-base-name"
                    value={newKnowledgeBaseName}
                    onChange={(event) =>
                      setNewKnowledgeBaseName(event.target.value)
                    }
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        void handleCreateKnowledgeBase();
                      }
                    }}
                    placeholder="知识库名称"
                    className="research-focus min-w-0 flex-1 border border-[#b7c4bf] bg-white px-3 py-2.5 text-sm text-[#17201f]"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      void handleCreateKnowledgeBase();
                    }}
                    disabled={
                      !newKnowledgeBaseName.trim() ||
                      isCreatingKnowledgeBase
                    }
                    className="bg-[#176b62] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#105149] disabled:bg-[#a7b8b2]"
                  >
                    {isCreatingKnowledgeBase ? "创建中..." : "创建"}
                  </button>
                </div>
              </div>
            </div>
          </section>
        </div>
      )}

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
          detachingKnowledgeFileId={detachingKnowledgeFileId}
          attachingKnowledgeFileId={attachingKnowledgeFileId}
          knowledgeFileUploadError={knowledgeFileUploadError}
          knowledgeFileDetachError={knowledgeFileDetachError}
          knowledgeFileAttachError={knowledgeFileAttachError}
          knowledgeFileLoadError={knowledgeFileLoadError}
          reusableFileLoadError={reusableFileLoadError}
          vectorIndexMessage={vectorIndexMessage}
          vectorIndexError={vectorIndexError}
          onClose={() => setIsFileManagerOpen(false)}
          onUploadClick={() => fileInputRef.current?.click()}
          onIndexKnowledgeBase={handleIndexKnowledgeBase}
          onRefreshVectorHealth={loadVectorIndexHealth}
          onClearCompletedJobs={clearCompletedVectorIndexJobs}
          onIndexFile={handleIndexKnowledgeFile}
          onDeleteFileVectors={handleDeleteKnowledgeFileVectors}
          onRemoveFile={handleRemoveKnowledgeFile}
          onAttachFile={handleAttachKnowledgeFile}
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
