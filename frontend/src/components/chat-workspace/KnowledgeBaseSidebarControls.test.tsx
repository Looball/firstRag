import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import {
  KnowledgeBaseSidebarControls,
  type KnowledgeBaseSidebarControlsProps,
} from "./KnowledgeBaseSidebarControls";

const baseProps: KnowledgeBaseSidebarControlsProps = {
  knowledgeBases: [
    {
      id: "default",
      name: "默认知识库",
      isDefault: true,
      fileCount: 0,
    },
    {
      id: "kb-research",
      name: "研究资料",
      isDefault: false,
      fileCount: 7,
    },
  ],
  selectedKnowledgeBaseId: "kb-research",
  selectedFileCount: 7,
  isUploadingFiles: false,
  uploadRetryAfterSeconds: 0,
  fileInputRef: {
    current: null,
  },
  onSelectedKnowledgeBaseChange: () => undefined,
  onOpenKnowledgeBaseManager: () => undefined,
  onOpenFileManager: () => undefined,
  onFilesSelected: () => undefined,
};

describe("KnowledgeBaseSidebarControls", () => {
  it("renders an empty knowledge-base state and disables upload", () => {
    const markup = renderToStaticMarkup(
      <KnowledgeBaseSidebarControls
        {...baseProps}
        knowledgeBases={[]}
        selectedKnowledgeBaseId=""
        selectedFileCount={0}
      />,
    );

    expect(markup).toContain("暂无知识库");
    expect(markup).toContain("上传文件");
    expect(markup).toContain("disabled");
    expect(markup).toContain("文件 0");
  });

  it("renders knowledge-base options, file count, and upload input", () => {
    const markup = renderToStaticMarkup(
      <KnowledgeBaseSidebarControls {...baseProps} />,
    );

    expect(markup).toContain("默认知识库");
    expect(markup).toContain("研究资料");
    expect(markup).toContain("文件 7");
    expect(markup).toContain("multiple");
    expect(markup).toContain(
      'accept=".pdf,.docx,.md,.txt,.png,.jpg,.jpeg,.webp"',
    );
  });

  it("renders upload progress and Retry-After with retry taking priority", () => {
    const uploadingMarkup = renderToStaticMarkup(
      <KnowledgeBaseSidebarControls {...baseProps} isUploadingFiles />,
    );
    const retryMarkup = renderToStaticMarkup(
      <KnowledgeBaseSidebarControls
        {...baseProps}
        isUploadingFiles
        uploadRetryAfterSeconds={12}
      />,
    );

    expect(uploadingMarkup).toContain("上传中...");
    expect(retryMarkup).toContain("12 秒后重试");
    expect(retryMarkup).not.toContain("上传中...");
  });
});
