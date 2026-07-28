"use client";

import type { RefObject } from "react";
import type { KnowledgeBase } from "../../lib/chat-workspace/types";

export type KnowledgeBaseSidebarControlsProps = {
  knowledgeBases: KnowledgeBase[];
  selectedKnowledgeBaseId: string;
  selectedFileCount: number;
  isUploadingFiles: boolean;
  uploadRetryAfterSeconds: number;
  fileInputRef: RefObject<HTMLInputElement | null>;
  onSelectedKnowledgeBaseChange: (knowledgeBaseId: string) => void;
  onOpenKnowledgeBaseManager: () => void;
  onOpenFileManager: () => void | Promise<void>;
  onFilesSelected: (files: FileList | null) => void | Promise<void>;
};

/**
 * 展示知识库选择、管理入口和知识文件操作。
 *
 * 知识库与文件请求、异步状态和限流倒计时由页面层管理，组件只负责渲染并转发操作。
 */
export function KnowledgeBaseSidebarControls({
  knowledgeBases,
  selectedKnowledgeBaseId,
  selectedFileCount,
  isUploadingFiles,
  uploadRetryAfterSeconds,
  fileInputRef,
  onSelectedKnowledgeBaseChange,
  onOpenKnowledgeBaseManager,
  onOpenFileManager,
  onFilesSelected,
}: KnowledgeBaseSidebarControlsProps) {
  return (
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
          onClick={onOpenKnowledgeBaseManager}
          className="text-xs font-semibold text-[#176b62] underline decoration-[#d5a83b] decoration-2 underline-offset-4"
        >
          管理
        </button>
      </div>

      <select
        id="knowledge-base"
        value={selectedKnowledgeBaseId}
        onChange={(event) =>
          onSelectedKnowledgeBaseChange(event.target.value)
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
            !selectedKnowledgeBaseId ||
            isUploadingFiles ||
            uploadRetryAfterSeconds > 0
          }
          className="bg-[#176b62] px-3 py-2.5 text-xs font-semibold text-white transition hover:bg-[#105149] disabled:bg-[#91aaa4]"
        >
          {uploadRetryAfterSeconds > 0
            ? `${uploadRetryAfterSeconds} 秒后重试`
            : isUploadingFiles
              ? "上传中..."
              : "上传文件"}
        </button>
        <button
          type="button"
          onClick={() => {
            void onOpenFileManager();
          }}
          className="border border-[#aebdb7] bg-[#fcfdfb] px-3 py-2.5 text-xs font-semibold text-[#46514e] transition hover:border-[#176b62] hover:text-[#176b62]"
        >
          文件 {selectedFileCount}
        </button>
      </div>
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".pdf,.docx,.md,.txt,.png,.jpg,.jpeg,.webp"
        onChange={(event) => {
          void onFilesSelected(event.target.files);
        }}
        className="hidden"
      />
    </div>
  );
}
