import { FrontendApiError } from "@/lib/frontend-api";
import { useRetryAfterCountdown } from "../use-retry-after-countdown";
import {
  type RefObject,
  useCallback,
  useState,
} from "react";
import * as chatApi from "./api";
import type { KnowledgeFile } from "./types";

const MAX_UPLOAD_FILE_SIZE = 200 * 1024 * 1024;
export const KNOWLEDGE_FILE_SUPPORTED_TYPES_TEXT =
  "PDF、DOCX、Markdown、TXT、PNG、JPEG 和 WebP";

type UseKnowledgeFileMutationsOptions = {
  selectedKnowledgeBaseId: string;
  fileInputRef: RefObject<HTMLInputElement | null>;
  refreshKnowledgeFiles: () => Promise<void>;
};

type UploadKnowledgeFileEffects = {
  onStart: () => void;
  onUploaded: (files: KnowledgeFile[]) => void;
  refreshExternalState: () => Promise<void>;
};

type DeleteKnowledgeFileEffects = {
  onStart: () => void;
  onDeleted: (fileId: string) => void;
  refreshExternalState: () => Promise<void>;
};

/** 根据上传结果生成复用、已有关联和向量化提示。 */
export function buildKnowledgeFileUploadMessage(files: KnowledgeFile[]) {
  if (files.length === 0) {
    return "文件上传已完成。";
  }

  const reusedCount = files.filter((file) => file.reused).length;
  const alreadyLinkedCount = files.filter(
    (file) => file.alreadyInKnowledgeBase,
  ).length;
  const messages = [`已处理 ${files.length} 个文件。`];

  if (reusedCount > 0) {
    messages.push(`${reusedCount} 个文件复用已有上传记录。`);
  }

  if (alreadyLinkedCount > 0) {
    messages.push(`${alreadyLinkedCount} 个文件已在当前知识库中。`);
  }

  messages.push("需要检索前，请点击“向量化”或“向量化当前知识库”。");
  return messages.join("");
}

/** 将上传错误转换为包含恢复动作的用户提示。 */
export function buildKnowledgeFileUploadErrorMessage(error: unknown) {
  const message =
    error instanceof Error ? error.message : "上传文件失败，请稍后再试。";

  if (error instanceof FrontendApiError && error.status === 413) {
    return `${message}。请压缩文件、拆分文档，或联系管理员调整上传上限。`;
  }

  if (message.includes("不支持的文件类型")) {
    return `${message}。当前支持 ${KNOWLEDGE_FILE_SUPPORTED_TYPES_TEXT} 文件。`;
  }

  return message;
}

/** 管理知识文件上传、关联、解除关联和永久删除 mutation 生命周期。 */
export function useKnowledgeFileMutations({
  selectedKnowledgeBaseId,
  fileInputRef,
  refreshKnowledgeFiles,
}: UseKnowledgeFileMutationsOptions) {
  const [isUploadingKnowledgeFiles, setIsUploadingKnowledgeFiles] =
    useState(false);
  const [knowledgeFileUploadError, setKnowledgeFileUploadError] =
    useState("");
  const [detachingKnowledgeFileId, setDetachingKnowledgeFileId] =
    useState("");
  const [knowledgeFileDetachError, setKnowledgeFileDetachError] =
    useState("");
  const [attachingKnowledgeFileId, setAttachingKnowledgeFileId] =
    useState("");
  const [knowledgeFileAttachError, setKnowledgeFileAttachError] =
    useState("");
  const [permanentlyDeletingFileId, setPermanentlyDeletingFileId] =
    useState("");
  const [knowledgeFileDeleteError, setKnowledgeFileDeleteError] =
    useState("");
  const {
    isRateLimited: isUploadRateLimited,
    retryAfterSeconds: uploadRetryAfterSeconds,
    startCountdownFromError: startUploadCountdownFromError,
  } = useRetryAfterCountdown();

  const handleSelectFiles = useCallback(
    async (
      files: FileList | null,
      effects: UploadKnowledgeFileEffects,
    ) => {
      if (
        !files?.length ||
        !selectedKnowledgeBaseId ||
        isUploadingKnowledgeFiles ||
        isUploadRateLimited
      ) {
        return;
      }

      const selectedFiles = Array.from(files);
      const oversizedFiles = selectedFiles.filter(
        (file) => file.size > MAX_UPLOAD_FILE_SIZE,
      );

      if (oversizedFiles.length > 0) {
        const names = oversizedFiles.map((file) => file.name).join("、");
        setKnowledgeFileUploadError(
          `以下文件超过 200MB 限制，请压缩或拆分后重新上传：${names}。`,
        );
        return;
      }

      setIsUploadingKnowledgeFiles(true);
      setKnowledgeFileUploadError("");
      effects.onStart();

      try {
        const uploadedFiles = await chatApi.uploadKnowledgeFiles(
          selectedKnowledgeBaseId,
          selectedFiles,
        );

        effects.onUploaded(uploadedFiles);
        await Promise.all([
          refreshKnowledgeFiles(),
          effects.refreshExternalState(),
        ]);
      } catch (error) {
        startUploadCountdownFromError(error);
        setKnowledgeFileUploadError(buildKnowledgeFileUploadErrorMessage(error));
      } finally {
        setIsUploadingKnowledgeFiles(false);

        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }
      }
    },
    [
      fileInputRef,
      isUploadingKnowledgeFiles,
      isUploadRateLimited,
      refreshKnowledgeFiles,
      selectedKnowledgeBaseId,
      startUploadCountdownFromError,
    ],
  );

  const handleAttachKnowledgeFile = useCallback(
    async (fileId: string) => {
      if (!selectedKnowledgeBaseId || !fileId || attachingKnowledgeFileId) {
        return;
      }

      setAttachingKnowledgeFileId(fileId);
      setKnowledgeFileAttachError("");

      try {
        await chatApi.attachKnowledgeFile(selectedKnowledgeBaseId, fileId);
        await refreshKnowledgeFiles();
      } catch (error) {
        setKnowledgeFileAttachError(
          error instanceof Error
            ? error.message
            : "添加文件关联失败，请稍后再试。",
        );
      } finally {
        setAttachingKnowledgeFileId("");
      }
    },
    [attachingKnowledgeFileId, refreshKnowledgeFiles, selectedKnowledgeBaseId],
  );

  const handleRemoveKnowledgeFile = useCallback(
    async (fileId: string) => {
      if (!selectedKnowledgeBaseId || !fileId || detachingKnowledgeFileId) {
        return;
      }

      setDetachingKnowledgeFileId(fileId);
      setKnowledgeFileDetachError("");

      try {
        await chatApi.removeKnowledgeFile(selectedKnowledgeBaseId, fileId);
        await refreshKnowledgeFiles();
      } catch (error) {
        setKnowledgeFileDetachError(
          error instanceof Error
            ? error.message
            : "解除文件关联失败，请稍后再试。",
        );
      } finally {
        setDetachingKnowledgeFileId("");
      }
    },
    [detachingKnowledgeFileId, refreshKnowledgeFiles, selectedKnowledgeBaseId],
  );

  const handlePermanentlyDeleteKnowledgeFile = useCallback(
    async (
      fileId: string,
      effects: DeleteKnowledgeFileEffects,
    ) => {
      if (!fileId || permanentlyDeletingFileId) {
        return;
      }

      setPermanentlyDeletingFileId(fileId);
      setKnowledgeFileDeleteError("");
      effects.onStart();

      try {
        await chatApi.permanentlyDeleteKnowledgeFile(fileId);
        effects.onDeleted(fileId);
        await Promise.all([
          refreshKnowledgeFiles(),
          effects.refreshExternalState(),
        ]);
      } catch (error) {
        setKnowledgeFileDeleteError(
          error instanceof Error
            ? error.message
            : "永久删除知识文件失败，请稍后再试。",
        );
      } finally {
        setPermanentlyDeletingFileId("");
      }
    },
    [permanentlyDeletingFileId, refreshKnowledgeFiles],
  );

  return {
    attachingKnowledgeFileId,
    detachingKnowledgeFileId,
    handleAttachKnowledgeFile,
    handlePermanentlyDeleteKnowledgeFile,
    handleRemoveKnowledgeFile,
    handleSelectFiles,
    isUploadingKnowledgeFiles,
    knowledgeFileAttachError,
    knowledgeFileDeleteError,
    knowledgeFileDetachError,
    knowledgeFileUploadError,
    permanentlyDeletingFileId,
    uploadRetryAfterSeconds,
  };
}
