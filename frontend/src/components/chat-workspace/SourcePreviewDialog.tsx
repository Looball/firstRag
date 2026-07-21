"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import * as chatApi from "@/lib/chat-workspace/api";
import type { ChatSource } from "@/lib/chat-workspace/types";

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
  const page = location.page_number ?? location.page;

  if (page !== undefined) {
    headings.push(`第 ${page} 页`);
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
      fileWindow.location.href = objectUrl;
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
