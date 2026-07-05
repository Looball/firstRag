import { describe, expect, it, vi } from "vitest";
import { FrontendApiError } from "@/lib/frontend-api";

import type {
  KnowledgeBaseFile,
  KnowledgeFile,
  VectorIndexQueueItem,
} from "./types";
import {
  buildKnowledgeFileUploadErrorMessage,
  buildKnowledgeFileUploadMessage,
  mergeKnowledgeFilesForKnowledgeBase,
  mergeVectorIndexQueueItems,
  replaceKnowledgeBaseFileAssociations,
} from "./use-knowledge-files";

vi.mock("@/lib/frontend-api", () => ({
  FrontendApiError: class FrontendApiError extends Error {
    status: number;

    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  },
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

  it("builds upload success message with duplicate and reuse hints", () => {
    expect(
      buildKnowledgeFileUploadMessage([
        knowledgeFile("file-a", { reused: true }),
        knowledgeFile("file-b", {
          reused: true,
          alreadyInKnowledgeBase: true,
        }),
      ]),
    ).toBe(
      "已处理 2 个文件。2 个文件复用已有上传记录。1 个文件已在当前知识库中。需要检索前，请点击“向量化”或“向量化当前知识库”。",
    );
  });

  it("adds user actions to common upload errors", () => {
    expect(
      buildKnowledgeFileUploadErrorMessage(
        new Error("不支持的文件类型：demo.exe"),
      ),
    ).toBe(
      "不支持的文件类型：demo.exe。当前支持 PDF、DOCX、Markdown、TXT、PNG、JPEG 和 WebP 文件。",
    );
    expect(
      buildKnowledgeFileUploadErrorMessage(
        new FrontendApiError("上传文件不能超过 20MB", 413),
      ),
    ).toBe(
      "上传文件不能超过 20MB。请压缩文件、拆分文档，或联系管理员调整上传上限。",
    );
  });
});
