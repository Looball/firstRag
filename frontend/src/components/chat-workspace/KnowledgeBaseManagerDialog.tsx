"use client";

import { useMemo } from "react";
import { DEFAULT_KNOWLEDGE_BASE_ID } from "../../lib/chat-workspace/constants";
import type {
  ChatSession,
  DeletedKnowledgeBase,
  KnowledgeBase,
  KnowledgeBaseFile,
  KnowledgeBaseRetrievalSettings,
  RetrievalMode,
} from "../../lib/chat-workspace/types";

type NumericRetrievalSetting =
  | "topK"
  | "vectorTopK"
  | "fulltextTopK"
  | "rrfK";

const RETRIEVAL_NUMBER_FIELDS: ReadonlyArray<{
  field: NumericRetrievalSetting;
  label: string;
  min: number;
  max: number;
}> = [
  { field: "topK", label: "最终引用", min: 1, max: 20 },
  { field: "vectorTopK", label: "Vector 召回", min: 1, max: 100 },
  { field: "fulltextTopK", label: "Fulltext 召回", min: 1, max: 100 },
  { field: "rrfK", label: "RRF 候选", min: 1, max: 100 },
];

export type KnowledgeBaseManagerDialogProps = {
  selectedKnowledgeBaseName: string;
  selectedKnowledgeBaseId: string;
  knowledgeBases: KnowledgeBase[];
  knowledgeBaseFiles: KnowledgeBaseFile[];
  sessions: ChatSession[];
  deletedKnowledgeBases: DeletedKnowledgeBase[];
  isLoadingDeletedKnowledgeBases: boolean;
  knowledgeBaseLifecycleMessage: string;
  knowledgeBaseLifecycleError: string;
  editingKnowledgeBaseId: string;
  editingKnowledgeBaseName: string;
  renamingKnowledgeBaseId: string;
  deletingKnowledgeBaseId: string;
  restoringKnowledgeBaseId: string;
  isAdvancedMode: boolean;
  selectedRetrievalSettings: KnowledgeBaseRetrievalSettings;
  isLoadingRetrievalSettings: boolean;
  isSavingRetrievalSettings: boolean;
  retrievalSettingsMessage: string;
  retrievalSettingsError: string;
  newKnowledgeBaseName: string;
  isCreatingKnowledgeBase: boolean;
  onClose: () => void;
  onSelectKnowledgeBase: (knowledgeBaseId: string) => void;
  onStartRename: (knowledgeBase: KnowledgeBase) => void;
  onEditingNameChange: (name: string) => void;
  onCancelRename: () => void;
  onSaveRename: () => void | Promise<void>;
  onDeleteKnowledgeBase: (
    knowledgeBase: KnowledgeBase,
  ) => void | Promise<void>;
  onRestoreKnowledgeBase: (knowledgeBaseId: string) => void | Promise<void>;
  onUpdateRetrievalSettings: (
    patch: Partial<KnowledgeBaseRetrievalSettings>,
  ) => void;
  onSaveRetrievalSettings: () => void | Promise<void>;
  onNewKnowledgeBaseNameChange: (name: string) => void;
  onCreateKnowledgeBase: () => void | Promise<void>;
};

/**
 * 展示知识库列表、回收站、检索设置和新建表单。
 *
 * 生命周期请求和局部状态由 useKnowledgeBaseLifecycle 管理；
 * retrieval settings 与文件数据保持各自独立边界。
 */
export function KnowledgeBaseManagerDialog({
  selectedKnowledgeBaseName,
  selectedKnowledgeBaseId,
  knowledgeBases,
  knowledgeBaseFiles,
  sessions,
  deletedKnowledgeBases,
  isLoadingDeletedKnowledgeBases,
  knowledgeBaseLifecycleMessage,
  knowledgeBaseLifecycleError,
  editingKnowledgeBaseId,
  editingKnowledgeBaseName,
  renamingKnowledgeBaseId,
  deletingKnowledgeBaseId,
  restoringKnowledgeBaseId,
  isAdvancedMode,
  selectedRetrievalSettings,
  isLoadingRetrievalSettings,
  isSavingRetrievalSettings,
  retrievalSettingsMessage,
  retrievalSettingsError,
  newKnowledgeBaseName,
  isCreatingKnowledgeBase,
  onClose,
  onSelectKnowledgeBase,
  onStartRename,
  onEditingNameChange,
  onCancelRename,
  onSaveRename,
  onDeleteKnowledgeBase,
  onRestoreKnowledgeBase,
  onUpdateRetrievalSettings,
  onSaveRetrievalSettings,
  onNewKnowledgeBaseNameChange,
  onCreateKnowledgeBase,
}: KnowledgeBaseManagerDialogProps) {
  const localFileCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const association of knowledgeBaseFiles) {
      counts.set(
        association.knowledgeBaseId,
        (counts.get(association.knowledgeBaseId) || 0) + 1,
      );
    }
    return counts;
  }, [knowledgeBaseFiles]);

  const conversationCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const session of sessions) {
      counts.set(
        session.knowledgeBaseId,
        (counts.get(session.knowledgeBaseId) || 0) + 1,
      );
    }
    return counts;
  }, [sessions]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#17201f]/55 px-4 py-8 backdrop-blur-[2px]"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
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
              当前：{selectedKnowledgeBaseName || "暂无知识库"}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭知识库管理"
            className="flex h-9 w-9 items-center justify-center text-xl text-[#64716d] transition hover:bg-[#e1e9e5] hover:text-[#17201f]"
          >
            ×
          </button>
        </div>

        <div className="px-6 py-5">
          {knowledgeBaseLifecycleMessage ? (
            <p className="mb-4 border-l-4 border-[#176b62] bg-[#edf7f3] px-3 py-2 text-xs text-[#176b62]">
              {knowledgeBaseLifecycleMessage}
            </p>
          ) : null}
          {knowledgeBaseLifecycleError ? (
            <p className="mb-4 border-l-4 border-[#e36b4f] bg-[#fff1ed] px-3 py-2 text-xs text-[#9b3c29]">
              {knowledgeBaseLifecycleError}
            </p>
          ) : null}

          <div className="divide-y divide-[#d5ded9] border-y border-[#cbd5d1]">
            {knowledgeBases.map((knowledgeBase) => {
              const localFileCount =
                localFileCounts.get(knowledgeBase.id) || 0;
              const fileCount =
                localFileCount || knowledgeBase.fileCount || 0;
              const conversationCount =
                conversationCounts.get(knowledgeBase.id) || 0;
              const isEditing =
                editingKnowledgeBaseId === knowledgeBase.id;

              return (
                <div key={knowledgeBase.id} className="px-2 py-4">
                  {isEditing ? (
                    <div className="flex flex-wrap items-center gap-2">
                      <input
                        value={editingKnowledgeBaseName}
                        onChange={(event) =>
                          onEditingNameChange(event.target.value)
                        }
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            event.preventDefault();
                            void onSaveRename();
                          }
                        }}
                        className="research-focus min-w-0 flex-1 border border-[#b7c4bf] bg-white px-3 py-2 text-sm text-[#17201f]"
                        aria-label={`重命名 ${knowledgeBase.name}`}
                      />
                      <button
                        type="button"
                        onClick={() => void onSaveRename()}
                        disabled={
                          !editingKnowledgeBaseName.trim() ||
                          renamingKnowledgeBaseId === knowledgeBase.id
                        }
                        className="bg-[#176b62] px-3 py-2 text-xs font-semibold text-white disabled:bg-[#a7b8b2]"
                      >
                        {renamingKnowledgeBaseId === knowledgeBase.id
                          ? "保存中..."
                          : "保存"}
                      </button>
                      <button
                        type="button"
                        onClick={onCancelRename}
                        className="px-2 py-2 text-xs font-semibold text-[#64716d]"
                      >
                        取消
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center justify-between gap-4">
                      <button
                        type="button"
                        onClick={() => {
                          onSelectKnowledgeBase(knowledgeBase.id);
                          onClose();
                        }}
                        className="min-w-0 flex-1 text-left"
                      >
                        <div className="flex items-center gap-2">
                          <p className="truncate text-sm font-semibold text-[#17201f]">
                            {knowledgeBase.name}
                          </p>
                          {knowledgeBase.isDefault ? (
                            <span className="font-utility bg-[#e0ebe7] px-1.5 py-0.5 text-[10px] font-semibold text-[#176b62]">
                              默认
                            </span>
                          ) : null}
                        </div>
                        <p className="mt-1 text-xs text-[#72807b]">
                          {fileCount} 个文件 · {conversationCount} 个会话
                        </p>
                      </button>
                      <div className="flex shrink-0 items-center gap-2">
                        <button
                          type="button"
                          onClick={() => onStartRename(knowledgeBase)}
                          className="px-2 py-1 text-xs font-semibold text-[#64716d] hover:bg-[#eef3f0] hover:text-[#176b62]"
                        >
                          重命名
                        </button>
                        {!knowledgeBase.isDefault ? (
                          <button
                            type="button"
                            onClick={() =>
                              void onDeleteKnowledgeBase(knowledgeBase)
                            }
                            disabled={
                              deletingKnowledgeBaseId === knowledgeBase.id
                            }
                            className="px-2 py-1 text-xs font-semibold text-[#9b3c29] hover:bg-[#fff1ed] disabled:text-[#aab3b0]"
                          >
                            {deletingKnowledgeBaseId === knowledgeBase.id
                              ? "删除中..."
                              : "删除"}
                          </button>
                        ) : null}
                        <button
                          type="button"
                          onClick={() => {
                            onSelectKnowledgeBase(knowledgeBase.id);
                            onClose();
                          }}
                          className="px-2 py-1 text-xs font-semibold text-[#176b62] hover:bg-[#e4f0ec]"
                        >
                          选择
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="mt-6">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="font-utility text-[10px] font-semibold uppercase text-[#72807b]">
                  Trash
                </p>
                <h3 className="mt-1 text-sm font-semibold text-[#17201f]">
                  知识库回收站
                </h3>
              </div>
              <span className="text-xs text-[#72807b]">
                {isLoadingDeletedKnowledgeBases
                  ? "读取中..."
                  : `${deletedKnowledgeBases.length} 项`}
              </span>
            </div>
            <div className="mt-2 divide-y divide-[#e0e7e3] border-y border-[#d5ded9]">
              {!isLoadingDeletedKnowledgeBases &&
              deletedKnowledgeBases.length === 0 ? (
                <p className="py-5 text-center text-xs text-[#8a9692]">
                  回收站为空
                </p>
              ) : null}
              {deletedKnowledgeBases.map((knowledgeBase) => (
                <div
                  key={knowledgeBase.id}
                  className="flex items-center justify-between gap-4 px-2 py-3"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-[#46514e]">
                      {knowledgeBase.name}
                    </p>
                    <p className="mt-1 text-xs text-[#8a9692]">
                      {knowledgeBase.fileCount} 个文件 ·{" "}
                      {knowledgeBase.conversationCount} 个会话
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      void onRestoreKnowledgeBase(knowledgeBase.id)
                    }
                    disabled={
                      restoringKnowledgeBaseId === knowledgeBase.id
                    }
                    className="shrink-0 border border-[#176b62] px-3 py-1.5 text-xs font-semibold text-[#176b62] hover:bg-[#e4f0ec] disabled:border-[#aab3b0] disabled:text-[#aab3b0]"
                  >
                    {restoringKnowledgeBaseId === knowledgeBase.id
                      ? "恢复中..."
                      : "恢复"}
                  </button>
                </div>
              ))}
            </div>
          </div>

          {isAdvancedMode ? (
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
                {isLoadingRetrievalSettings ? (
                  <span className="text-xs text-[#72807b]">读取中...</span>
                ) : null}
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <label className="block text-xs font-semibold text-[#46514e]">
                  检索模式
                  <select
                    value={selectedRetrievalSettings.retrievalMode}
                    onChange={(event) =>
                      onUpdateRetrievalSettings({
                        retrievalMode: event.target.value as RetrievalMode,
                      })
                    }
                    disabled={
                      !selectedKnowledgeBaseId ||
                      selectedKnowledgeBaseId ===
                        DEFAULT_KNOWLEDGE_BASE_ID
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
                    value={
                      selectedRetrievalSettings.rerankScoreThreshold
                    }
                    onChange={(event) =>
                      onUpdateRetrievalSettings({
                        rerankScoreThreshold: Number(event.target.value),
                      })
                    }
                    className="research-focus mt-1 w-full border border-[#b7c4bf] bg-white px-3 py-2 text-sm text-[#17201f]"
                  />
                </label>

                <label className="flex items-center gap-2 text-xs font-semibold text-[#46514e]">
                  <input
                    type="checkbox"
                    checked={
                      selectedRetrievalSettings.enableQueryRouter
                    }
                    onChange={(event) =>
                      onUpdateRetrievalSettings({
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
                      onUpdateRetrievalSettings({
                        enableRerank: event.target.checked,
                      })
                    }
                    className="h-4 w-4 accent-[#176b62]"
                  />
                  启用 Rerank 精排
                </label>
              </div>

              <div className="mt-3 grid gap-3 md:grid-cols-4">
                {RETRIEVAL_NUMBER_FIELDS.map(
                  ({ field, label, min, max }) => (
                    <label
                      key={field}
                      className="block text-xs font-semibold text-[#46514e]"
                    >
                      {label}
                      <input
                        type="number"
                        min={min}
                        max={max}
                        value={selectedRetrievalSettings[field]}
                        onChange={(event) =>
                          onUpdateRetrievalSettings({
                            [field]: Number(event.target.value),
                          })
                        }
                        className="research-focus mt-1 w-full border border-[#b7c4bf] bg-white px-2 py-2 text-sm text-[#17201f]"
                      />
                    </label>
                  ),
                )}
              </div>

              {retrievalSettingsMessage ? (
                <p className="mt-3 border-l-4 border-[#176b62] bg-[#edf7f3] px-3 py-2 text-xs text-[#176b62]">
                  {retrievalSettingsMessage}
                </p>
              ) : null}

              {retrievalSettingsError ? (
                <p className="mt-3 border-l-4 border-[#e36b4f] bg-[#fff1ed] px-3 py-2 text-xs text-[#9b3c29]">
                  {retrievalSettingsError}
                </p>
              ) : null}

              <button
                type="button"
                onClick={() => void onSaveRetrievalSettings()}
                disabled={
                  !selectedKnowledgeBaseId ||
                  selectedKnowledgeBaseId ===
                    DEFAULT_KNOWLEDGE_BASE_ID ||
                  isSavingRetrievalSettings
                }
                className="mt-4 w-full bg-[#176b62] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#105149] disabled:bg-[#a7b8b2]"
              >
                {isSavingRetrievalSettings ? "保存中..." : "保存检索设置"}
              </button>
            </div>
          ) : null}

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
                  onNewKnowledgeBaseNameChange(event.target.value)
                }
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    void onCreateKnowledgeBase();
                  }
                }}
                placeholder="知识库名称"
                className="research-focus min-w-0 flex-1 border border-[#b7c4bf] bg-white px-3 py-2.5 text-sm text-[#17201f]"
              />
              <button
                type="button"
                onClick={() => void onCreateKnowledgeBase()}
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
  );
}
