import { describe, expect, it, vi } from "vitest";
import { FrontendApiError } from "@/lib/frontend-api";

import type { KnowledgeFile } from "./types";
import {
  buildKnowledgeFileUploadErrorMessage,
  buildKnowledgeFileUploadMessage,
} from "./use-knowledge-file-mutations";

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

/** 构造 mutation helper 测试使用的知识文件。 */
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

describe("useKnowledgeFileMutations helpers", () => {
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
