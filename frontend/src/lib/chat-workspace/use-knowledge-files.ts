import { useQuery, useQueryClient } from "@tanstack/react-query";
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
import {
  getVectorStatus,
  isVectorIndexJobDone,
  wait,
} from "./utils";
import type {
  KnowledgeBaseFile,
  KnowledgeFile,
  VectorIndexJob,
  VectorIndexQueueItem,
} from "./types";

export const VECTOR_INDEX_HEALTH_QUERY_KEY = [
  "chat-workspace",
  "vector-index-health",
] as const;

const MAX_UPLOAD_FILE_SIZE = 200 * 1024 * 1024;
export const KNOWLEDGE_FILE_SUPPORTED_TYPES_TEXT =
  "PDF、DOCX、Markdown、TXT、PNG、JPEG 和 WebP";

type LoadingOptions = {
  showLoading?: boolean;
};

type UseKnowledgeFilesOptions = {
  hasCheckedAuth: boolean;
  selectedKnowledgeBaseId: string;
  selectedKnowledgeBaseName: string;
  selectedKnowledgeBaseStoredFileCount: number;
  fileInputRef: RefObject<HTMLInputElement | null>;
  onKnowledgeBaseFileCountChange: (
    knowledgeBaseId: string,
    fileCount: number,
  ) => void;
};

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

export function mergeVectorIndexQueueItems(
  previousJobs: VectorIndexQueueItem[],
  jobs: VectorIndexJob[],
  target: Pick<VectorIndexQueueItem, "targetName" | "targetType">,
) {
  if (jobs.length === 0) {
    return previousJobs;
  }

  const nextJobs = new Map<string, VectorIndexQueueItem>(
    previousJobs.map((job) => [job.id, job]),
  );

  jobs.forEach((job) => {
    const previousJob = nextJobs.get(job.id);

    nextJobs.set(job.id, {
      ...(previousJob || {}),
      ...job,
      targetName: previousJob?.targetName || target.targetName,
      targetType: previousJob?.targetType || target.targetType,
    });
  });

  return Array.from(nextJobs.values());
}

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

export function useKnowledgeFiles({
  hasCheckedAuth,
  selectedKnowledgeBaseId,
  selectedKnowledgeBaseName,
  selectedKnowledgeBaseStoredFileCount,
  fileInputRef,
  onKnowledgeBaseFileCountChange,
}: UseKnowledgeFilesOptions) {
  const [isFileManagerOpen, setIsFileManagerOpen] = useState(false);
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
  const [deletingVectorFileId, setDeletingVectorFileId] = useState("");
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
  const [vectorIndexingFileIds, setVectorIndexingFileIds] = useState<
    Record<string, boolean>
  >({});
  const [vectorIndexQueue, setVectorIndexQueue] = useState<
    VectorIndexQueueItem[]
  >([]);
  const [isIndexingKnowledgeBase, setIsIndexingKnowledgeBase] =
    useState(false);
  const [vectorIndexMessage, setVectorIndexMessage] = useState("");
  const [vectorIndexError, setVectorIndexError] = useState("");
  const {
    isRateLimited: isUploadRateLimited,
    retryAfterSeconds: uploadRetryAfterSeconds,
    startCountdownFromError: startUploadCountdownFromError,
  } = useRetryAfterCountdown();
  const {
    isRateLimited: isVectorIndexRateLimited,
    retryAfterSeconds: vectorIndexRetryAfterSeconds,
    startCountdownFromError: startVectorIndexCountdownFromError,
  } = useRetryAfterCountdown();

  const queryClient = useQueryClient();
  const vectorIndexHealthQuery = useQuery({
    queryKey: VECTOR_INDEX_HEALTH_QUERY_KEY,
    queryFn: chatApi.loadVectorIndexHealth,
    enabled: hasCheckedAuth,
    staleTime: 5_000,
  });
  const vectorIndexHealth = vectorIndexHealthQuery.data ?? null;
  const vectorIndexHealthError = vectorIndexHealthQuery.error
    ? "任务状态暂不可用"
    : "";
  const isLoadingVectorIndexHealth = vectorIndexHealthQuery.isFetching;

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
  const hasPollingIndexJobs = useMemo(
    () => knowledgeFiles.some((file) => getVectorStatus(file).canPoll),
    [knowledgeFiles],
  );
  const hasActiveVectorIndexQueueJobs = useMemo(
    () => vectorIndexQueue.some((job) => !isVectorIndexJobDone(job)),
    [vectorIndexQueue],
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

  const loadVectorIndexHealth = useCallback(async () => {
    try {
      await queryClient.fetchQuery({
        queryKey: VECTOR_INDEX_HEALTH_QUERY_KEY,
        queryFn: chatApi.loadVectorIndexHealth,
        staleTime: 0,
      });
    } catch {
      // Health is advisory; the panel renders the query error state.
    }
  }, [queryClient]);

  const refreshKnowledgeFiles = useCallback(
    async (options?: LoadingOptions) => {
      await Promise.all([
        loadKnowledgeBaseFiles(selectedKnowledgeBaseId, options),
        loadAllKnowledgeFiles(options),
      ]);
    },
    [loadAllKnowledgeFiles, loadKnowledgeBaseFiles, selectedKnowledgeBaseId],
  );

  const updateVectorIndexQueue = useCallback(
    (
      jobs: VectorIndexJob[],
      target: Pick<VectorIndexQueueItem, "targetName" | "targetType">,
    ) => {
      setVectorIndexQueue((previousJobs) =>
        mergeVectorIndexQueueItems(previousJobs, jobs, target),
      );
    },
    [],
  );

  const waitForVectorIndexJobs = useCallback(
    async (
      jobs: VectorIndexJob[],
      onJobsUpdated?: (jobs: VectorIndexJob[]) => void,
    ) => {
      if (jobs.length === 0) {
        return [];
      }

      let latestJobs = jobs;
      onJobsUpdated?.(latestJobs);

      for (let attempt = 0; attempt < 45; attempt += 1) {
        if (latestJobs.every(isVectorIndexJobDone)) {
          return latestJobs;
        }

        await wait(2000);

        const nextJobs = await Promise.all(
          latestJobs.map(async (job) => {
            if (isVectorIndexJobDone(job)) {
              return job;
            }

            return (await chatApi.getVectorIndexJob(job.id)) || job;
          }),
        );

        latestJobs = nextJobs;
        onJobsUpdated?.(latestJobs);
      }

      return latestJobs;
    },
    [],
  );

  const refreshVectorIndexQueue = useCallback(async () => {
    const activeJobs = vectorIndexQueue.filter(
      (job) => !isVectorIndexJobDone(job),
    );

    if (activeJobs.length === 0) {
      return;
    }

    const nextJobs = await Promise.all(
      activeJobs.map(async (job) => {
        return (await chatApi.getVectorIndexJob(job.id)) || job;
      }),
    );
    const nextJobsById = new Map(nextJobs.map((job) => [job.id, job]));

    setVectorIndexQueue((previousJobs) =>
      previousJobs.map((job) => {
        const nextJob = nextJobsById.get(job.id);

        return nextJob ? { ...job, ...nextJob } : job;
      }),
    );
  }, [vectorIndexQueue]);

  const handleOpenFileManager = useCallback(async () => {
    setIsFileManagerOpen(true);
    await Promise.all([
      loadKnowledgeBaseFiles(selectedKnowledgeBaseId),
      loadAllKnowledgeFiles(),
      loadVectorIndexHealth(),
    ]);
  }, [
    loadAllKnowledgeFiles,
    loadKnowledgeBaseFiles,
    loadVectorIndexHealth,
    selectedKnowledgeBaseId,
  ]);

  const handleSelectFiles = useCallback(
    async (files: FileList | null) => {
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
      setVectorIndexError("");
      setVectorIndexMessage("");
      setIsFileManagerOpen(true);

      try {
        const uploadedFiles = await chatApi.uploadKnowledgeFiles(
          selectedKnowledgeBaseId,
          selectedFiles,
        );

        setVectorIndexMessage(buildKnowledgeFileUploadMessage(uploadedFiles));
        await Promise.all([refreshKnowledgeFiles(), loadVectorIndexHealth()]);
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
      loadVectorIndexHealth,
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

  const handleIndexKnowledgeFile = useCallback(
    async (fileId: string) => {
      if (
        !fileId ||
        vectorIndexingFileIds[fileId] ||
        isVectorIndexRateLimited
      ) {
        return;
      }

      const targetFile = knowledgeFiles.find((file) => file.id === fileId);
      const target = {
        targetName: targetFile?.name || "知识库文件",
        targetType: "file" as const,
      };
      setVectorIndexingFileIds((previousFileIds) => ({
        ...previousFileIds,
        [fileId]: true,
      }));
      setVectorIndexError("");
      setVectorIndexMessage("");

      try {
        const jobs = await chatApi.indexKnowledgeFile(fileId);
        updateVectorIndexQueue(jobs, target);

        setVectorIndexMessage("文件向量化任务已提交。");
        await Promise.all([refreshKnowledgeFiles(), loadVectorIndexHealth()]);
      } catch (error) {
        startVectorIndexCountdownFromError(error);
        setVectorIndexError(
          error instanceof Error ? error.message : "文件向量化失败，请稍后再试。",
        );
      } finally {
        setVectorIndexingFileIds((previousFileIds) => {
          const nextFileIds = { ...previousFileIds };
          delete nextFileIds[fileId];
          return nextFileIds;
        });
      }
    },
    [
      knowledgeFiles,
      isVectorIndexRateLimited,
      loadVectorIndexHealth,
      refreshKnowledgeFiles,
      startVectorIndexCountdownFromError,
      updateVectorIndexQueue,
      vectorIndexingFileIds,
    ],
  );

  const handleDeleteKnowledgeFileVectors = useCallback(
    async (fileId: string) => {
      if (!fileId || deletingVectorFileId) {
        return;
      }

      setDeletingVectorFileId(fileId);
      setVectorIndexError("");
      setVectorIndexMessage("");

      try {
        await chatApi.deleteKnowledgeFileVectors(fileId);
        setVectorIndexMessage("文件向量已删除，可重新向量化。");
        await Promise.all([refreshKnowledgeFiles(), loadVectorIndexHealth()]);
      } catch (error) {
        setVectorIndexError(
          error instanceof Error
            ? error.message
            : "删除文件向量失败，请稍后再试。",
        );
      } finally {
        setDeletingVectorFileId("");
      }
    },
    [deletingVectorFileId, loadVectorIndexHealth, refreshKnowledgeFiles],
  );

  const handleIndexKnowledgeBase = useCallback(async () => {
    if (
      !selectedKnowledgeBaseId ||
      selectedKnowledgeBaseId === DEFAULT_KNOWLEDGE_BASE_ID ||
      isIndexingKnowledgeBase ||
      isVectorIndexRateLimited
    ) {
      return;
    }

    setIsIndexingKnowledgeBase(true);
    setVectorIndexError("");
    setVectorIndexMessage("");

    try {
      const target = {
        targetName: selectedKnowledgeBaseName || "当前知识库",
        targetType: "knowledge-base" as const,
      };
      const jobs = await chatApi.indexKnowledgeBase(selectedKnowledgeBaseId);
      updateVectorIndexQueue(jobs, target);

      setVectorIndexMessage("知识库向量化任务已提交。");

      const finishedJobs = await waitForVectorIndexJobs(jobs, (latestJobs) =>
        updateVectorIndexQueue(latestJobs, target),
      );
      const failedJob = finishedJobs.find((job) => job.status === "failed");

      if (failedJob) {
        throw new Error(failedJob.errorMessage || "知识库向量化失败。");
      }

      if (finishedJobs.length > 0) {
        setVectorIndexMessage("知识库向量化完成。");
      }

      await Promise.all([refreshKnowledgeFiles(), loadVectorIndexHealth()]);
    } catch (error) {
      startVectorIndexCountdownFromError(error);
      setVectorIndexError(
        error instanceof Error ? error.message : "知识库向量化失败，请稍后再试。",
      );
    } finally {
      setIsIndexingKnowledgeBase(false);
    }
  }, [
    isIndexingKnowledgeBase,
    isVectorIndexRateLimited,
    loadVectorIndexHealth,
    refreshKnowledgeFiles,
    selectedKnowledgeBaseId,
    selectedKnowledgeBaseName,
    startVectorIndexCountdownFromError,
    updateVectorIndexQueue,
    waitForVectorIndexJobs,
  ]);

  const clearCompletedVectorIndexJobs = useCallback(() => {
    setVectorIndexQueue((previousJobs) =>
      previousJobs.filter(
        (job) => job.status !== "succeeded" && job.status !== "failed",
      ),
    );
  }, []);

  useEffect(() => {
    if (!hasCheckedAuth || !selectedKnowledgeBaseId) {
      return;
    }

    void loadKnowledgeBaseFiles(selectedKnowledgeBaseId);
  }, [hasCheckedAuth, loadKnowledgeBaseFiles, selectedKnowledgeBaseId]);

  useEffect(() => {
    if (!hasCheckedAuth || !hasPollingIndexJobs) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void Promise.all([
        loadKnowledgeBaseFiles(selectedKnowledgeBaseId, {
          showLoading: false,
        }),
        loadAllKnowledgeFiles({ showLoading: false }),
        loadVectorIndexHealth(),
      ]);
    }, 2500);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [
    hasCheckedAuth,
    hasPollingIndexJobs,
    loadAllKnowledgeFiles,
    loadKnowledgeBaseFiles,
    loadVectorIndexHealth,
    selectedKnowledgeBaseId,
  ]);

  useEffect(() => {
    if (!hasCheckedAuth || !hasActiveVectorIndexQueueJobs) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void Promise.all([
        refreshVectorIndexQueue(),
        loadVectorIndexHealth(),
      ]);
    }, 2500);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [
    hasActiveVectorIndexQueueJobs,
    hasCheckedAuth,
    loadVectorIndexHealth,
    refreshVectorIndexQueue,
  ]);

  return {
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
    uploadRetryAfterSeconds,
    vectorIndexRetryAfterSeconds,
  };
}
