import { describe, expect, it, vi } from "vitest";

import type { VectorIndexQueueItem } from "./types";
import {
  mergeRefreshedVectorIndexQueueItems,
  mergeVectorIndexQueueItems,
  removeVectorIndexQueueItemsForFile,
} from "./use-knowledge-file-indexing";

vi.mock("@/lib/frontend-api", () => ({
  authenticatedFetch: vi.fn(),
  authenticatedJson: vi.fn(),
  authenticatedText: vi.fn(),
}));

/** 构造向量任务队列测试数据。 */
function queueItem(
  id: string,
  overrides: Partial<VectorIndexQueueItem> = {},
): VectorIndexQueueItem {
  return {
    id,
    status: "queued",
    errorMessage: "",
    failureHint: "",
    targetName: "合同.md",
    targetType: "file",
    ...overrides,
  };
}

describe("useKnowledgeFileIndexing helpers", () => {
  it("merges jobs while keeping existing target labels", () => {
    const previousJobs = [queueItem("job-1")];

    expect(
      mergeVectorIndexQueueItems(
        previousJobs,
        [
          {
            id: "job-1",
            status: "succeeded",
            errorMessage: "",
            failureHint: "",
          },
          {
            id: "job-2",
            status: "queued",
            errorMessage: "",
            failureHint: "",
          },
        ],
        { targetName: "当前知识库", targetType: "knowledge-base" },
      ),
    ).toEqual([
      queueItem("job-1", { status: "succeeded" }),
      queueItem("job-2", {
        targetName: "当前知识库",
        targetType: "knowledge-base",
      }),
    ]);
  });

  it("refreshes matching jobs without dropping queue metadata or other jobs", () => {
    expect(
      mergeRefreshedVectorIndexQueueItems(
        [
          queueItem("job-1", { knowledgeFileId: "file-1" }),
          queueItem("job-2", { knowledgeFileId: "file-2" }),
        ],
        [
          {
            id: "job-1",
            status: "failed",
            errorMessage: "向量写入失败",
            failureHint: "稍后重试",
          },
        ],
      ),
    ).toEqual([
      queueItem("job-1", {
        knowledgeFileId: "file-1",
        status: "failed",
        errorMessage: "向量写入失败",
        failureHint: "稍后重试",
      }),
      queueItem("job-2", { knowledgeFileId: "file-2" }),
    ]);
  });

  it("removes only jobs belonging to the permanently deleted file", () => {
    expect(
      removeVectorIndexQueueItemsForFile(
        [
          queueItem("job-1", { knowledgeFileId: "file-1" }),
          queueItem("job-2", { knowledgeFileId: "file-2" }),
          queueItem("job-3"),
        ],
        "file-1",
      ),
    ).toEqual([
      queueItem("job-2", { knowledgeFileId: "file-2" }),
      queueItem("job-3"),
    ]);
  });
});
