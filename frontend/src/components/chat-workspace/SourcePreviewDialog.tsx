"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import * as chatApi from "@/lib/chat-workspace/api";
import type { ChatSource } from "@/lib/chat-workspace/types";
import {
  buildOriginalFilePreviewUrl,
  formatOcrConfidence,
  formatSourcePosition,
} from "@/lib/chat-workspace/utils";

type SourcePreviewDialogProps = {
  source: ChatSource;
  onClose: () => void;
};

const LOCATION_KEYS = ["h1", "h2", "h3", "h4", "h5", "h6"];

/** 将 chunk 标题层级和可用页码格式化为可读定位信息。 */
function formatChunkLocation(location: Record<string, string | number>) {
  const headings = LOCATION_KEYS.map((key) => location[key])
    .filter((value): value is string | number => value !== undefined)
    .map(String);
  const position = formatSourcePosition({
    pageNumber:
      typeof (location.page_number ?? location.page) === "number"
        ? Number(location.page_number ?? location.page)
        : undefined,
    pageCount:
      typeof location.page_count === "number"
        ? location.page_count
        : undefined,
    paragraphStart:
      typeof location.paragraph_start === "number"
        ? location.paragraph_start
        : undefined,
    paragraphEnd:
      typeof location.paragraph_end === "number"
        ? location.paragraph_end
        : undefined,
  });

  if (position) {
    headings.push(position);
  }
  if (location.pdf_parse_method === "ocr") {
    const confidence =
      typeof location.ocr_confidence === "number"
        ? formatOcrConfidence(location.ocr_confidence)
        : "";
    headings.push(
      location.ocr_quality === "low"
        ? `OCR 质量较低${confidence ? ` ${confidence}` : ""}`
        : `OCR 识别${confidence ? ` ${confidence}` : ""}`,
    );
  }

  return headings.join(" / ");
}

/** 展示引用目标 chunk、相邻上下文和原始文件入口。 */
export function SourcePreviewDialog({
  source,
  onClose,
}: SourcePreviewDialogProps) {
  const targetChunkRef = useRef<HTMLElement | null>(null);
  const [isOpeningFile, setIsOpeningFile] = useState(false);
  const [fileOpenError, setFileOpenError] = useState("");
  const [ocrReindexJobId, setOcrReindexJobId] = useState("");
  const fileId = source.fileId || "";
  const chunkIndex = source.chunkIndex;
  const canLoadPreview = Boolean(fileId) && chunkIndex !== undefined;
  const previewQuery = useQuery({
    queryKey: [
      "knowledge-source-preview",
      fileId,
      chunkIndex,
      source.indexVersion,
      1,
    ],
    queryFn: () =>
      chatApi.loadKnowledgeSourcePreview(
        fileId,
        chunkIndex!,
        1,
        source.indexVersion,
      ),
    enabled: canLoadPreview,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
  const targetChunk = previewQuery.data?.chunks.find((chunk) => chunk.isTarget);
  const targetPageNumber =
    source.pageNumber ??
    (typeof targetChunk?.location.page_number === "number"
      ? targetChunk.location.page_number
      : undefined);
  const sourcePosition = formatSourcePosition({
    pageNumber: targetPageNumber,
    pageCount:
      source.pageCount ??
      (typeof targetChunk?.location.page_count === "number"
        ? targetChunk.location.page_count
        : undefined),
    paragraphStart:
      source.paragraphStart ??
      (typeof targetChunk?.location.paragraph_start === "number"
        ? targetChunk.location.paragraph_start
        : undefined),
    paragraphEnd:
      source.paragraphEnd ??
      (typeof targetChunk?.location.paragraph_end === "number"
        ? targetChunk.location.paragraph_end
        : undefined),
  });
  const targetIsOcrPage = targetChunk?.location.pdf_parse_method === "ocr";
  const targetOcrConfidence =
    typeof targetChunk?.location.ocr_confidence === "number"
      ? targetChunk.location.ocr_confidence
      : undefined;
  const targetOcrQuality =
    typeof targetChunk?.location.ocr_quality === "string"
      ? targetChunk.location.ocr_quality
      : "";
  const targetOcrConfidenceLabel = formatOcrConfidence(targetOcrConfidence);
  const ocrReindexMutation = useMutation({
    mutationFn: () =>
      chatApi.reindexKnowledgeFileOcrPage(fileId, targetPageNumber!),
    onSuccess: (job) => setOcrReindexJobId(job.id),
  });
  const ocrReindexJobQuery = useQuery({
    queryKey: ["pdf-ocr-page-reindex", ocrReindexJobId],
    queryFn: () => chatApi.getVectorIndexJob(ocrReindexJobId),
    enabled: Boolean(ocrReindexJobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "processing" ? 1_000 : false;
    },
  });
  const ocrReindexJob = ocrReindexJobQuery.data;
  const ocrReindexIsActive =
    ocrReindexMutation.isPending ||
    ocrReindexJob?.status === "queued" ||
    ocrReindexJob?.status === "processing";
  const ocrReindexError =
    ocrReindexMutation.error instanceof Error
      ? ocrReindexMutation.error.message
      : ocrReindexJobQuery.error instanceof Error
        ? ocrReindexJobQuery.error.message
        : ocrReindexJob?.status === "failed"
          ? ocrReindexJob.errorMessage ||
            ocrReindexJob.failureHint ||
            "OCR 重新识别失败，请稍后重试。"
          : "";

  /** 根据失败来源重试提交或仅重试任务状态查询，避免重复创建任务。 */
  function handleOcrReindex() {
    if (ocrReindexJobQuery.isError && ocrReindexJobId) {
      void ocrReindexJobQuery.refetch();
      return;
    }
    if (ocrReindexJob?.status === "failed") {
      setOcrReindexJobId("");
      ocrReindexMutation.reset();
    }
    ocrReindexMutation.mutate();
  }

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    if (previewQuery.data) {
      targetChunkRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    }
  }, [previewQuery.data]);

  /** 先同步打开空白页，再异步加载带 Authorization 的原始文件。 */
  async function handleOpenOriginalFile() {
    if (!fileId || isOpeningFile) {
      return;
    }

    const fileWindow = window.open("about:blank", "_blank");
    if (!fileWindow) {
      setFileOpenError("浏览器阻止了新窗口，请允许弹窗后重试。");
      return;
    }
    fileWindow.opener = null;
    setIsOpeningFile(true);
    setFileOpenError("");

    try {
      const blob = await chatApi.loadKnowledgeFileContent(fileId);
      const objectUrl = URL.createObjectURL(blob);
      fileWindow.location.href = buildOriginalFilePreviewUrl(
        objectUrl,
        blob.type || previewQuery.data?.mimeType || "",
        targetPageNumber,
      );
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
    } catch (error) {
      fileWindow.close();
      setFileOpenError(
        error instanceof Error ? error.message : "打开原始文件失败，请稍后再试。",
      );
    } finally {
      setIsOpeningFile(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center bg-[#17201f]/55 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="source-preview-title"
    >
      <div className="flex max-h-[88vh] w-full max-w-4xl flex-col border border-[#bccac5] bg-[#f8faf7] shadow-2xl">
        <header className="flex items-start justify-between gap-4 border-b border-[#ccd7d3] px-5 py-4">
          <div className="min-w-0">
            <p className="font-utility text-[10px] font-semibold uppercase tracking-[0.18em] text-[#176b62]">
              Source Context
            </p>
            <h2
              id="source-preview-title"
              className="mt-1 truncate text-xl font-semibold text-[#17201f]"
            >
              {previewQuery.data?.fileName || source.fileName || source.title}
            </h2>
            <p className="mt-1 text-xs text-[#64716d]">
              {sourcePosition ? `${sourcePosition} · ` : ""}
              精确定位 Chunk #{chunkIndex ?? "未知"}，并展示相邻上下文
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="font-utility shrink-0 border border-[#c4d0cc] px-3 py-2 text-xs font-semibold uppercase text-[#52605c] transition hover:border-[#176b62] hover:text-[#176b62]"
          >
            关闭
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {!canLoadPreview ? (
            <p className="border border-[#e2c7be] bg-[#fff8f5] px-4 py-3 text-sm text-[#8f3d2d]">
              这条历史引用缺少 file_id 或 chunk_index，无法精确读取原文。
            </p>
          ) : previewQuery.isPending ? (
            <p className="py-10 text-center text-sm text-[#64716d]">
              正在读取引用原文...
            </p>
          ) : previewQuery.isError ? (
            <div className="border border-[#e2c7be] bg-[#fff8f5] px-4 py-3 text-sm text-[#8f3d2d]">
              <p>
                {previewQuery.error instanceof Error
                  ? previewQuery.error.message
                  : "读取引用原文失败，请稍后再试。"}
              </p>
              <button
                type="button"
                onClick={() => previewQuery.refetch()}
                className="font-utility mt-3 border border-[#c98f80] px-3 py-1.5 text-[10px] font-semibold uppercase"
              >
                重新加载
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {targetIsOcrPage && targetPageNumber !== undefined ? (
                <section
                  className={
                    targetOcrQuality === "low"
                      ? "border border-[#d9aa2f] bg-[#fff7df] px-4 py-3 text-[#6d5010]"
                      : "border border-[#bdd2cc] bg-[#eef7f4] px-4 py-3 text-[#275f58]"
                  }
                  aria-live="polite"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="font-utility text-[10px] font-semibold uppercase tracking-[0.12em]">
                        {targetOcrQuality === "low"
                          ? "OCR 质量需要关注"
                          : "OCR 质量"}
                      </p>
                      <p className="mt-1 text-sm leading-6">
                        第 {targetPageNumber} 页
                        {targetOcrConfidenceLabel
                          ? `置信度 ${targetOcrConfidenceLabel}`
                          : "暂时没有可用置信度"}
                        。重新识别会异步重建该文件索引，期间文件暂不可检索。
                      </p>
                    </div>
                    <button
                      type="button"
                      disabled={
                        ocrReindexIsActive ||
                        ocrReindexJob?.status === "succeeded"
                      }
                      onClick={handleOcrReindex}
                      className="font-utility shrink-0 border border-current px-3 py-2 text-[10px] font-semibold uppercase transition-colors duration-150 hover:bg-white/55 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {ocrReindexMutation.isPending
                        ? "正在提交"
                        : ocrReindexJob?.status === "queued"
                          ? "排队中"
                          : ocrReindexJob?.status === "processing"
                            ? "重新识别中"
                            : ocrReindexJob?.status === "succeeded"
                              ? "已完成"
                              : ocrReindexJob?.status === "failed"
                                ? "重新尝试"
                                : ocrReindexJobQuery.isError
                                  ? "重新查询"
                                  : "重新识别此页"}
                    </button>
                  </div>
                  {ocrReindexJob?.status === "succeeded" ? (
                    <p className="mt-2 text-xs font-medium">
                      新索引已生成。请关闭弹窗并重新提问，以获取使用新 OCR 文本的引用。
                    </p>
                  ) : ocrReindexError ? (
                    <p className="mt-2 text-xs text-[#9b3c29]">
                      {ocrReindexError}
                    </p>
                  ) : ocrReindexIsActive ? (
                    <p className="mt-2 text-xs">任务已提交，可保持弹窗打开查看进度。</p>
                  ) : null}
                </section>
              ) : null}
              {previewQuery.data?.chunks.map((chunk) => {
                const location = formatChunkLocation(chunk.location);
                return (
                  <article
                    key={chunk.chunkIndex}
                    ref={chunk.isTarget ? targetChunkRef : undefined}
                    className={
                      chunk.isTarget
                        ? "border-2 border-[#176b62] bg-white px-4 py-4 shadow-[4px_4px_0_#d9e7e2]"
                        : "border border-[#d5ded9] bg-[#fdfefd] px-4 py-3"
                    }
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p
                        className={`font-utility text-[10px] font-semibold uppercase tracking-[0.12em] ${
                          chunk.isTarget ? "text-[#176b62]" : "text-[#72807b]"
                        }`}
                      >
                        Chunk #{chunk.chunkIndex}
                        {chunk.isTarget ? " · 当前引用" : " · 相邻上下文"}
                      </p>
                      {location ? (
                        <p className="text-[11px] text-[#64716d]">{location}</p>
                      ) : null}
                    </div>
                    <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-[#283331]">
                      {chunk.content}
                    </p>
                  </article>
                );
              })}
            </div>
          )}
        </div>

        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-[#ccd7d3] px-5 py-3">
          <div>
            <p className="text-xs text-[#64716d]">
              {previewQuery.data
                ? `索引版本 ${previewQuery.data.indexVersion} · ${previewQuery.data.mimeType}`
                : "原始文件访问同样经过当前用户权限校验"}
            </p>
            {fileOpenError ? (
              <p className="mt-1 text-xs text-[#9b3c29]">{fileOpenError}</p>
            ) : null}
          </div>
          <button
            type="button"
            disabled={!fileId || isOpeningFile}
            onClick={handleOpenOriginalFile}
            className="font-utility border border-[#176b62] bg-[#176b62] px-4 py-2 text-xs font-semibold uppercase text-white transition hover:bg-[#12564f] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isOpeningFile ? "正在打开" : "打开原始文件"}
          </button>
        </footer>
      </div>
    </div>
  );
}
