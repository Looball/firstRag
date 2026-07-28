import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { DEFAULT_RETRIEVAL_SETTINGS } from "../../lib/chat-workspace/constants";
import {
  KnowledgeBaseManagerDialog,
  type KnowledgeBaseManagerDialogProps,
} from "./KnowledgeBaseManagerDialog";

const baseProps: KnowledgeBaseManagerDialogProps = {
  selectedKnowledgeBaseName: "研究资料",
  selectedKnowledgeBaseId: "kb-research",
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
  knowledgeBaseFiles: [
    {
      knowledgeBaseId: "kb-research",
      knowledgeFileId: "file-1",
    },
    {
      knowledgeBaseId: "kb-research",
      knowledgeFileId: "file-2",
    },
  ],
  sessions: [
    {
      id: "session-1",
      knowledgeBaseId: "kb-research",
      title: "研究会话",
      messages: [],
      messagesLoaded: true,
    },
  ],
  deletedKnowledgeBases: [],
  isLoadingDeletedKnowledgeBases: false,
  knowledgeBaseLifecycleMessage: "",
  knowledgeBaseLifecycleError: "",
  editingKnowledgeBaseId: "",
  editingKnowledgeBaseName: "",
  renamingKnowledgeBaseId: "",
  deletingKnowledgeBaseId: "",
  restoringKnowledgeBaseId: "",
  isAdvancedMode: false,
  selectedRetrievalSettings: DEFAULT_RETRIEVAL_SETTINGS,
  isLoadingRetrievalSettings: false,
  isSavingRetrievalSettings: false,
  retrievalSettingsMessage: "",
  retrievalSettingsError: "",
  newKnowledgeBaseName: "",
  isCreatingKnowledgeBase: false,
  onClose: () => undefined,
  onSelectKnowledgeBase: () => undefined,
  onStartRename: () => undefined,
  onEditingNameChange: () => undefined,
  onCancelRename: () => undefined,
  onSaveRename: () => undefined,
  onDeleteKnowledgeBase: () => undefined,
  onRestoreKnowledgeBase: () => undefined,
  onUpdateRetrievalSettings: () => undefined,
  onSaveRetrievalSettings: () => undefined,
  onNewKnowledgeBaseNameChange: () => undefined,
  onCreateKnowledgeBase: () => undefined,
};

describe("KnowledgeBaseManagerDialog", () => {
  it("renders the selected library, default marker, and local counts", () => {
    const markup = renderToStaticMarkup(
      <KnowledgeBaseManagerDialog {...baseProps} />,
    );

    expect(markup).toContain("当前：研究资料");
    expect(markup).toContain("默认知识库");
    expect(markup).toContain("默认");
    expect(markup).toContain("2 个文件 · 1 个会话");
    expect(markup).toContain("回收站为空");
  });

  it("renders deleted libraries and advanced retrieval settings", () => {
    const markup = renderToStaticMarkup(
      <KnowledgeBaseManagerDialog
        {...baseProps}
        deletedKnowledgeBases={[
          {
            id: "kb-deleted",
            name: "旧资料",
            isDefault: false,
            fileCount: 3,
            conversationCount: 2,
            deletedAt: "2026-07-28T00:00:00Z",
          },
        ]}
        isAdvancedMode
        selectedRetrievalSettings={{
          ...DEFAULT_RETRIEVAL_SETTINGS,
          retrievalMode: "always",
          enableRerank: true,
        }}
      />,
    );

    expect(markup).toContain("旧资料");
    expect(markup).toContain("3 个文件 · 2 个会话");
    expect(markup).toContain("Retrieval Policy");
    expect(markup).toContain("启用 Rerank 精排");
    expect(markup).toContain("保存检索设置");
  });
});
