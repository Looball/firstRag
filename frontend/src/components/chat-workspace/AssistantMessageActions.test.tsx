import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import {
  AssistantMessageActions,
  type AssistantMessageActionsProps,
} from "./AssistantMessageActions";

const baseProps: AssistantMessageActionsProps = {
  messageKey: "session-1-2",
  feedbackReason: "missing_answer",
  feedbackNote: "",
  isAdvancedMode: false,
  isFeedbackPanelOpen: false,
  isFeedbackSubmitting: false,
  feedbackError: "",
  feedbackMessage: "",
  canExportEvalDraft: false,
  isExportingEvalDraft: false,
  evalDraftError: "",
  isDiagnosticExpanded: false,
  diagnostic: null,
  isDiagnosticLoading: false,
  hasLoadedDiagnostics: false,
  diagnosticError: "",
  isCopied: false,
  onPositiveFeedback: () => undefined,
  onToggleNegativeFeedback: () => undefined,
  onFeedbackReasonChange: () => undefined,
  onFeedbackNoteChange: () => undefined,
  onSubmitNegativeFeedback: () => undefined,
  onExportEvalDraft: () => undefined,
  onToggleDiagnostics: () => undefined,
  onCopy: () => undefined,
};

describe("AssistantMessageActions", () => {
  it("keeps normal mode focused on copying the answer", () => {
    const markup = renderToStaticMarkup(
      <AssistantMessageActions {...baseProps} />,
    );

    expect(markup).toContain("复制回答");
    expect(markup).not.toContain("有用");
    expect(markup).not.toContain("有问题");
    expect(markup).not.toContain("诊断");
    expect(markup).not.toContain("Eval 草稿");
  });

  it("renders advanced feedback and diagnostics controls", () => {
    const markup = renderToStaticMarkup(
      <AssistantMessageActions {...baseProps} isAdvancedMode />,
    );

    expect(markup).toContain("有用");
    expect(markup).toContain("有问题");
    expect(markup).toContain("诊断");
    expect(markup).toContain("复制回答");
  });

  it("renders negative feedback draft and error state", () => {
    const markup = renderToStaticMarkup(
      <AssistantMessageActions
        {...baseProps}
        isAdvancedMode
        isFeedbackPanelOpen
        feedbackReason="hallucination"
        feedbackNote="引用与结论不一致"
        feedbackError="请检查后重试"
      />,
    );

    expect(markup).toContain("疑似幻觉");
    expect(markup).toContain('value="hallucination" selected=""');
    expect(markup).toContain('value="引用与结论不一致"');
    expect(markup).toContain("请检查后重试");
    expect(markup).toContain("提交反馈");
  });

  it("renders saved, export, copied, and expanded diagnostics states", () => {
    const markup = renderToStaticMarkup(
      <AssistantMessageActions
        {...baseProps}
        isAdvancedMode
        feedbackRating="negative"
        canExportEvalDraft
        isDiagnosticExpanded
        hasLoadedDiagnostics
        isCopied
      />,
    );

    expect(markup).toContain("已标记：有问题");
    expect(markup).toContain("Eval 草稿");
    expect(markup).toContain("收起诊断");
    expect(markup).toContain("暂无诊断信息");
    expect(markup).toContain("已复制");
  });

  it("renders submitting and eval export failure states", () => {
    const markup = renderToStaticMarkup(
      <AssistantMessageActions
        {...baseProps}
        isAdvancedMode
        isFeedbackSubmitting
        canExportEvalDraft
        isExportingEvalDraft
        evalDraftError="导出失败"
      />,
    );

    expect(markup).toContain("保存中");
    expect(markup).toContain("导出中");
    expect(markup).toContain("导出失败");
    expect(markup).toContain('disabled=""');
  });
});
