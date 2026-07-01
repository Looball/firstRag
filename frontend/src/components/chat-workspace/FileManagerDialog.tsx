import { TaskQueuePanel } from "@/components/chat-workspace/TaskQueuePanel";
import type { ReactNode } from "react";
import type {
  KnowledgeFile,
  VectorIndexHealthResponse,
  VectorIndexQueueItem,
} from "@/lib/chat-workspace/types";
import { formatFileSize, getVectorStatus } from "@/lib/chat-workspace/utils";

type FileManagerDialogProps = {
  knowledgeBaseName: string;
  selectedKnowledgeBaseId: string;
  selectedFiles: KnowledgeFile[];
  reusableFiles: KnowledgeFile[];
  vectorIndexingFileIds: Record<string, boolean>;
  vectorIndexQueue: VectorIndexQueueItem[];
  vectorIndexHealth: VectorIndexHealthResponse | null;
  vectorIndexHealthError: string;
  isLoadingVectorIndexHealth: boolean;
  isUploadingKnowledgeFiles: boolean;
  isIndexingKnowledgeBase: boolean;
  isLoadingKnowledgeFiles: boolean;
  isLoadingReusableFiles: boolean;
  deletingVectorFileId: string;
  detachingKnowledgeFileId: string;
  attachingKnowledgeFileId: string;
  knowledgeFileUploadError: string;
  knowledgeFileDetachError: string;
  knowledgeFileAttachError: string;
  knowledgeFileLoadError: string;
  reusableFileLoadError: string;
  vectorIndexMessage: string;
  vectorIndexError: string;
  onClose: () => void;
  onUploadClick: () => void;
  onIndexKnowledgeBase: () => void | Promise<void>;
  onRefreshVectorHealth: () => void | Promise<void>;
  onClearCompletedJobs: () => void;
  onIndexFile: (fileId: string) => void | Promise<void>;
  onDeleteFileVectors: (fileId: string) => void | Promise<void>;
  onRemoveFile: (fileId: string) => void | Promise<void>;
  onAttachFile: (fileId: string) => void | Promise<void>;
};

type KnowledgeFileListProps = {
  title: string;
  titleTone: "primary" | "muted";
  files: KnowledgeFile[];
  emptyState: ReactNode;
  loadingLabel: string;
  isLoading: boolean;
  mode: "selected" | "reusable";
  vectorIndexingFileIds: Record<string, boolean>;
  isIndexingKnowledgeBase: boolean;
  deletingVectorFileId: string;
  detachingKnowledgeFileId: string;
  attachingKnowledgeFileId: string;
  onIndexFile: (fileId: string) => void | Promise<void>;
  onDeleteFileVectors: (fileId: string) => void | Promise<void>;
  onRemoveFile: (fileId: string) => void | Promise<void>;
  onAttachFile: (fileId: string) => void | Promise<void>;
};

function StatusMessage({
  children,
  tone,
}: {
  children: ReactNode;
  tone: "success" | "danger";
}) {
  const toneClass =
    tone === "success"
      ? "border-[#176b62] bg-[#edf7f3] text-[#176b62]"
      : "border-[#e36b4f] bg-[#fff1ed] text-[#9b3c29]";

  return (
    <p
      role={tone === "danger" ? "alert" : undefined}
      className={`mt-3 border-l-4 px-4 py-3 text-sm ${toneClass}`}
    >
      {children}
    </p>
  );
}

function KnowledgeFileRow({
  file,
  mode,
  isFileIndexing,
  isIndexingKnowledgeBase,
  deletingVectorFileId,
  detachingKnowledgeFileId,
  attachingKnowledgeFileId,
  onIndexFile,
  onDeleteFileVectors,
  onRemoveFile,
  onAttachFile,
}: {
  file: KnowledgeFile;
  mode: "selected" | "reusable";
  isFileIndexing: boolean;
  isIndexingKnowledgeBase: boolean;
  deletingVectorFileId: string;
  detachingKnowledgeFileId: string;
  attachingKnowledgeFileId: string;
  onIndexFile: (fileId: string) => void | Promise<void>;
  onDeleteFileVectors: (fileId: string) => void | Promise<void>;
  onRemoveFile: (fileId: string) => void | Promise<void>;
  onAttachFile: (fileId: string) => void | Promise<void>;
}) {
  const vectorStatus = getVectorStatus(file);

  return (
    <div className="flex items-center justify-between gap-4 py-4">
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-[#17201f]">
          {file.name}
        </p>
        <p className="mt-1 text-xs text-[#72807b]">
          {formatFileSize(file.size)} · {vectorStatus.label}
        </p>
        {vectorStatus.errorMessage && (
          <p className="mt-1 text-xs text-[#9b3c29]">
            {vectorStatus.errorMessage}
          </p>
        )}
        {vectorStatus.failureHint && (
          <p className="mt-1 text-xs font-semibold text-[#9b3c29]">
            {vectorStatus.failureHint}
          </p>
        )}
        {vectorStatus.workerHint && (
          <p className="mt-1 text-xs font-semibold text-[#9b3c29]">
            {vectorStatus.workerHint}
          </p>
        )}
        {vectorStatus.recoveryActions &&
          vectorStatus.recoveryActions.length > 0 && (
            <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-[#7a5a12]">
              {vectorStatus.recoveryActions.map((action) => (
                <li key={action}>{action}</li>
              ))}
            </ul>
          )}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {vectorStatus.canDeleteVector && (
          <button
            type="button"
            onClick={() => void onDeleteFileVectors(file.id)}
            disabled={
              isFileIndexing ||
              isIndexingKnowledgeBase ||
              Boolean(deletingVectorFileId)
            }
            className="px-2 py-1 text-xs font-semibold text-[#9b3c29] transition hover:bg-[#fff1ed] disabled:cursor-not-allowed disabled:text-[#aab3b0]"
          >
            {deletingVectorFileId === file.id
              ? "处理中..."
              : vectorStatus.deleteVectorLabel || "删除向量"}
          </button>
        )}
        <button
          type="button"
          onClick={() => void onIndexFile(file.id)}
          disabled={
            isFileIndexing ||
            !vectorStatus.canVectorize ||
            isIndexingKnowledgeBase
          }
          className="px-2 py-1 text-xs font-semibold text-[#176b62] transition hover:bg-[#e4f0ec] disabled:cursor-not-allowed disabled:text-[#aab3b0]"
        >
          {isFileIndexing || vectorStatus.canPoll
            ? "向量化中..."
            : vectorStatus.type === "failed"
              ? "重新向量化"
              : "向量化"}
        </button>
        {mode === "selected" ? (
          <button
            type="button"
            onClick={() => void onRemoveFile(file.id)}
            disabled={Boolean(detachingKnowledgeFileId)}
            className="px-2 py-1 text-xs font-semibold text-[#72807b] transition hover:bg-[#fff1ed] hover:text-[#9b3c29] disabled:cursor-not-allowed disabled:text-[#aab3b0]"
          >
            {detachingKnowledgeFileId === file.id ? "解除中..." : "解除关联"}
          </button>
        ) : (
          <button
            type="button"
            onClick={() => void onAttachFile(file.id)}
            disabled={Boolean(attachingKnowledgeFileId)}
            className="bg-[#176b62] px-3 py-2 text-xs font-semibold text-white transition hover:bg-[#105149] disabled:cursor-not-allowed disabled:bg-[#91aaa4]"
          >
            {attachingKnowledgeFileId === file.id ? "添加中..." : "添加"}
          </button>
        )}
      </div>
    </div>
  );
}

function KnowledgeFileList({
  title,
  titleTone,
  files,
  emptyState,
  loadingLabel,
  isLoading,
  mode,
  vectorIndexingFileIds,
  isIndexingKnowledgeBase,
  deletingVectorFileId,
  detachingKnowledgeFileId,
  attachingKnowledgeFileId,
  onIndexFile,
  onDeleteFileVectors,
  onRemoveFile,
  onAttachFile,
}: KnowledgeFileListProps) {
  const titleClass =
    titleTone === "primary" ? "text-[#176b62]" : "text-[#72807b]";

  return (
    <div className={mode === "selected" ? "mt-6" : "mt-7"}>
      <div className="flex items-center justify-between gap-4">
        <p
          className={`font-utility text-[10px] font-semibold uppercase ${titleClass}`}
        >
          {title}
        </p>
        <span className="font-utility text-[10px] text-[#72807b]">
          {String(files.length).padStart(2, "0")}
        </span>
      </div>

      <div className="mt-2 divide-y divide-[#d5ded9] border-y border-[#cbd5d1]">
        {isLoading ? (
          <p className="py-7 text-center text-sm text-[#64716d]">
            {loadingLabel}
          </p>
        ) : files.length > 0 ? (
          files.map((file) => (
            <KnowledgeFileRow
              key={file.id}
              file={file}
              mode={mode}
              isFileIndexing={Boolean(vectorIndexingFileIds[file.id])}
              isIndexingKnowledgeBase={isIndexingKnowledgeBase}
              deletingVectorFileId={deletingVectorFileId}
              detachingKnowledgeFileId={detachingKnowledgeFileId}
              attachingKnowledgeFileId={attachingKnowledgeFileId}
              onIndexFile={onIndexFile}
              onDeleteFileVectors={onDeleteFileVectors}
              onRemoveFile={onRemoveFile}
              onAttachFile={onAttachFile}
            />
          ))
        ) : (
          emptyState
        )}
      </div>
    </div>
  );
}

export function FileManagerDialog({
  knowledgeBaseName,
  selectedKnowledgeBaseId,
  selectedFiles,
  reusableFiles,
  vectorIndexingFileIds,
  vectorIndexQueue,
  vectorIndexHealth,
  vectorIndexHealthError,
  isLoadingVectorIndexHealth,
  isUploadingKnowledgeFiles,
  isIndexingKnowledgeBase,
  isLoadingKnowledgeFiles,
  isLoadingReusableFiles,
  deletingVectorFileId,
  detachingKnowledgeFileId,
  attachingKnowledgeFileId,
  knowledgeFileUploadError,
  knowledgeFileDetachError,
  knowledgeFileAttachError,
  knowledgeFileLoadError,
  reusableFileLoadError,
  vectorIndexMessage,
  vectorIndexError,
  onClose,
  onUploadClick,
  onIndexKnowledgeBase,
  onRefreshVectorHealth,
  onClearCompletedJobs,
  onIndexFile,
  onDeleteFileVectors,
  onRemoveFile,
  onAttachFile,
}: FileManagerDialogProps) {
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
            <p className="mt-1 text-sm text-[#64716d]">{knowledgeBaseName}</p>
            <p className="mt-1 text-xs text-[#72807b]">
              文件只保存一次，可关联到多个知识库
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭文件管理"
            className="flex h-9 w-9 items-center justify-center text-xl text-[#64716d] transition hover:bg-[#e1e9e5] hover:text-[#17201f]"
          >
            ×
          </button>
        </div>

        <div className="px-6 py-5">
          <button
            type="button"
            onClick={onUploadClick}
            disabled={!selectedKnowledgeBaseId || isUploadingKnowledgeFiles}
            className="w-full border border-dashed border-[#9bada6] bg-[#eef3f0] px-4 py-5 text-sm font-semibold text-[#46514e] transition hover:border-[#176b62] hover:text-[#176b62] disabled:border-[#cbd5d1] disabled:text-[#9ba8a3]"
          >
            {isUploadingKnowledgeFiles
              ? "正在上传并登记文件..."
              : selectedKnowledgeBaseId
                ? "选择文件上传"
                : "请先创建知识库"}
          </button>

          <button
            type="button"
            onClick={() => void onIndexKnowledgeBase()}
            disabled={
              selectedFiles.length === 0 ||
              isIndexingKnowledgeBase ||
              isUploadingKnowledgeFiles
            }
            className="mt-3 w-full border border-[#176b62] bg-[#fcfdfb] px-4 py-3 text-sm font-semibold text-[#176b62] transition hover:bg-[#e4f0ec] disabled:border-[#cbd5d1] disabled:text-[#9ba8a3]"
          >
            {isIndexingKnowledgeBase ? "知识库向量化中..." : "向量化当前知识库"}
          </button>

          {knowledgeFileUploadError && (
            <StatusMessage tone="danger">{knowledgeFileUploadError}</StatusMessage>
          )}
          {knowledgeFileDetachError && (
            <StatusMessage tone="danger">{knowledgeFileDetachError}</StatusMessage>
          )}
          {knowledgeFileAttachError && (
            <StatusMessage tone="danger">{knowledgeFileAttachError}</StatusMessage>
          )}
          {knowledgeFileLoadError && (
            <StatusMessage tone="danger">{knowledgeFileLoadError}</StatusMessage>
          )}
          {reusableFileLoadError && (
            <StatusMessage tone="danger">{reusableFileLoadError}</StatusMessage>
          )}
          {vectorIndexMessage && (
            <StatusMessage tone="success">{vectorIndexMessage}</StatusMessage>
          )}
          {vectorIndexError && (
            <StatusMessage tone="danger">{vectorIndexError}</StatusMessage>
          )}

          <TaskQueuePanel
            isLoadingHealth={isLoadingVectorIndexHealth}
            health={vectorIndexHealth}
            healthError={vectorIndexHealthError}
            queue={vectorIndexQueue}
            onRefreshHealth={onRefreshVectorHealth}
            onClearCompletedJobs={onClearCompletedJobs}
            onRetryFile={onIndexFile}
            onDeleteFileVectors={onDeleteFileVectors}
          />

          <KnowledgeFileList
            title="当前知识库"
            titleTone="primary"
            files={selectedFiles}
            emptyState={
              <div className="py-7 text-center">
                <p className="text-sm text-[#64716d]">当前知识库还没有文件</p>
                <p className="mt-1 text-xs text-[#8a9692]">
                  上传新文件，或从下方文件库添加
                </p>
              </div>
            }
            loadingLabel="正在读取文件..."
            isLoading={isLoadingKnowledgeFiles}
            mode="selected"
            vectorIndexingFileIds={vectorIndexingFileIds}
            isIndexingKnowledgeBase={isIndexingKnowledgeBase}
            deletingVectorFileId={deletingVectorFileId}
            detachingKnowledgeFileId={detachingKnowledgeFileId}
            attachingKnowledgeFileId={attachingKnowledgeFileId}
            onIndexFile={onIndexFile}
            onDeleteFileVectors={onDeleteFileVectors}
            onRemoveFile={onRemoveFile}
            onAttachFile={onAttachFile}
          />

          <KnowledgeFileList
            title="可复用文件"
            titleTone="muted"
            files={reusableFiles}
            emptyState={
              <p className="py-7 text-center text-sm text-[#72807b]">
                暂无其他可复用文件
              </p>
            }
            loadingLabel="正在读取可复用文件..."
            isLoading={isLoadingReusableFiles}
            mode="reusable"
            vectorIndexingFileIds={vectorIndexingFileIds}
            isIndexingKnowledgeBase={isIndexingKnowledgeBase}
            deletingVectorFileId={deletingVectorFileId}
            detachingKnowledgeFileId={detachingKnowledgeFileId}
            attachingKnowledgeFileId={attachingKnowledgeFileId}
            onIndexFile={onIndexFile}
            onDeleteFileVectors={onDeleteFileVectors}
            onRemoveFile={onRemoveFile}
            onAttachFile={onAttachFile}
          />
        </div>
      </section>
    </div>
  );
}
