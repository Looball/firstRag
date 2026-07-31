import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import * as chatApi from "./api";
import type {
  KnowledgeFile,
  VectorIndexJob,
  VectorIndexQueueItem,
} from "./types";
import {
  getVectorStatus,
  isVectorIndexJobDone,
  wait,
} from "./utils";

type RefreshKnowledgeFiles = (options?: {
  showLoading?: boolean;
}) => Promise<void>;

type UseVectorIndexQueueOptions = {
  hasCheckedAuth: boolean;
  knowledgeFiles: KnowledgeFile[];
  loadVectorIndexHealth: () => Promise<void>;
  refreshKnowledgeFiles: RefreshKnowledgeFiles;
};

/** 合并向量任务响应，并保留队列中已有的目标名称和类型。 */
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

/** 使用轮询结果更新已有队列项，不移除未参与本轮刷新的任务。 */
export function mergeRefreshedVectorIndexQueueItems(
  previousJobs: VectorIndexQueueItem[],
  jobs: VectorIndexJob[],
) {
  if (jobs.length === 0) {
    return previousJobs;
  }

  const jobsById = new Map(jobs.map((job) => [job.id, job]));

  return previousJobs.map((job) => {
    const nextJob = jobsById.get(job.id);
    return nextJob ? { ...job, ...nextJob } : job;
  });
}

/** 从本地任务队列中移除指定知识文件的历史任务。 */
export function removeVectorIndexQueueItemsForFile(
  previousJobs: VectorIndexQueueItem[],
  fileId: string,
) {
  return previousJobs.filter((job) => job.knowledgeFileId !== fileId);
}

/** 管理 vector index 本地任务队列、任务等待和后台轮询生命周期。 */
export function useVectorIndexQueue({
  hasCheckedAuth,
  knowledgeFiles,
  loadVectorIndexHealth,
  refreshKnowledgeFiles,
}: UseVectorIndexQueueOptions) {
  const [vectorIndexQueue, setVectorIndexQueue] = useState<
    VectorIndexQueueItem[]
  >([]);
  const hasPollingIndexJobs = useMemo(
    () => knowledgeFiles.some((file) => getVectorStatus(file).canPoll),
    [knowledgeFiles],
  );
  const hasActiveVectorIndexQueueJobs = useMemo(
    () => vectorIndexQueue.some((job) => !isVectorIndexJobDone(job)),
    [vectorIndexQueue],
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

        latestJobs = await Promise.all(
          latestJobs.map(async (job) => {
            if (isVectorIndexJobDone(job)) {
              return job;
            }

            return (await chatApi.getVectorIndexJob(job.id)) || job;
          }),
        );
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

    setVectorIndexQueue((previousJobs) =>
      mergeRefreshedVectorIndexQueueItems(previousJobs, nextJobs),
    );
  }, [vectorIndexQueue]);

  const clearCompletedVectorIndexJobs = useCallback(() => {
    setVectorIndexQueue((previousJobs) =>
      previousJobs.filter(
        (job) => job.status !== "succeeded" && job.status !== "failed",
      ),
    );
  }, []);

  const removeVectorIndexJobsForFile = useCallback((fileId: string) => {
    setVectorIndexQueue((previousJobs) =>
      removeVectorIndexQueueItemsForFile(previousJobs, fileId),
    );
  }, []);

  useEffect(() => {
    if (!hasCheckedAuth || !hasPollingIndexJobs) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void Promise.all([
        refreshKnowledgeFiles({ showLoading: false }),
        loadVectorIndexHealth(),
      ]);
    }, 2500);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [
    hasCheckedAuth,
    hasPollingIndexJobs,
    loadVectorIndexHealth,
    refreshKnowledgeFiles,
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
    clearCompletedVectorIndexJobs,
    removeVectorIndexJobsForFile,
    updateVectorIndexQueue,
    vectorIndexQueue,
    waitForVectorIndexJobs,
  };
}
