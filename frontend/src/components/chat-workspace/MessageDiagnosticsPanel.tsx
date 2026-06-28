import type { MessageDiagnostic } from "@/lib/chat-workspace/types";
import {
  formatDiagnosticCount,
  formatDiagnosticScore,
  formatDiagnosticTiming,
  formatDiagnosticValue,
  formatRetrievalDecision,
} from "@/lib/chat-workspace/utils";

type MessageDiagnosticsPanelProps = {
  messageKey: string;
  diagnostic: MessageDiagnostic | null;
  isLoading: boolean;
  hasLoadedDiagnostics: boolean;
  errorMessage: string;
};

function DiagnosticMetric({
  label,
  value,
  blockLabel = false,
}: {
  label: string;
  value: string | number;
  blockLabel?: boolean;
}) {
  return (
    <p>
      <span className={blockLabel ? "block text-[#72807b]" : "text-[#72807b]"}>
        {label}
      </span>
      {value}
    </p>
  );
}

function TimingGroup({
  title,
  metrics,
  gridClass,
}: {
  title: string;
  metrics: Array<[string, string]>;
  gridClass: string;
}) {
  return (
    <div>
      <p className="font-utility text-[10px] font-semibold uppercase text-[#72807b]">
        {title}
      </p>
      <div className={`mt-1 grid gap-2 ${gridClass}`}>
        {metrics.map(([label, value]) => (
          <DiagnosticMetric
            key={label}
            label={label}
            value={value}
            blockLabel
          />
        ))}
      </div>
    </div>
  );
}

export function MessageDiagnosticsPanel({
  messageKey,
  diagnostic,
  isLoading,
  hasLoadedDiagnostics,
  errorMessage,
}: MessageDiagnosticsPanelProps) {
  const diagnosticChannels = diagnostic
    ? diagnostic.retrievalSources.length > 0
      ? diagnostic.retrievalSources
      : diagnostic.diagnostics.retrievalSources
    : [];
  const diagnosticTiming = diagnostic?.diagnostics.timing;
  const finalNeedRetrieval = diagnostic
    ? (diagnostic.finalNeedRetrieval ?? diagnostic.needRetrieval)
    : null;

  return (
    <div className="mt-4 border-t border-[#d6dedb] pt-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-utility text-[10px] font-semibold uppercase text-[#64716d]">
          诊断
        </p>
        {diagnostic?.createdAt && (
          <p className="text-xs text-[#72807b]">{diagnostic.createdAt}</p>
        )}
      </div>

      {isLoading && !hasLoadedDiagnostics && (
        <p className="mt-2 text-xs text-[#64716d]">正在加载诊断信息...</p>
      )}

      {errorMessage && (
        <p className="mt-2 border border-[#f0b8a8] bg-[#fff1ed] px-3 py-2 text-xs text-[#9b3c29]">
          {errorMessage}
        </p>
      )}

      {!isLoading && !errorMessage && !diagnostic && (
        <div className="mt-2 border border-[#d5ded9] bg-[#fcfdfb] px-3 py-2 text-xs text-[#64716d]">
          <p className="font-semibold text-[#17201f]">暂无诊断信息</p>
          <p className="mt-1">
            常见原因：这是旧消息、本地问候短路回答、消息生成失败或被取消，或后端版本较旧。
          </p>
        </div>
      )}

      {diagnostic && (
        <div className="mt-2 space-y-3">
          <div className="grid gap-2 border border-[#d5ded9] bg-[#fcfdfb] px-3 py-2 text-xs text-[#46514e] md:grid-cols-2">
            <DiagnosticMetric
              label="最终决策："
              value={formatRetrievalDecision(finalNeedRetrieval)}
            />
            <DiagnosticMetric
              label="LLM 判断："
              value={formatRetrievalDecision(diagnostic.llmNeedRetrieval)}
            />
            <DiagnosticMetric
              label="规则覆盖："
              value={diagnostic.overrideApplied ? "是" : "否"}
            />
            <DiagnosticMetric
              label="向量降级："
              value={diagnostic.vectorDegraded ? "是" : "否"}
            />
            <DiagnosticMetric label="展示引用：" value={diagnostic.sourceCount} />
            <DiagnosticMetric
              label="最终引用通道："
              value={
                diagnosticChannels.length > 0
                  ? diagnosticChannels.join(" + ")
                  : "—"
              }
            />
            <p className="md:col-span-2">
              <span className="text-[#72807b]">改写问题：</span>
              {diagnostic.rewrittenQuery || "—"}
            </p>
            <p className="md:col-span-2">
              <span className="text-[#72807b]">LLM 原因：</span>
              {diagnostic.llmReason || diagnostic.reason || "—"}
            </p>
            <p className="md:col-span-2">
              <span className="text-[#72807b]">覆盖原因：</span>
              {diagnostic.overrideReason || "—"}
            </p>
          </div>

          <div className="grid gap-2 border border-[#d5ded9] bg-[#fcfdfb] px-3 py-2 text-xs text-[#46514e] md:grid-cols-4">
            <DiagnosticMetric
              label="Vector 召回"
              value={formatDiagnosticCount(diagnostic.diagnostics.vectorCount)}
              blockLabel
            />
            <DiagnosticMetric
              label="Fulltext 召回"
              value={formatDiagnosticCount(diagnostic.diagnostics.fulltextCount)}
              blockLabel
            />
            <DiagnosticMetric
              label="融合后"
              value={formatDiagnosticCount(diagnostic.diagnostics.fusedCount)}
              blockLabel
            />
            <DiagnosticMetric
              label="精排后"
              value={formatDiagnosticCount(diagnostic.diagnostics.rerankedCount)}
              blockLabel
            />
          </div>

          <div className="border border-[#d5ded9] bg-[#fcfdfb] px-3 py-2 text-xs text-[#46514e]">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="font-utility text-[10px] font-semibold uppercase text-[#64716d]">
                LLM
              </p>
              <p className="max-w-full truncate text-[11px] text-[#72807b]">
                {formatDiagnosticValue(diagnostic.diagnostics.llm.baseUrl)}
              </p>
            </div>
            <div className="mt-2 grid gap-2 md:grid-cols-4">
              {[
                ["Provider", diagnostic.diagnostics.llm.provider],
                ["Model", diagnostic.diagnostics.llm.model],
                ["Key 来源", diagnostic.diagnostics.llm.credentialMode],
                ["Temperature", diagnostic.diagnostics.llm.temperature],
                ["Max tokens", diagnostic.diagnostics.llm.maxTokens],
                ["Prompt tokens", diagnostic.diagnostics.llm.promptTokens],
                [
                  "Completion tokens",
                  diagnostic.diagnostics.llm.completionTokens,
                ],
                ["Total tokens", diagnostic.diagnostics.llm.totalTokens],
              ].map(([label, value]) => (
                <DiagnosticMetric
                  key={String(label)}
                  label={String(label)}
                  value={formatDiagnosticValue(value)}
                  blockLabel
                />
              ))}
            </div>
          </div>

          <div className="border border-[#d5ded9] bg-[#fcfdfb] px-3 py-2 text-xs text-[#46514e]">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="font-utility text-[10px] font-semibold uppercase text-[#64716d]">
                耗时分析
              </p>
              <p className="text-[11px] text-[#72807b]">
                总耗时 {formatDiagnosticTiming(diagnosticTiming?.chatStreamTotalMs)}
              </p>
            </div>
            <div className="mt-3 space-y-3">
              <TimingGroup
                title="Decision"
                gridClass="md:grid-cols-5"
                metrics={[
                  [
                    "问题改写",
                    formatDiagnosticTiming(diagnosticTiming?.standaloneQuestionMs),
                  ],
                  [
                    "读取配置",
                    formatDiagnosticTiming(diagnosticTiming?.retrievalSettingsMs),
                  ],
                  [
                    "知识画像",
                    formatDiagnosticTiming(diagnosticTiming?.knowledgeProfileMs),
                  ],
                  ["Router", formatDiagnosticTiming(diagnosticTiming?.queryRouterMs)],
                  [
                    "最终决策",
                    formatDiagnosticTiming(diagnosticTiming?.finalizeDecisionMs),
                  ],
                ]}
              />
              <TimingGroup
                title="Retrieval"
                gridClass="md:grid-cols-4 lg:grid-cols-7"
                metrics={[
                  [
                    "检索调用",
                    formatDiagnosticTiming(diagnosticTiming?.retrieveDocumentsMs),
                  ],
                  ["Embedding", formatDiagnosticTiming(diagnosticTiming?.embeddingMs)],
                  ["Vector", formatDiagnosticTiming(diagnosticTiming?.vectorMs)],
                  ["Fulltext", formatDiagnosticTiming(diagnosticTiming?.fulltextMs)],
                  ["RRF", formatDiagnosticTiming(diagnosticTiming?.rrfMs)],
                  ["Rerank", formatDiagnosticTiming(diagnosticTiming?.rerankMs)],
                  [
                    "检索总计",
                    formatDiagnosticTiming(diagnosticTiming?.retrievalTotalMs),
                  ],
                ]}
              />
              <TimingGroup
                title="Answer"
                gridClass="md:grid-cols-4"
                metrics={[
                  [
                    "回答前",
                    formatDiagnosticTiming(diagnosticTiming?.preAnswerTotalMs),
                  ],
                  [
                    "首 token",
                    formatDiagnosticTiming(diagnosticTiming?.firstAnswerTokenMs),
                  ],
                  [
                    "输出耗时",
                    formatDiagnosticTiming(diagnosticTiming?.answerStreamMs),
                  ],
                  [
                    "总耗时",
                    formatDiagnosticTiming(diagnosticTiming?.chatStreamTotalMs),
                  ],
                ]}
              />
            </div>
          </div>

          {diagnostic.vectorDegraded && (
            <div className="border border-[#f0b8a8] bg-[#fff1ed] px-3 py-2 text-xs text-[#9b3c29]">
              <p>向量检索发生降级，已尝试使用全文检索兜底。</p>
              {diagnostic.diagnostics.vectorErrors.length > 0 && (
                <ul className="mt-1 list-disc space-y-1 pl-4">
                  {diagnostic.diagnostics.vectorErrors.map((error) => (
                    <li key={error}>{error}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {diagnostic.sourcesPreview.length > 0 && (
            <div className="space-y-2">
              <p className="font-utility text-[10px] font-semibold uppercase text-[#64716d]">
                Sources 预览
              </p>
              {diagnostic.sourcesPreview.map((source, sourceIndex) => (
                <div
                  key={`${messageKey}-diagnostic-source-${sourceIndex}`}
                  className="border border-[#d5ded9] bg-[#fcfdfb] px-3 py-2 text-xs text-[#46514e]"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <p className="font-semibold text-[#17201f]">
                      {source.index !== null ? `${source.index}. ` : ""}
                      {source.fileName || "未知来源"}
                    </p>
                    <p className="font-utility text-[10px] text-[#72807b]">
                      文件片段{" "}
                      {source.chunkIndex !== null ? `#${source.chunkIndex}` : "—"}
                    </p>
                  </div>
                  <p className="mt-1 text-[#64716d]">
                    通道：
                    {source.retrievalSources.length > 0
                      ? source.retrievalSources.join(" + ")
                      : "—"}
                  </p>
                  <p className="mt-1 text-[#64716d]">
                    RRF：{formatDiagnosticScore(source.rrfScore)} · 向量距离：
                    {formatDiagnosticScore(source.vectorScore)} · 文本分：
                    {formatDiagnosticScore(source.fulltextScore)} · 相关性：
                    {formatDiagnosticScore(source.rerankScore)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
