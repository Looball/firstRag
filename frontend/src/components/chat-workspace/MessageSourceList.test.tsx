import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { ChatSource } from "../../lib/chat-workspace/types";
import {
  MessageSourceList,
  type MessageSourceListProps,
} from "./MessageSourceList";

const sources: ChatSource[] = [
  {
    title: "年度报告",
    content: "营收同比增长，研发投入保持稳定。",
    metadata: "section: results",
    index: 4,
    fileId: "file-report",
    fileName: "annual-report.pdf",
    fileType: "pdf",
    chunkIndex: 12,
    pageNumber: 8,
    pageCount: 20,
    pdfParseMethod: "ocr",
    ocrConfidence: 0.91,
    ocrCorrectionApplied: true,
    ocrCorrectionRevision: 2,
    retrievalSources: ["vector", "fulltext"],
    vectorScore: 0.81234,
    fulltextScore: 0.71234,
    rerankScore: 0.91234,
    rrfScore: 0.11234,
  },
];

const baseProps: MessageSourceListProps = {
  messageKey: "session-1-2",
  sources,
  displaySourceCount: 1,
  retrievedCount: 8,
  isAdvancedMode: false,
  submittingFeedback: {},
  feedbackErrors: {},
  feedbackMessages: {},
  onOpenSource: () => undefined,
  onSubmitFeedback: () => undefined,
};

describe("MessageSourceList", () => {
  it("renders source content, file metadata, and preview entry", () => {
    const markup = renderToStaticMarkup(
      <MessageSourceList {...baseProps} />,
    );

    expect(markup).toContain("引用来源");
    expect(markup).toContain("可展示 1 条");
    expect(markup).toContain("年度报告");
    expect(markup).toContain("营收同比增长");
    expect(markup).toContain("第 8 / 20 页");
    expect(markup).toContain("已人工校对");
    expect(markup).toContain("修订 #2");
    expect(markup).toContain("annual-report.pdf");
    expect(markup).toContain("查看原文");
    expect(markup).not.toContain("召回 8 段");
  });

  it("renders advanced retrieval diagnostics and source feedback controls", () => {
    const markup = renderToStaticMarkup(
      <MessageSourceList {...baseProps} isAdvancedMode />,
    );

    expect(markup).toContain("召回 8 段");
    expect(markup).toContain("Chunk #12");
    expect(markup).toContain("vector / fulltext");
    expect(markup).toContain("Vector 0.8123");
    expect(markup).toContain("Fulltext 0.7123");
    expect(markup).toContain("Rerank 0.9123");
    expect(markup).toContain("RRF 0.1123");
    expect(markup).toContain("section: results");
    expect(markup).toContain("file-report");
    expect(markup).toContain("引用有用");
    expect(markup).toContain("引用无关");
  });

  it("renders saved, submitting, success, and error feedback states", () => {
    const savedMarkup = renderToStaticMarkup(
      <MessageSourceList
        {...baseProps}
        isAdvancedMode
        sources={[
          {
            ...sources[0],
            feedback: {
              rating: "useful",
              sourceIndex: 4,
            },
          },
        ]}
      />,
    );
    const sourceKey = "session-1-2-source-4";
    const submittingMarkup = renderToStaticMarkup(
      <MessageSourceList
        {...baseProps}
        isAdvancedMode
        submittingFeedback={{ [sourceKey]: true }}
      />,
    );
    const successMarkup = renderToStaticMarkup(
      <MessageSourceList
        {...baseProps}
        isAdvancedMode
        feedbackMessages={{ [sourceKey]: "已保存" }}
      />,
    );
    const errorMarkup = renderToStaticMarkup(
      <MessageSourceList
        {...baseProps}
        isAdvancedMode
        feedbackErrors={{ [sourceKey]: "保存失败" }}
        feedbackMessages={{ [sourceKey]: "不应展示" }}
      />,
    );

    expect(savedMarkup).toContain("已标记：引用有用");
    expect(submittingMarkup).toContain("保存中");
    expect(submittingMarkup).toContain('disabled=""');
    expect(successMarkup).toContain("已保存");
    expect(errorMarkup).toContain("保存失败");
    expect(errorMarkup).not.toContain("不应展示");
  });
});
