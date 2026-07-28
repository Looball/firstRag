import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import {
  ConversationMessageItem,
  type ConversationMessageItemProps,
} from "./ConversationMessageItem";

const baseProps: ConversationMessageItemProps = {
  messageKey: "session-1-0",
  message: {
    role: "user",
    content: "请总结报告",
  },
  position: 1,
  isLatestMessage: true,
  isCurrentSessionLoading: false,
  isAdvancedMode: false,
  isCopied: false,
  feedbackState: {
    isPanelOpen: false,
    isSubmitting: false,
    errorMessage: "",
    successMessage: "",
  },
  diagnosticState: {
    isExpanded: false,
    diagnostic: null,
    isLoading: false,
    hasLoaded: false,
    errorMessage: "",
  },
  evalDraftState: {
    isExporting: false,
    errorMessage: "",
  },
  sourceFeedbackState: {
    submitting: {},
    errors: {},
    messages: {},
  },
  onOpenSource: () => undefined,
  onSubmitSourceFeedback: () => undefined,
  onSubmitMessageFeedback: () => undefined,
  onToggleNegativeFeedback: () => undefined,
  onFeedbackReasonChange: () => undefined,
  onFeedbackNoteChange: () => undefined,
  onExportEvalDraft: () => undefined,
  onToggleDiagnostics: () => undefined,
  onCopy: () => undefined,
};

describe("ConversationMessageItem", () => {
  it("renders numbered user content without assistant actions", () => {
    const markup = renderToStaticMarkup(
      <ConversationMessageItem {...baseProps} position={7} />,
    );

    expect(markup).toContain("07");
    expect(markup).toContain("问题");
    expect(markup).toContain("请总结报告");
    expect(markup).not.toContain("复制回答");
  });

  it("renders the latest empty assistant message as a streaming placeholder", () => {
    const markup = renderToStaticMarkup(
      <ConversationMessageItem
        {...baseProps}
        message={{ role: "assistant", content: "" }}
        position={2}
        isCurrentSessionLoading
      />,
    );

    expect(markup).toContain("02");
    expect(markup).toContain("回答");
    expect(markup).toContain("AI 正在思考中...");
    expect(markup).not.toContain("复制回答");
  });

  it("renders retrieval empty state when no source is available", () => {
    const markup = renderToStaticMarkup(
      <ConversationMessageItem
        {...baseProps}
        message={{
          role: "assistant",
          content: "暂时没有足够资料。",
          retrieval: {
            need_retrieval: true,
            rewritten_query: "",
            reason: "",
            retrieved_count: 0,
            source_count: 0,
          },
        }}
      />,
    );

    expect(markup).toContain("已检索知识库，但没有找到高相关引用");
    expect(markup).toContain("复制回答");
  });

  it("composes source details and advanced assistant actions", () => {
    const markup = renderToStaticMarkup(
      <ConversationMessageItem
        {...baseProps}
        isAdvancedMode
        message={{
          id: "message-1",
          role: "assistant",
          content: "报告显示营收增长。",
          retrieval: {
            need_retrieval: true,
            rewritten_query: "营收增长",
            reason: "需要检索",
            retrieved_count: 4,
            source_count: 1,
          },
          sources: [
            {
              title: "年度报告",
              content: "营收同比增长。",
              metadata: "",
              index: 0,
            },
          ],
        }}
      />,
    );

    expect(markup).toContain("引用来源");
    expect(markup).toContain("年度报告");
    expect(markup).toContain("召回 4 段");
    expect(markup).toContain("有用");
    expect(markup).toContain("有问题");
    expect(markup).toContain("诊断");
    expect(markup).toContain("复制回答");
  });

  it("uses message feedback as the fallback for the negative draft", () => {
    const markup = renderToStaticMarkup(
      <ConversationMessageItem
        {...baseProps}
        isAdvancedMode
        message={{
          role: "assistant",
          content: "旧回答",
          feedback: {
            rating: "negative",
            reason: "hallucination",
            note: "事实不一致",
          },
        }}
        feedbackState={{
          ...baseProps.feedbackState,
          isPanelOpen: true,
        }}
      />,
    );

    expect(markup).toContain("已标记：有问题");
    expect(markup).toContain("疑似幻觉");
    expect(markup).toContain('value="事实不一致"');
  });
});
