"use client";

import { type ReactNode, useEffect, useRef, useState } from "react";
import {
  AUTH_STORAGE_KEY,
  buildAuthorizationHeader,
  getAuthUsername,
  parseAuthState,
} from "@/lib/auth";

type Message = {
  role: "user" | "assistant";
  content: string;
};

type ChatSession = {
  id: string;
  title: string;
  messages: Message[];
  isPersisted: boolean;
};

type KnowledgeBase = {
  id: string;
  name: string;
  isDefault: boolean;
};

type KnowledgeFile = {
  id: string;
  knowledgeBaseId: string;
  name: string;
  size: number;
  status: "ready" | "processing";
};

type BackendConversation = {
  id?: unknown;
  title?: unknown;
  messages?: unknown;
};

type CreateConversationResponse = {
  conversation?: BackendConversation;
  id?: unknown;
  title?: unknown;
  answer?: string;
  detail?: string;
  error?: string;
  message?: string;
};

type ListConversationsResponse = {
  conversations?: unknown;
  answer?: string;
  detail?: string;
  error?: string;
  message?: string;
};

const STORAGE_KEY = "ai-learning-assistant-sessions";
const CURRENT_SESSION_KEY = "ai-learning-assistant-current-session";
const DEFAULT_KNOWLEDGE_BASE_ID = "default";
const LEGACY_INITIAL_MESSAGE =
  "你好，我是你的 AI 学习助手。你可以问我任何关于 AI 的问题。";

function createClientId() {
  return typeof crypto?.randomUUID === "function"
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function formatFileSize(size: number) {
  if (size < 1024) {
    return `${size} B`;
  }

  if (size < 1024 * 1024) {
    return `${Math.round(size / 1024)} KB`;
  }

  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function buildSessionTitle(input: string) {
  const normalized = input.replace(/\s+/g, " ").trim();

  if (!normalized) {
    return "新对话";
  }

  return normalized.length > 24 ? `${normalized.slice(0, 24)}...` : normalized;
}

function isMessage(value: unknown): value is Message {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const candidate = value as Partial<Message>;

  return (
    (candidate.role === "user" || candidate.role === "assistant") &&
    typeof candidate.content === "string"
  );
}

function getResponseErrorMessage(errorText: string, fallback: string) {
  const getStringValue = (value: unknown) =>
    typeof value === "string" && value.trim() ? value.trim() : "";

  try {
    const errorData = JSON.parse(errorText) as {
      answer?: unknown;
      detail?: unknown;
      error?: unknown;
      message?: unknown;
    };
    const directMessage =
      getStringValue(errorData.answer) ||
      getStringValue(errorData.detail) ||
      getStringValue(errorData.error) ||
      getStringValue(errorData.message);

    if (directMessage) {
      return directMessage;
    }

    if (Array.isArray(errorData.detail)) {
      const detailMessages = errorData.detail
        .map((detail) => {
          if (typeof detail === "string") {
            return detail;
          }

          if (typeof detail !== "object" || detail === null) {
            return "";
          }

          const candidate = detail as {
            loc?: unknown;
            msg?: unknown;
            type?: unknown;
          };
          const location = Array.isArray(candidate.loc)
            ? candidate.loc.join(".")
            : getStringValue(candidate.loc);
          const message = getStringValue(candidate.msg);
          const type = getStringValue(candidate.type);

          if (location && message) {
            return `${location}: ${message}`;
          }

          return message || type;
        })
        .filter(Boolean);

      if (detailMessages.length > 0) {
        return detailMessages.join("；");
      }
    }

    return fallback;
  } catch {
    return errorText.trim() || fallback;
  }
}

function getAssistantContent(value: unknown) {
  if (typeof value === "string") {
    return value;
  }

  if (typeof value !== "object" || value === null) {
    return "";
  }

  const candidate = value as {
    answer?: unknown;
    content?: unknown;
    assistant_message?: { content?: unknown };
    message?: { content?: unknown } | unknown;
    messages?: Array<{ role?: unknown; content?: unknown }>;
  };

  if (typeof candidate.assistant_message?.content === "string") {
    return candidate.assistant_message.content;
  }

  if (typeof candidate.answer === "string") {
    return candidate.answer;
  }

  if (typeof candidate.content === "string") {
    return candidate.content;
  }

  if (
    typeof candidate.message === "object" &&
    candidate.message !== null &&
    "content" in candidate.message &&
    typeof candidate.message.content === "string"
  ) {
    return candidate.message.content;
  }

  const assistantMessage = candidate.messages?.find(
    (message) =>
      message.role === "assistant" && typeof message.content === "string"
  );

  return typeof assistantMessage?.content === "string"
    ? assistantMessage.content
    : "";
}

function removeLegacyInitialMessage(messages: Message[]) {
  if (
    messages[0]?.role === "assistant" &&
    messages[0].content === LEGACY_INITIAL_MESSAGE
  ) {
    return messages.slice(1);
  }

  return messages;
}

function toChatSession(value: unknown): ChatSession | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }

  const conversation = value as BackendConversation;

  if (typeof conversation.id !== "string" || !conversation.id.trim()) {
    return null;
  }

  const messages = Array.isArray(conversation.messages)
    ? removeLegacyInitialMessage(conversation.messages.filter(isMessage))
    : [];

  return {
    id: conversation.id,
    title:
      typeof conversation.title === "string" && conversation.title.trim()
        ? conversation.title.trim()
        : "新对话",
    messages,
    isPersisted: true,
  };
}

function waitForNextPaint() {
  return new Promise<void>((resolve) => {
    requestAnimationFrame(() => resolve());
  });
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
  const [editingSessionId, setEditingSessionId] = useState("");
  const [editingTitle, setEditingTitle] = useState("");
  const [renamingSessionId, setRenamingSessionId] = useState("");
  const [deletingSessionId, setDeletingSessionId] = useState("");
  const [copiedMessageKey, setCopiedMessageKey] = useState("");
  const [loadingSessions, setLoadingSessions] = useState<Record<string, boolean>>(
    {}
  );
  const [sessionErrors, setSessionErrors] = useState<Record<string, string>>({});
  const [hasCheckedAuth, setHasCheckedAuth] = useState(false);
  const [isCreatingSession, setIsCreatingSession] = useState(false);
  const [pageError, setPageError] = useState("");
  const [currentUsername, setCurrentUsername] = useState("");
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([
    {
      id: DEFAULT_KNOWLEDGE_BASE_ID,
      name: "默认知识库",
      isDefault: true,
    },
  ]);
  const [selectedKnowledgeBaseId, setSelectedKnowledgeBaseId] = useState(
    DEFAULT_KNOWLEDGE_BASE_ID
  );
  const [knowledgeFiles, setKnowledgeFiles] = useState<KnowledgeFile[]>([]);
  const [isKnowledgeBaseManagerOpen, setIsKnowledgeBaseManagerOpen] =
    useState(false);
  const [isFileManagerOpen, setIsFileManagerOpen] = useState(false);
  const [newKnowledgeBaseName, setNewKnowledgeBaseName] = useState("");

  const bottomRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const previousSessionIdRef = useRef("");
  const previousMessageCountRef = useRef(0);
  const previousLoadingRef = useRef(false);

  const currentSession =
    sessions.find((session) => session.id === currentSessionId) || sessions[0] || null;
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
  const selectedKnowledgeBase =
    knowledgeBases.find(
      (knowledgeBase) => knowledgeBase.id === selectedKnowledgeBaseId
    ) || knowledgeBases[0];
  const selectedKnowledgeFiles = knowledgeFiles.filter(
    (file) => file.knowledgeBaseId === selectedKnowledgeBaseId
  );

  function handleCreateKnowledgeBase() {
    const normalizedName = newKnowledgeBaseName.trim();

    if (!normalizedName) {
      return;
    }

    const knowledgeBase: KnowledgeBase = {
      id: createClientId(),
      name: normalizedName,
      isDefault: false,
    };

    setKnowledgeBases((prev) => [...prev, knowledgeBase]);
    setSelectedKnowledgeBaseId(knowledgeBase.id);
    setNewKnowledgeBaseName("");
  }

  function handleSelectFiles(files: FileList | null) {
    if (!files?.length) {
      return;
    }

    const nextFiles = Array.from(files).map<KnowledgeFile>((file) => ({
      id: createClientId(),
      knowledgeBaseId: selectedKnowledgeBaseId,
      name: file.name,
      size: file.size,
      status: "ready",
    }));

    setKnowledgeFiles((prev) => [...nextFiles, ...prev]);
    setIsFileManagerOpen(true);

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  function handleRemoveKnowledgeFile(fileId: string) {
    setKnowledgeFiles((prev) => prev.filter((file) => file.id !== fileId));
  }

  async function createBackendSession(title = "新对话") {
    const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

    if (!authState) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      window.location.href = "/login";
      throw new Error("登录已失效，请重新登录。");
    }

    const response = await fetch("/api/chat/conversation", {
      method: "POST",
      headers: {
        Authorization: buildAuthorizationHeader(authState),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ title }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(
        getResponseErrorMessage(errorText, "创建对话失败，请稍后再试。")
      );
    }

    const data = (await response.json()) as CreateConversationResponse;
    const conversation = data.conversation || data;
    const conversationId = conversation.id;

    if (typeof conversationId !== "string" || !conversationId.trim()) {
      throw new Error("创建对话响应缺少 conversation.id。");
    }

    return {
      id: conversationId,
      title:
        typeof conversation.title === "string" && conversation.title.trim()
          ? conversation.title.trim()
          : title,
      messages: [],
      isPersisted: true,
    };
  }

  async function ensureBackendSession(session: ChatSession, title = session.title) {
    if (session.isPersisted) {
      return session;
    }

    const persistedSession = await createBackendSession(title);
    const nextSession = {
      ...persistedSession,
      title: persistedSession.title || title,
      messages: session.messages,
    };

    setSessions((prev) =>
      prev.map((candidate) =>
        candidate.id === session.id ? nextSession : candidate
      )
    );
    setCurrentSessionId(nextSession.id);

    return nextSession;
  }

  async function loadBackendSessions() {
    const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

    if (!authState) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      window.location.href = "/login";
      throw new Error("登录已失效，请重新登录。");
    }

    const response = await fetch("/api/chat/conversations", {
      method: "GET",
      headers: {
        Authorization: buildAuthorizationHeader(authState),
      },
      cache: "no-store",
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(
        getResponseErrorMessage(errorText, "读取会话列表失败，请稍后再试。")
      );
    }

    const data = (await response.json()) as ListConversationsResponse;
    const conversations = Array.isArray(data.conversations)
      ? data.conversations
      : [];

    return conversations
      .map(toChatSession)
      .filter((session): session is ChatSession => session !== null);
  }

  useEffect(() => {
    try {
      const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

      if (!authState) {
        localStorage.removeItem(AUTH_STORAGE_KEY);
        window.location.href = "/login";
        return;
      }

      setCurrentUsername(getAuthUsername(authState));
    } catch (error) {
      console.error("Failed to read auth state:", error);
      window.location.href = "/login";
      return;
    }

    setHasCheckedAuth(true);
  }, []);

  useEffect(() => {
    let isCancelled = false;

    async function restoreSessions() {
      let nextSessions: ChatSession[] = [];
      let didLoadSessions = false;

      try {
        nextSessions = await loadBackendSessions();
        didLoadSessions = true;
      } catch (error) {
        console.error("Failed to load saved sessions:", error);
        setPageError(
          error instanceof Error
            ? error.message
            : "读取会话列表失败，请稍后再试。"
        );
      }

      if (didLoadSessions && nextSessions.length === 0) {
        try {
          nextSessions = [await createBackendSession()];
        } catch (error) {
          console.error("Failed to create initial session:", error);
          setPageError(
            error instanceof Error
              ? error.message
              : "创建初始对话失败，请稍后再试。"
          );
        }
      }

      if (isCancelled) {
        return;
      }

      setSessions(nextSessions);
      setCurrentSessionId(nextSessions[0]?.id || "");
    }

    if (hasCheckedAuth) {
      void restoreSessions();
    }

    return () => {
      isCancelled = true;
    };
  }, [hasCheckedAuth]);

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
    localStorage.removeItem(AUTH_STORAGE_KEY);
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(CURRENT_SESSION_KEY);
    window.location.href = "/login";
  }

  async function handleCreateSession() {
    setIsCreatingSession(true);
    setPageError("");

    try {
      const newSession = await createBackendSession();

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

    const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

    if (!authState) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      window.location.href = "/login";
      return;
    }

    setDeletingSessionId(sessionId);
    setPageError("");

    try {
      const response = await fetch(
        `/api/chat/conversation/${encodeURIComponent(sessionId)}`,
        {
          method: "DELETE",
          headers: {
            Authorization: buildAuthorizationHeader(authState),
          },
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(
          getResponseErrorMessage(errorText, "删除会话失败，请稍后再试。")
        );
      }

      const remainingSessions = sessions.filter(
        (session) => session.id !== sessionId
      );

      setSessions(remainingSessions);
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

      if (remainingSessions.length === 0) {
        setCurrentSessionId("");
        setInput("");

        const newSession = await createBackendSession();
        setSessions([newSession]);
        setCurrentSessionId(newSession.id);
      } else if (currentSessionId === sessionId) {
        setCurrentSessionId(remainingSessions[0].id);
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
    const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

    if (!authState) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      window.location.href = "/login";
      return;
    }

    setRenamingSessionId(editingSessionId);
    setSessionErrors((prev) => ({
      ...prev,
      [editingSessionId]: "",
    }));

    try {
      const response = await fetch(
        `/api/chat/conversation/${encodeURIComponent(editingSessionId)}`,
        {
          method: "PATCH",
          headers: {
            Authorization: buildAuthorizationHeader(authState),
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            title: normalizedTitle,
          }),
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(
          getResponseErrorMessage(errorText, "重命名失败，请稍后再试。")
        );
      }

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
      await navigator.clipboard.writeText(content);
      setCopiedMessageKey(messageKey);

      window.setTimeout(() => {
        setCopiedMessageKey((current) =>
          current === messageKey ? "" : current
        );
      }, 1500);
    } catch (error) {
      console.error("Failed to copy message:", error);
    }
  }

  async function handleSubmit(overrideInput?: string) {
    if (!currentSession || isCurrentSessionLoading || isCreatingSession) {
      return;
    }

    const messageContent = (overrideInput ?? input).trim();

    if (!messageContent) {
      setSessionErrors((prev) => ({
        ...prev,
        [currentSession.id]: "请先在下方输入问题。",
      }));
      return;
    }

    const authState = parseAuthState(localStorage.getItem(AUTH_STORAGE_KEY));

    if (!authState) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      window.location.href = "/login";
      return;
    }

    let activeSession = currentSession;

    try {
      activeSession = await ensureBackendSession(
        currentSession,
        buildSessionTitle(messageContent)
      );
      setPageError("");
    } catch (error) {
      setPageError(
        error instanceof Error ? error.message : "创建对话失败，请稍后再试。"
      );
      return;
    }

    const userMessage: Message = {
      role: "user",
      content: messageContent,
    };

    const updatedMessages = [...activeSession.messages, userMessage];
    const activeSessionId = activeSession.id;

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

    const setAssistantFallback = (content: string) => {
      setSessions((prev) =>
        prev.map((session) => {
          if (session.id !== activeSessionId) {
            return session;
          }

          const messages = [...session.messages];
          const lastMessage = messages[messages.length - 1];

          if (lastMessage?.role === "assistant" && !lastMessage.content) {
            messages[messages.length - 1] = {
              ...lastMessage,
              content,
            };
          }

          return {
            ...session,
            messages,
          };
        })
      );
    };

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          Authorization: buildAuthorizationHeader(authState),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          conversation_id: activeSessionId,
          message: messageContent,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        const errorMessage = getResponseErrorMessage(
          errorText,
          "请求失败了，请稍后再试。"
        );

        setSessionErrors((prev) => ({
          ...prev,
          [activeSessionId]: errorMessage,
        }));
        return;
      }

      appendAssistantContent("");

      const contentType = response.headers.get("Content-Type") || "";

      if (contentType.includes("application/json")) {
        const data = (await response.json()) as unknown;
        const answer = getAssistantContent(data);

        setAssistantFallback(answer || "模型暂时没有返回内容。");
        return;
      }

      if (!response.body) {
        const answer = await response.text();
        setAssistantFallback(answer || "模型暂时没有返回内容。");
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let streamedAnswer = "";

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          break;
        }

        const chunk = decoder.decode(value, { stream: true });

        if (chunk) {
          streamedAnswer += chunk;
          appendAssistantContent(chunk);
          await waitForNextPaint();
        }
      }

      const finalChunk = decoder.decode();

      if (finalChunk) {
        streamedAnswer += finalChunk;
        appendAssistantContent(finalChunk);
        await waitForNextPaint();
      }

      if (!streamedAnswer) {
        setAssistantFallback("模型暂时没有返回内容。");
      }
    } catch (error) {
      console.error(error);
      setSessionErrors((prev) => ({
        ...prev,
        [activeSessionId]: "请求失败了，请稍后再试。",
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
          正在整理研究台...
        </div>
      </main>
    );
  }

  return (
    <main className="research-canvas min-h-screen px-3 py-3 md:px-5 md:py-5">
      <div className="mx-auto grid min-w-0 w-full max-w-[1440px] gap-4 lg:grid-cols-[304px_minmax(0,1fr)]">
        <aside className="research-enter flex min-w-0 max-h-[calc(100vh-1.5rem)] flex-col border border-[#bdcac5] bg-[#edf2ef] p-4 lg:sticky lg:top-5 lg:h-[calc(100vh-2.5rem)] lg:max-h-none">
          <div className="flex items-center justify-between gap-3 border-b border-[#c7d1cd] px-1 pb-4">
            <div className="min-w-0">
              <p className="font-utility text-[10px] font-semibold uppercase text-[#72807b]">
                Researcher
              </p>
              <p className="font-display mt-1 truncate text-lg font-semibold text-[#17201f]">
                {currentUsername || "已登录"}
              </p>
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
                className="bg-[#176b62] px-3 py-2.5 text-xs font-semibold text-white transition hover:bg-[#105149]"
              >
                上传文件
              </button>
              <button
                type="button"
                onClick={() => setIsFileManagerOpen(true)}
                className="border border-[#aebdb7] bg-[#fcfdfb] px-3 py-2.5 text-xs font-semibold text-[#46514e] transition hover:border-[#176b62] hover:text-[#176b62]"
              >
                文件 {selectedKnowledgeFiles.length}
              </button>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".txt,.md,.csv,.json,.pdf,.png,.jpg,.jpeg,.webp,.gif"
              onChange={(event) => handleSelectFiles(event.target.files)}
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
              {String(sessions.length).padStart(2, "0")}
            </p>
          </div>

          <div className="mt-2 min-h-0 min-w-0 flex-1 space-y-2 overflow-y-auto pr-1">
            {sessions.map((session) => {
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
                            setCurrentSessionId(session.id);
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

        <section className="research-paper research-enter min-w-0 border border-[#bdcac5]">
          <header className="border-b border-[#cbd5d1] px-5 py-5 md:px-8 md:py-6">
            <div className="flex flex-col justify-between gap-5 md:flex-row md:items-end">
              <div className="min-w-0">
                <div className="flex items-center gap-3">
                  <span className="font-utility bg-[#d5a83b] px-2 py-1 text-[10px] font-bold uppercase text-[#17201f]">
                    Live Research
                  </span>
                  <span className="font-utility text-[10px] font-semibold uppercase text-[#72807b]">
                    {selectedKnowledgeBase?.name || "默认知识库"}
                  </span>
                </div>
                <h1 className="font-display mt-4 truncate text-3xl font-semibold text-[#17201f] md:text-4xl">
                  {currentSession?.title || "研究工作台"}
                </h1>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-[#64716d]">
                  基于当前知识库继续提问，回答与上下文会保存在此会话中。
                </p>
              </div>
              <div className="font-utility flex shrink-0 gap-5 border-t border-[#d6dedb] pt-4 text-[10px] uppercase text-[#72807b] md:border-l md:border-t-0 md:pl-5 md:pt-0">
                <span>
                  Messages
                  <strong className="mt-1 block text-base text-[#17201f]">
                    {String(currentSession?.messages.length || 0).padStart(2, "0")}
                  </strong>
                </span>
                <span>
                  Files
                  <strong className="mt-1 block text-base text-[#17201f]">
                    {String(selectedKnowledgeFiles.length).padStart(2, "0")}
                  </strong>
                </span>
              </div>
            </div>
          </header>

          <div className="px-5 py-7 md:px-8 md:py-9">
            <div className="space-y-6">
              {currentSession?.messages.length === 0 && (
                <div className="border-y border-[#cbd5d1] py-12 text-center">
                  <p className="font-utility text-[10px] font-semibold uppercase text-[#176b62]">
                    Empty Research Log
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
                const isStreamingPlaceholder =
                  message.role === "assistant" &&
                  index === currentSession.messages.length - 1 &&
                  isCurrentSessionLoading &&
                  !message.content;

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
                      {message.role === "user" ? "Question" : "Response"}
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

                      {message.role === "assistant" && message.content && (
                        <div className="mt-4 flex justify-end border-t border-[#d6dedb] pt-3">
                          <button
                            onClick={() =>
                              handleCopyMessage(messageKey, message.content)
                            }
                            className="font-utility text-[10px] font-semibold uppercase text-[#64716d] transition hover:text-[#176b62]"
                          >
                            {copiedMessageKey === messageKey
                              ? "Copied"
                              : "Copy Response"}
                          </button>
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

          <div className="border-t border-[#cbd5d1] bg-[#eef3f0] px-5 py-5 md:px-8 md:py-6">
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
                  isCurrentSessionLoading || isCreatingSession || !currentSession
                }
                className="h-12 shrink-0 bg-[#176b62] px-6 text-sm font-semibold text-white transition hover:bg-[#105149] disabled:bg-[#91aaa4] md:h-[104px] md:w-32"
              >
                {isCurrentSessionLoading ? "思考中..." : "发送问题"}
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
                  当前：{selectedKnowledgeBase?.name || "默认知识库"}
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
                  const fileCount = knowledgeFiles.filter(
                    (file) => file.knowledgeBaseId === knowledgeBase.id
                  ).length;
                  const conversationCount =
                    knowledgeBase.id === DEFAULT_KNOWLEDGE_BASE_ID
                      ? sessions.length
                      : 0;

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
                        handleCreateKnowledgeBase();
                      }
                    }}
                    placeholder="知识库名称"
                    className="research-focus min-w-0 flex-1 border border-[#b7c4bf] bg-white px-3 py-2.5 text-sm text-[#17201f]"
                  />
                  <button
                    type="button"
                    onClick={handleCreateKnowledgeBase}
                    disabled={!newKnowledgeBaseName.trim()}
                    className="bg-[#176b62] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#105149] disabled:bg-[#a7b8b2]"
                  >
                    创建
                  </button>
                </div>
              </div>
            </div>
          </section>
        </div>
      )}

      {isFileManagerOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-[#17201f]/55 px-4 py-8 backdrop-blur-[2px]"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setIsFileManagerOpen(false);
            }
          }}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="file-manager-title"
            className="research-paper max-h-full w-full max-w-xl overflow-y-auto border border-[#bdcac5]"
          >
            <div className="flex items-center justify-between border-b border-[#cbd5d1] px-6 py-5">
              <div>
                <p className="font-utility text-[10px] font-semibold uppercase text-[#176b62]">
                  Source Material
                </p>
                <h2
                  id="file-manager-title"
                  className="font-display mt-2 text-2xl font-semibold text-[#17201f]"
                >
                  知识库文件
                </h2>
                <p className="mt-1 text-sm text-[#64716d]">
                  {selectedKnowledgeBase?.name || "默认知识库"}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsFileManagerOpen(false)}
                aria-label="关闭文件管理"
                className="flex h-9 w-9 items-center justify-center text-xl text-[#64716d] transition hover:bg-[#e1e9e5] hover:text-[#17201f]"
              >
                ×
              </button>
            </div>

            <div className="px-6 py-5">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="w-full border border-dashed border-[#9bada6] bg-[#eef3f0] px-4 py-5 text-sm font-semibold text-[#46514e] transition hover:border-[#176b62] hover:text-[#176b62]"
              >
                选择文件上传
              </button>

              <div className="mt-5 divide-y divide-[#d5ded9] border-y border-[#cbd5d1]">
                {selectedKnowledgeFiles.length > 0 ? (
                  selectedKnowledgeFiles.map((file) => (
                    <div
                      key={file.id}
                      className="flex items-center justify-between gap-4 py-4"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-[#17201f]">
                          {file.name}
                        </p>
                        <p className="mt-1 text-xs text-[#72807b]">
                          {formatFileSize(file.size)} ·{" "}
                          {file.status === "processing" ? "处理中" : "已选择"}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRemoveKnowledgeFile(file.id)}
                        className="shrink-0 px-2 py-1 text-xs font-semibold text-[#72807b] transition hover:bg-[#fff1ed] hover:text-[#9b3c29]"
                      >
                        移除
                      </button>
                    </div>
                  ))
                ) : (
                  <p className="py-8 text-center text-sm text-[#72807b]">
                    暂无文件
                  </p>
                )}
              </div>
            </div>
          </section>
        </div>
      )}

      <button
        onClick={() => {
          window.scrollTo({ top: 0, behavior: "smooth" });
        }}
        className="font-utility fixed bottom-5 right-5 border border-[#9bada6] bg-[#fcfdfb] px-3 py-2 text-[10px] font-semibold uppercase text-[#46514e] shadow-sm transition hover:border-[#176b62] hover:text-[#176b62]"
      >
        Top ↑
      </button>
    </main>
  );
}
