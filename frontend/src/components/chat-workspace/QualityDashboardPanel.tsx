"use client";

import type { QualityDashboard } from "../../lib/chat-workspace/types";

export type QualityDashboardPanelProps = {
  isOpen: boolean;
  dashboard: QualityDashboard | null;
  isLoading: boolean;
  error: string;
  onToggle: () => void | Promise<void>;
  onRefresh: () => void | Promise<void>;
};

/**
 * 将比例格式化为整数百分比。
 */
function formatPercent(value: number | null) {
  return typeof value === "number" && Number.isFinite(value)
    ? `${Math.round(value * 100)}%`
    : "—";
}

/**
 * 将可选数值格式化为固定小数位。
 */
function formatMetricNumber(value: number | null, digits = 1) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "—";
  }

  return value.toFixed(digits);
}

/**
 * 将毫秒指标格式化为适合展示的时长。
 */
function formatMetricMs(value: number | null) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "—";
  }

  return value >= 1000
    ? `${(value / 1000).toFixed(2)}s`
    : `${value.toFixed(0)}ms`;
}

/**
 * 展示高级模式的质量指标、空数据说明和反馈分布。
 *
 * 质量数据请求和 lifecycle state 由上层 hook 管理，组件只负责渲染并转发操作。
 */
export function QualityDashboardPanel({
  isOpen,
  dashboard,
  isLoading,
  error,
  onToggle,
  onRefresh,
}: QualityDashboardPanelProps) {
  return (
    <div className="border-b border-[#c7d1cd] py-4">
      <div className="flex items-center justify-between gap-3">
        <p className="font-utility text-[10px] font-semibold uppercase text-[#72807b]">
          Quality
        </p>
        <button
          type="button"
          onClick={() => {
            void onToggle();
          }}
          className="text-xs font-semibold text-[#176b62] underline decoration-[#d5a83b] decoration-2 underline-offset-4"
        >
          {isOpen ? "收起" : "质量看板"}
        </button>
      </div>

      {isOpen && (
        <div className="mt-3 border border-[#d5ded9] bg-[#f8faf8] p-3 text-xs text-[#46514e]">
          <div className="flex items-center justify-between gap-2">
            <p className="font-utility text-[10px] font-semibold uppercase text-[#64716d]">
              最近 {dashboard?.windowDays ?? 7} 天
            </p>
            <button
              type="button"
              disabled={isLoading}
              onClick={() => {
                void onRefresh();
              }}
              className="font-utility text-[10px] font-semibold uppercase text-[#176b62] disabled:opacity-60"
            >
              {isLoading ? "加载中" : "刷新"}
            </button>
          </div>

          {error && <p className="mt-3 text-[#9b3c29]">{error}</p>}

          {!error && !isLoading && !dashboard?.hasFeedback && (
            <p className="mt-3 leading-5 text-[#64716d]">
              还没有回答或引用反馈。这里不会把空数据当成质量良好。
            </p>
          )}

          {dashboard?.hasFeedback && (
            <div className="mt-3 grid gap-3">
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <p className="text-[10px] text-[#72807b]">反馈</p>
                  <p className="font-display text-lg font-semibold text-[#17201f]">
                    {dashboard.messageFeedback.total}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] text-[#72807b]">负反馈</p>
                  <p className="font-display text-lg font-semibold text-[#9b3c29]">
                    {formatPercent(dashboard.messageFeedback.negativeRate)}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] text-[#72807b]">引用无关</p>
                  <p className="font-display text-lg font-semibold text-[#9b3c29]">
                    {formatPercent(dashboard.sourceFeedback.irrelevantRate)}
                  </p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2 border-t border-[#d5ded9] pt-3">
                <div>
                  <p className="text-[10px] text-[#72807b]">平均引用</p>
                  <p className="font-semibold text-[#17201f]">
                    {formatMetricNumber(dashboard.retrieval.averageSources)}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] text-[#72807b]">首 token</p>
                  <p className="font-semibold text-[#17201f]">
                    {formatMetricMs(dashboard.retrieval.averageFirstTokenMs)}
                  </p>
                </div>
              </div>
              {dashboard.messageFeedback.reasonDistribution.length > 0 && (
                <div className="border-t border-[#d5ded9] pt-3">
                  <p className="font-utility text-[10px] font-semibold uppercase text-[#64716d]">
                    负反馈原因
                  </p>
                  <div className="mt-2 space-y-1">
                    {dashboard.messageFeedback.reasonDistribution.map(
                      (item) => (
                        <p
                          key={item.reason}
                          className="flex justify-between gap-3"
                        >
                          <span className="truncate">{item.reason}</span>
                          <span>{item.count}</span>
                        </p>
                      ),
                    )}
                  </div>
                </div>
              )}
              {dashboard.sourceFeedback.topIrrelevantFiles.length > 0 && (
                <div className="border-t border-[#d5ded9] pt-3">
                  <p className="font-utility text-[10px] font-semibold uppercase text-[#64716d]">
                    无关引用来源
                  </p>
                  <div className="mt-2 space-y-1">
                    {dashboard.sourceFeedback.topIrrelevantFiles.map((item) => (
                      <p
                        key={item.fileName}
                        className="flex justify-between gap-3"
                      >
                        <span className="truncate">{item.fileName}</span>
                        <span>{item.count}</span>
                      </p>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
