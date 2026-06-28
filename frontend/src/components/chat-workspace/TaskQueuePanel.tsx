import {
  getVectorIndexStatusText,
  getWorkerHealthDetailToneClass,
  getWorkerHealthDetails,
  getWorkerHealthToneClass,
  isVectorIndexJobDone,
} from "@/lib/chat-workspace/utils";
import type {
  VectorIndexHealthResponse,
  VectorIndexQueueItem,
} from "@/lib/chat-workspace/types";

type TaskQueuePanelProps = {
  isLoadingHealth: boolean;
  health: VectorIndexHealthResponse | null;
  healthError: string;
  queue: VectorIndexQueueItem[];
  onRefreshHealth: () => void | Promise<void>;
  onClearCompletedJobs: () => void;
};

export function TaskQueuePanel({
  isLoadingHealth,
  health,
  healthError,
  queue,
  onRefreshHealth,
  onClearCompletedJobs,
}: TaskQueuePanelProps) {
  const workerHealthDetails = getWorkerHealthDetails(health, healthError);
  const vectorQueueCount = health?.queue.total ?? queue.length;
  const hasCompletedJobs = queue.some(isVectorIndexJobDone);

  return (
    <div className="mt-6 border border-[#cbd5d1] bg-[#f7faf8]">
      <div className="flex items-center justify-between gap-4 border-b border-[#d5ded9] px-4 py-3">
        <div>
          <p className="font-utility text-[10px] font-semibold uppercase text-[#176b62]">
            任务队列
          </p>
          <p className="mt-1 text-xs text-[#72807b]">
            {isLoadingHealth ? "正在读取任务状态..." : workerHealthDetails.summary}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="font-utility text-[10px] text-[#72807b]">
            {String(vectorQueueCount).padStart(2, "0")}
          </span>
          <button
            type="button"
            onClick={() => void onRefreshHealth()}
            disabled={isLoadingHealth}
            className="text-xs font-semibold text-[#72807b] underline decoration-[#176b62] underline-offset-4 transition hover:text-[#176b62] disabled:cursor-not-allowed disabled:text-[#9aa5a0]"
          >
            {isLoadingHealth ? "刷新中" : "刷新"}
          </button>
          {hasCompletedJobs && (
            <button
              type="button"
              onClick={onClearCompletedJobs}
              className="text-xs font-semibold text-[#72807b] underline decoration-[#d9aa2f] underline-offset-4 transition hover:text-[#176b62]"
            >
              清除完成
            </button>
          )}
        </div>
      </div>

      <div className="border-b border-[#d5ded9] px-4 py-3">
        <div
          className={`border px-3 py-2 text-xs ${getWorkerHealthToneClass(
            workerHealthDetails.tone
          )}`}
        >
          <div className="flex flex-wrap items-start justify-between gap-2">
            <p className="font-semibold">{workerHealthDetails.summary}</p>
            <p className="font-utility text-[10px] uppercase">
              检查 {workerHealthDetails.checkedAtLabel}
            </p>
          </div>

          {workerHealthDetails.details.length > 0 && (
            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {workerHealthDetails.details.map((detail) => (
                <div
                  key={`${detail.label}-${detail.value}`}
                  className={`border px-2 py-2 ${getWorkerHealthDetailToneClass(
                    detail.tone
                  )}`}
                >
                  <p className="font-utility text-[10px] uppercase opacity-75">
                    {detail.label}
                  </p>
                  <p className="mt-1 font-semibold">{detail.value}</p>
                </div>
              ))}
            </div>
          )}

          {workerHealthDetails.suggestedActions.length > 0 && (
            <div className="mt-3 space-y-1">
              {workerHealthDetails.suggestedActions.map((action) => (
                <p key={action} className="text-[11px] font-semibold">
                  {action}
                </p>
              ))}
            </div>
          )}
        </div>
      </div>

      {queue.length > 0 ? (
        <div className="divide-y divide-[#d5ded9]">
          {queue.map((job) => {
            const isFailed = job.status === "failed";
            const isSucceeded = job.status === "succeeded";

            return (
              <div
                key={job.id}
                className="flex items-start justify-between gap-4 px-4 py-3"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-[#17201f]">
                    {job.targetName}
                  </p>
                  <p className="mt-1 font-utility text-[10px] uppercase text-[#72807b]">
                    {job.targetType === "file" ? "File" : "Knowledge Base"} ·{" "}
                    {job.id.slice(0, 8)}
                  </p>
                  {job.errorMessage && (
                    <p className="mt-2 text-xs text-[#9b3c29]">
                      {job.errorMessage}
                    </p>
                  )}
                  {job.failureHint && (
                    <p className="mt-1 text-xs font-semibold text-[#9b3c29]">
                      {job.failureHint}
                    </p>
                  )}
                </div>
                <span
                  className={`shrink-0 border px-2 py-1 text-xs font-semibold ${
                    isFailed
                      ? "border-[#e36b4f] bg-[#fff1ed] text-[#9b3c29]"
                      : isSucceeded
                        ? "border-[#176b62] bg-[#edf7f3] text-[#176b62]"
                        : "border-[#d9aa2f] bg-[#fff7df] text-[#7a5a12]"
                  }`}
                >
                  {getVectorIndexStatusText(job.status)}
                </span>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="px-4 py-5 text-center text-sm text-[#72807b]">
          暂无向量化任务
        </p>
      )}
    </div>
  );
}
