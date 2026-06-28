import type { KnowledgeBaseRetrievalSettings } from "./types";

export const STORAGE_KEY = "ai-learning-assistant-sessions";
export const CURRENT_SESSION_KEY = "ai-learning-assistant-current-session";
export const DEFAULT_KNOWLEDGE_BASE_ID = "default";
export const DEFAULT_RETRIEVAL_SETTINGS: KnowledgeBaseRetrievalSettings = {
  retrievalMode: "auto",
  enableQueryRouter: true,
  enableRerank: true,
  topK: 5,
  vectorTopK: 20,
  fulltextTopK: 20,
  rrfK: 10,
  rerankScoreThreshold: 0,
};
export const LEGACY_INITIAL_MESSAGE =
  "你好，我是你的 AI 学习助手。你可以问我任何关于 AI 的问题。";
