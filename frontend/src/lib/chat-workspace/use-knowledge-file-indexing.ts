import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  type Dispatch,
  type SetStateAction,
  useCallback,
  useState,
} from "react";
import { useRetryAfterCountdown } from "../use-retry-after-countdown";
import * as chatApi from "./api";
import { DEFAULT_KNOWLEDGE_BASE_ID } from "./constants";
import type { KnowledgeFile } from "./types";
import { useVectorIndexQueue } from "./use-vector-index-queue";

export const VECTOR_INDEX_HEALTH_QUERY_KEY = [
  "chat-workspace",
  "vector-index-health",
] as const;

type RefreshKnowledgeFiles = (options?: {
  showLoading?: boolean;
}) => Promise<void>;

type UseKnowledgeFileIndexingOptions = {
  hasCheckedAuth: boolean;
  knowledgeFiles: KnowledgeFile[];
  refreshKnowledgeFiles: RefreshKnowledgeFiles;
  selectedKnowledgeBaseId: string;
  selectedKnowledgeBaseName: string;
  setVectorIndexError: Dispatch<SetStateAction<string>>;
  setVectorIndexMessage: Dispatch<SetStateAction<string>>;
};

/** 管理知识文件向量化 health、提交、删除和 Retry-After 生命周期。 */
export function useKnowledgeFileIndexing({
  hasCheckedAuth,
  knowledgeFiles,
  refreshKnowledgeFiles,
  selectedKnowledgeBaseId,
  selectedKnowledgeBaseName,
  setVectorIndexError,
  setVectorIndexMessage,
}: UseKnowledgeFileIndexingOptions) {
  const [deletingVectorFileId, setDeletingVectorFileId] = useState("");
  const [vectorIndexingFileIds, setVectorIndexingFileIds] = useState<
    Record<string, boolean>
  >({});
  const [isIndexingKnowledgeBase, setIsIndexingKnowledgeBase] =
    useState(false);
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

  const loadVectorIndexHealth = useCallback(async () => {
    try {
      await queryClient.fetchQuery({
        queryKey: VECTOR_INDEX_HEALTH_QUERY_KEY,
        queryFn: chatApi.loadVectorIndexHealth,
        staleTime: 0,
      });
    } catch {
      // Health 仅用于辅助诊断，查询错误由面板状态负责展示。
    }
  }, [queryClient]);

  const {
    clearCompletedVectorIndexJobs,
    removeVectorIndexJobsForFile,
    updateVectorIndexQueue,
    vectorIndexQueue,
    waitForVectorIndexJobs,
  } = useVectorIndexQueue({
    hasCheckedAuth,
    knowledgeFiles,
    loadVectorIndexHealth,
    refreshKnowledgeFiles,
  });

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
        await Promise.all([
          refreshKnowledgeFiles(),
          loadVectorIndexHealth(),
        ]);
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
      isVectorIndexRateLimited,
      knowledgeFiles,
      loadVectorIndexHealth,
      refreshKnowledgeFiles,
      setVectorIndexError,
      setVectorIndexMessage,
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
        await Promise.all([
          refreshKnowledgeFiles(),
          loadVectorIndexHealth(),
        ]);
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
    [
      deletingVectorFileId,
      loadVectorIndexHealth,
      refreshKnowledgeFiles,
      setVectorIndexError,
      setVectorIndexMessage,
    ],
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

      await Promise.all([
        refreshKnowledgeFiles(),
        loadVectorIndexHealth(),
      ]);
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
    setVectorIndexError,
    setVectorIndexMessage,
    startVectorIndexCountdownFromError,
    updateVectorIndexQueue,
    waitForVectorIndexJobs,
  ]);

  return {
    clearCompletedVectorIndexJobs,
    deletingVectorFileId,
    handleDeleteKnowledgeFileVectors,
    handleIndexKnowledgeBase,
    handleIndexKnowledgeFile,
    isIndexingKnowledgeBase,
    isLoadingVectorIndexHealth,
    loadVectorIndexHealth,
    removeVectorIndexJobsForFile,
    vectorIndexHealth,
    vectorIndexHealthError,
    vectorIndexingFileIds,
    vectorIndexQueue,
    vectorIndexRetryAfterSeconds,
  };
}
