import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import {
  ChatWorkspaceHeader,
  type ChatWorkspaceHeaderProps,
} from "./ChatWorkspaceHeader";

const baseProps: ChatWorkspaceHeaderProps = {
  knowledgeBaseName: "研究资料",
  sessionTitle: "季度报告分析",
  messageCount: 5,
  fileCount: 8,
};

describe("ChatWorkspaceHeader", () => {
  it("renders the active knowledge base and session title", () => {
    const markup = renderToStaticMarkup(
      <ChatWorkspaceHeader {...baseProps} />,
    );

    expect(markup).toContain("Live Research");
    expect(markup).toContain("研究资料");
    expect(markup).toContain("季度报告分析");
    expect(markup).toContain(
      "基于当前知识库继续提问，回答与上下文会保存在此会话中。",
    );
  });

  it("renders fallback labels when no knowledge base or session is active", () => {
    const markup = renderToStaticMarkup(
      <ChatWorkspaceHeader
        {...baseProps}
        knowledgeBaseName=""
        sessionTitle=""
      />,
    );

    expect(markup).toContain("暂无知识库");
    expect(markup).toContain("聊天工作台");
  });

  it("pads single-digit counts without truncating larger values", () => {
    const markup = renderToStaticMarkup(
      <ChatWorkspaceHeader {...baseProps} />,
    );
    const largeCountMarkup = renderToStaticMarkup(
      <ChatWorkspaceHeader {...baseProps} messageCount={128} fileCount={42} />,
    );

    expect(markup).toMatch(/消息<strong[^>]*>05<\/strong>/);
    expect(markup).toMatch(/文件<strong[^>]*>08<\/strong>/);
    expect(largeCountMarkup).toMatch(/消息<strong[^>]*>128<\/strong>/);
    expect(largeCountMarkup).toMatch(/文件<strong[^>]*>42<\/strong>/);
  });
});
