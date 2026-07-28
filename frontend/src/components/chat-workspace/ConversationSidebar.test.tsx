import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { ChatSession } from "../../lib/chat-workspace/types";
import {
  ConversationSidebar,
  type ConversationSidebarProps,
} from "./ConversationSidebar";

const sessions: ChatSession[] = [
  {
    id: "session-active",
    knowledgeBaseId: "kb-research",
    title: "活动会话",
    messages: [
      {
        role: "assistant",
        content: "最新研究结论",
      },
    ],
    messagesLoaded: true,
  },
  {
    id: "session-empty",
    knowledgeBaseId: "kb-research",
    title: "待研究主题",
    messages: [],
    messagesLoaded: true,
  },
];

const baseProps: ConversationSidebarProps = {
  sessions,
  activeSessionId: "session-active",
  isCreatingSession: false,
  editingSessionId: "",
  editingTitle: "",
  renamingSessionId: "",
  deletingSessionId: "",
  onCreateSession: () => undefined,
  onSelectSession: () => undefined,
  onStartRename: () => undefined,
  onEditingTitleChange: () => undefined,
  onSaveRename: () => undefined,
  onCancelRename: () => undefined,
  onDeleteSession: () => undefined,
};

describe("ConversationSidebar", () => {
  it("renders the empty state and padded session count", () => {
    const markup = renderToStaticMarkup(
      <ConversationSidebar {...baseProps} sessions={[]} />,
    );

    expect(markup).toContain("＋ 新建研究会话");
    expect(markup).toContain("Conversation Index");
    expect(markup).toContain(">00<");
    expect(markup).toContain("暂无会话，发送问题即可开始");
  });

  it("renders active state, message summaries, and fallback text", () => {
    const markup = renderToStaticMarkup(
      <ConversationSidebar {...baseProps} />,
    );

    expect(markup).toContain(">02<");
    expect(markup).toContain("活动会话");
    expect(markup).toContain("最新研究结论");
    expect(markup).toContain("待研究主题");
    expect(markup).toContain("暂无消息");
    expect(markup).toContain("border-[#e36b4f]");
  });

  it("renders rename and pending states", () => {
    const markup = renderToStaticMarkup(
      <ConversationSidebar
        {...baseProps}
        isCreatingSession
        editingSessionId="session-active"
        editingTitle="新的会话标题"
        renamingSessionId="session-active"
        deletingSessionId="session-empty"
      />,
    );

    expect(markup).toContain("创建中...");
    expect(markup).toContain('aria-label="重命名 活动会话"');
    expect(markup).toContain('value="新的会话标题"');
    expect(markup).toContain("保存中...");
    expect(markup).toContain("删除中...");
  });
});
