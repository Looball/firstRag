import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { QualityDashboard } from "../../lib/chat-workspace/types";
import {
  QualityDashboardPanel,
  type QualityDashboardPanelProps,
} from "./QualityDashboardPanel";

const dashboard: QualityDashboard = {
  windowDays: 14,
  hasFeedback: true,
  messageFeedback: {
    total: 8,
    positive: 5,
    negative: 3,
    negativeRate: 0.375,
    reasonDistribution: [
      {
        reason: "没有答到点",
        count: 2,
      },
    ],
  },
  sourceFeedback: {
    total: 10,
    useful: 7,
    irrelevant: 3,
    irrelevantRate: 0.3,
    topIrrelevantFiles: [
      {
        fileName: "旧资料.pdf",
        count: 2,
      },
    ],
  },
  retrieval: {
    assistantMessages: 9,
    averageSources: 2.5,
    averageFirstTokenMs: 1250,
  },
};

const baseProps: QualityDashboardPanelProps = {
  isOpen: true,
  dashboard,
  isLoading: false,
  error: "",
  onToggle: () => undefined,
  onRefresh: () => undefined,
};

describe("QualityDashboardPanel", () => {
  it("renders only the toggle while closed", () => {
    const markup = renderToStaticMarkup(
      <QualityDashboardPanel {...baseProps} isOpen={false} />,
    );

    expect(markup).toContain("Quality");
    expect(markup).toContain("质量看板");
    expect(markup).not.toContain("最近 14 天");
  });

  it("renders the loading state with the default window", () => {
    const markup = renderToStaticMarkup(
      <QualityDashboardPanel
        {...baseProps}
        dashboard={null}
        isLoading
      />,
    );

    expect(markup).toContain("最近 7 天");
    expect(markup).toContain("加载中");
    expect(markup).toContain("disabled");
    expect(markup).not.toContain("还没有回答或引用反馈");
  });

  it("renders an error instead of the empty state", () => {
    const markup = renderToStaticMarkup(
      <QualityDashboardPanel
        {...baseProps}
        dashboard={null}
        error="加载质量看板失败"
      />,
    );

    expect(markup).toContain("加载质量看板失败");
    expect(markup).not.toContain("还没有回答或引用反馈");
  });

  it("does not treat missing feedback as good quality", () => {
    const markup = renderToStaticMarkup(
      <QualityDashboardPanel
        {...baseProps}
        dashboard={{
          ...dashboard,
          hasFeedback: false,
        }}
      />,
    );

    expect(markup).toContain(
      "还没有回答或引用反馈。这里不会把空数据当成质量良好。",
    );
  });

  it("renders metrics and feedback distributions", () => {
    const markup = renderToStaticMarkup(
      <QualityDashboardPanel {...baseProps} />,
    );

    expect(markup).toContain("最近 14 天");
    expect(markup).toContain(">8<");
    expect(markup).toContain("38%");
    expect(markup).toContain("30%");
    expect(markup).toContain("2.5");
    expect(markup).toContain("1.25s");
    expect(markup).toContain("没有答到点");
    expect(markup).toContain("旧资料.pdf");
  });
});
