import { FrontendApiError } from "@/lib/frontend-api";
import { useRetryAfterCountdown } from "../use-retry-after-countdown";
import {
  type RefObject,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import { DEFAULT_KNOWLEDGE_BASE_ID } from "./constants";
import * as chatApi from "./api";
import type {
  KnowledgeBaseFile,
  KnowledgeFile,
} from "./types";

const MAX_UPLOAD_FILE_SIZE = 200 * 1024 * 1024;
export const KNOWLEDGE_FILE_SUPPORTED_TYPES_TEXT =
  "PDF、DOCX、Markdown、TXT、PNG、JPEG 和 WebP";

type LoadingOptions = {
  showLoading?: boolean;
};

type UseKnowledgeFileLibraryOptions = {
  hasCheckedAuth: boolean;
  selectedKnowledgeBaseId: string;
  selectedKnowledgeBaseStoredFileCount: number;
  fileInputRef: RefObject<HTMLInputElement | null>;
  onKnowledgeBaseFileCountChange: (
    knowledgeBaseId: string,
    fileCount: number,
  ) => void;
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

/** 合并指定知识库的文件响应，并保留全局列表中已有的 usage count。 */
export function mergeKnowledgeFilesForKnowledgeBase(
  previousFiles: KnowledgeFile[],
  loadedFiles: KnowledgeFile[],
) {
  const loadedFileIds = new Set(loadedFiles.map((file) => file.id));
  const previousFilesById = new Map(previousFiles.map((file) => [file.id, file]));
  const mergedLoadedFiles = loadedFiles.map((file) => ({
    ...file,
    usageCount:
      file.usageCount ?? previousFilesById.get(file.id)?.usageCount ?? null,
  }));

  return [
    ...mergedLoadedFiles,
    ...previousFiles.filter((file) => !loadedFileIds.has(file.id)),
  ];
}

/** 替换指定知识库的文件关联，同时保留其他知识库的关联缓存。 */
export function replaceKnowledgeBaseFileAssociations(
  previousAssociations: KnowledgeBaseFile[],
  knowledgeBaseId: string,
  loadedFiles: KnowledgeFile[],
) {
  return [
    ...previousAssociations.filter(
      (association) => association.knowledgeBaseId !== knowledgeBaseId,
    ),
    ...loadedFiles.map((file) => ({
      knowledgeBaseId,
      knowledgeFileId: file.id,
    })),
  ];
}

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

/** 管理知识文件列表、上传、知识库关联和永久删除生命周期。 */
export function useKnowledgeFileLibrary({
  hasCheckedAuth,
  selectedKnowledgeBaseId,
  selectedKnowledgeBaseStoredFileCount,
  fileInputRef,
  onKnowledgeBaseFileCountChange,
}: UseKnowledgeFileLibraryOptions) {
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
  const [permanentlyDeletingFileId, setPermanentlyDeletingFileId] =
    useState("");
  const [knowledgeFileDeleteError, setKnowledgeFileDeleteError] =
    useState("");
  const [knowledgeFileAttachError, setKnowledgeFileAttachError] =
    useState("");
  const [isLoadingKnowledgeFiles, setIsLoadingKnowledgeFiles] =
    useState(false);
  const [knowledgeFileLoadError, setKnowledgeFileLoadError] = useState("");
  const [isLoadingReusableFiles, setIsLoadingReusableFiles] =
    useState(false);
  const [reusableFileLoadError, setReusableFileLoadError] = useState("");
  const [knowledgeFiles, setKnowledgeFiles] = useState<KnowledgeFile[]>([]);
  const [knowledgeBaseFiles, setKnowledgeBaseFiles] = useState<
    KnowledgeBaseFile[]
  >([]);
  const {
    isRateLimited: isUploadRateLimited,
    retryAfterSeconds: uploadRetryAfterSeconds,
    startCountdownFromError: startUploadCountdownFromError,
  } = useRetryAfterCountdown();

  const selectedKnowledgeFileIds = useMemo(
    () =>
      new Set(
        knowledgeBaseFiles
          .filter(
            (association) =>
              association.knowledgeBaseId === selectedKnowledgeBaseId,
          )
          .map((association) => association.knowledgeFileId),
      ),
    [knowledgeBaseFiles, selectedKnowledgeBaseId],
  );
  const selectedKnowledgeFiles = useMemo(
    () => knowledgeFiles.filter((file) => selectedKnowledgeFileIds.has(file.id)),
    [knowledgeFiles, selectedKnowledgeFileIds],
  );
  const reusableKnowledgeFiles = useMemo(
    () => knowledgeFiles.filter((file) => !selectedKnowledgeFileIds.has(file.id)),
    [knowledgeFiles, selectedKnowledgeFileIds],
  );
  const selectedKnowledgeBaseFileCount =
    selectedKnowledgeFiles.length || selectedKnowledgeBaseStoredFileCount || 0;

  const loadKnowledgeBaseFiles = useCallback(
    async (knowledgeBaseId: string, options?: LoadingOptions) => {
      if (!knowledgeBaseId || knowledgeBaseId === DEFAULT_KNOWLEDGE_BASE_ID) {
        return;
      }

      const shouldShowLoading = options?.showLoading !== false;

      if (shouldShowLoading) {
        setIsLoadingKnowledgeFiles(true);
      }

      setKnowledgeFileLoadError("");

      try {
        const loadedFiles = await chatApi.listKnowledgeBaseFiles(knowledgeBaseId);

        setKnowledgeFiles((previousFiles) =>
          mergeKnowledgeFilesForKnowledgeBase(previousFiles, loadedFiles),
        );
        setKnowledgeBaseFiles((previousAssociations) =>
          replaceKnowledgeBaseFileAssociations(
            previousAssociations,
            knowledgeBaseId,
            loadedFiles,
          ),
        );
        onKnowledgeBaseFileCountChange(knowledgeBaseId, loadedFiles.length);
      } catch (error) {
        setKnowledgeFileLoadError(
          error instanceof Error
            ? error.message
            : "读取知识库文件失败，请稍后再试。",
        );
      } finally {
        if (shouldShowLoading) {
          setIsLoadingKnowledgeFiles(false);
        }
      }
    },
    [onKnowledgeBaseFileCountChange],
  );

  const loadAllKnowledgeFiles = useCallback(async (options?: LoadingOptions) => {
    const shouldShowLoading = options?.showLoading !== false;

    if (shouldShowLoading) {
      setIsLoadingReusableFiles(true);
    }

    setReusableFileLoadError("");

    try {
      setKnowledgeFiles(await chatApi.listAllKnowledgeFiles());
    } catch (error) {
      setReusableFileLoadError(
        error instanceof Error
          ? error.message
          : "读取用户文件列表失败，请稍后再试。",
      );
    } finally {
      if (shouldShowLoading) {
        setIsLoadingReusableFiles(false);
      }
    }
  }, []);

  const refreshKnowledgeFiles = useCallback(
    async (options?: LoadingOptions) => {
      await Promise.all([
        loadKnowledgeBaseFiles(selectedKnowledgeBaseId, options),
        loadAllKnowledgeFiles(options),
      ]);
    },
    [loadAllKnowledgeFiles, loadKnowledgeBaseFiles, selectedKnowledgeBaseId],
  );

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

  useEffect(() => {
    if (!hasCheckedAuth || !selectedKnowledgeBaseId) {
      return;
    }

    void loadKnowledgeBaseFiles(selectedKnowledgeBaseId);
  }, [hasCheckedAuth, loadKnowledgeBaseFiles, selectedKnowledgeBaseId]);

  return {
    attachingKnowledgeFileId,
    detachingKnowledgeFileId,
    handleAttachKnowledgeFile,
    handlePermanentlyDeleteKnowledgeFile,
    handleRemoveKnowledgeFile,
    handleSelectFiles,
    isLoadingKnowledgeFiles,
    isLoadingReusableFiles,
    isUploadingKnowledgeFiles,
    knowledgeBaseFiles,
    knowledgeFileAttachError,
    knowledgeFileDeleteError,
    knowledgeFileDetachError,
    knowledgeFileLoadError,
    knowledgeFileUploadError,
    knowledgeFiles,
    loadAllKnowledgeFiles,
    loadKnowledgeBaseFiles,
    permanentlyDeletingFileId,
    refreshKnowledgeFiles,
    reusableFileLoadError,
    reusableKnowledgeFiles,
    selectedKnowledgeBaseFileCount,
    selectedKnowledgeFiles,
    uploadRetryAfterSeconds,
  };
}
