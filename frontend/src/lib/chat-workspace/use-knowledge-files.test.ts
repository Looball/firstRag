import { describe, expect, it, vi } from "vitest";

import type {
  KnowledgeBaseFile,
  KnowledgeFile,
  VectorIndexQueueItem,
} from "./types";
import {
  mergeKnowledgeFilesForKnowledgeBase,
  mergeVectorIndexQueueItems,
  replaceKnowledgeBaseFileAssociations,
} from "./use-knowledge-files";

vi.mock("@/lib/frontend-api", () => ({
  authenticatedFetch: vi.fn(),
  authenticatedJson: vi.fn(),
  authenticatedText: vi.fn(),
}));

function knowledgeFile(
  id: string,
  overrides: Partial<KnowledgeFile> = {},
): KnowledgeFile {
  return {
    id,
    name: `${id}.md`,
    size: 10,
    fingerprint: `${id}:10`,
    status: "pending",
    latestIndexJob: null,
    usageCount: null,
    ...overrides,
  };
}

describe("useKnowledgeFiles helpers", () => {
  it("merges loaded knowledge base files and preserves known usage counts", () => {
    const previousFiles = [
      knowledgeFile("file-a", { usageCount: 3 }),
      knowledgeFile("file-b", { usageCount: 1 }),
    ];
    const loadedFiles = [
      knowledgeFile("file-a", { name: "updated.md", usageCount: null }),
      knowledgeFile("file-c", { usageCount: 2 }),
    ];

    expect(
      mergeKnowledgeFilesForKnowledgeBase(previousFiles, loadedFiles),
    ).toEqual([
      knowledgeFile("file-a", { name: "updated.md", usageCount: 3 }),
      knowledgeFile("file-c", { usageCount: 2 }),
      knowledgeFile("file-b", { usageCount: 1 }),
    ]);
  });

  it("replaces only the selected knowledge base file associations", () => {
    const previousAssociations: KnowledgeBaseFile[] = [
      { knowledgeBaseId: "kb-1", knowledgeFileId: "file-old" },
      { knowledgeBaseId: "kb-2", knowledgeFileId: "file-other" },
    ];

    expect(
      replaceKnowledgeBaseFileAssociations(previousAssociations, "kb-1", [
        knowledgeFile("file-new"),
      ]),
    ).toEqual([
      { knowledgeBaseId: "kb-2", knowledgeFileId: "file-other" },
      { knowledgeBaseId: "kb-1", knowledgeFileId: "file-new" },
    ]);
  });

  it("updates vector index queue jobs while keeping existing target labels", () => {
    const previousJobs: VectorIndexQueueItem[] = [
      {
        id: "job-1",
        status: "queued",
        errorMessage: "",
        failureHint: "",
        targetName: "合同.md",
        targetType: "file",
      },
    ];

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
      {
        id: "job-1",
        status: "succeeded",
        errorMessage: "",
        failureHint: "",
        targetName: "合同.md",
        targetType: "file",
      },
      {
        id: "job-2",
        status: "queued",
        errorMessage: "",
        failureHint: "",
        targetName: "当前知识库",
        targetType: "knowledge-base",
      },
    ]);
  });
});
