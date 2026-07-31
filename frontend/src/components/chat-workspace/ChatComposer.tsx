"use client";

import type { ClipboardEventHandler, RefObject } from "react";
import { formatFileSize } from "../../lib/chat-workspace/utils";
import {
  CHAT_IMAGE_ACCEPT,
  CHAT_IMAGE_MAX_FILES,
  CHAT_IMAGE_MAX_FILE_SIZE_BYTES,
  type PendingChatImage,
} from "../../lib/chat-workspace/use-pending-chat-images";

export {
  CHAT_IMAGE_ACCEPT,
  CHAT_IMAGE_MAX_FILES,
  CHAT_IMAGE_MAX_FILE_SIZE_BYTES,
} from "../../lib/chat-workspace/use-pending-chat-images";
export type { PendingChatImage } from "../../lib/chat-workspace/use-pending-chat-images";

export type ChatComposerProps = {
  input: string;
  pendingImages: PendingChatImage[];
  imageInputRef: RefObject<HTMLInputElement | null>;
  isCurrentSessionLoading: boolean;
  isCreatingSession: boolean;
  isUploadingImages: boolean;
  isChatRateLimited: boolean;
  chatRetryAfterSeconds: number;
  isImageRateLimited: boolean;
  imageRetryAfterSeconds: number;
  canSendToKnowledgeBase: boolean;
  onInputChange: (value: string) => void;
  onPasteImages: ClipboardEventHandler<HTMLTextAreaElement>;
  onSelectImages: (files: FileList | null) => void;
  onRemoveImage: (imageId: string) => void;
  onSubmit: () => void | Promise<void>;
};

/**
 * 展示聊天输入、待发送图片、图片选择入口和发送状态。
 *
 * 图片校验与 Object URL 生命周期由 usePendingChatImages 管理；
 * 上传、自动建会话和消息发送由 useChatSubmission 管理。
 */
export function ChatComposer({
  input,
  pendingImages,
  imageInputRef,
  isCurrentSessionLoading,
  isCreatingSession,
  isUploadingImages,
  isChatRateLimited,
  chatRetryAfterSeconds,
  isImageRateLimited,
  imageRetryAfterSeconds,
  canSendToKnowledgeBase,
  onInputChange,
  onPasteImages,
  onSelectImages,
  onRemoveImage,
  onSubmit,
}: ChatComposerProps) {
  const hasPendingImages = pendingImages.length > 0;
  const isPendingImageRateLimited =
    hasPendingImages && isImageRateLimited;
  const isRetryLimited = isChatRateLimited || isPendingImageRateLimited;
  const retryAfterSeconds = Math.max(
    chatRetryAfterSeconds,
    hasPendingImages ? imageRetryAfterSeconds : 0,
  );
  const isImageSelectionDisabled =
    isCurrentSessionLoading ||
    isCreatingSession ||
    isUploadingImages ||
    pendingImages.length >= CHAT_IMAGE_MAX_FILES;
  const isSubmitDisabled =
    isCurrentSessionLoading ||
    isCreatingSession ||
    isUploadingImages ||
    isRetryLimited ||
    !canSendToKnowledgeBase;

  return (
    <div className="shrink-0 border-t border-[#cbd5d1] bg-[#eef3f0] px-5 py-5 md:px-8 md:py-6">
      <div className="flex items-center justify-between gap-4">
        <label
          htmlFor="question"
          className="font-utility block text-[10px] font-semibold uppercase text-[#176b62]"
        >
          Add To Research Log
        </label>
        <span className="font-utility text-[10px] text-[#7b8884]">
          Enter 发送 · Shift + Enter 换行
        </span>
      </div>
      <div className="mt-3 flex flex-col gap-3 md:flex-row md:items-end">
        <div className="research-focus-within min-w-0 flex-1 border border-[#aebdb7] bg-[#fcfdfb]">
          {hasPendingImages && (
            <div className="grid gap-2 border-b border-[#d5ded9] bg-[#f5f8f6] p-3 sm:grid-cols-3">
              {pendingImages.map((image) => (
                <figure
                  key={image.id}
                  className="overflow-hidden border border-[#cbd5d1] bg-[#fcfdfb]"
                >
                  <img
                    src={image.previewUrl}
                    alt={image.file.name}
                    className="aspect-[4/3] w-full object-cover"
                  />
                  <figcaption className="flex items-center justify-between gap-2 px-2 py-1.5 text-[11px] text-[#64716d]">
                    <span
                      className="min-w-0 truncate"
                      title={image.file.name}
                    >
                      {image.file.name}
                    </span>
                    <button
                      type="button"
                      onClick={() => onRemoveImage(image.id)}
                      className="shrink-0 font-semibold text-[#9b3c29] hover:text-[#e36b4f] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#176b62]"
                    >
                      移除
                    </button>
                  </figcaption>
                </figure>
              ))}
            </div>
          )}

          <textarea
            id="question"
            value={input}
            onChange={(event) => onInputChange(event.target.value)}
            onPaste={onPasteImages}
            onKeyDown={(event) => {
              if (
                event.key === "Enter" &&
                !event.shiftKey &&
                !isCurrentSessionLoading
              ) {
                event.preventDefault();
                void onSubmit();
              }
            }}
            placeholder="输入问题，或直接粘贴剪切板中的图片..."
            className="min-h-[64px] w-full resize-y bg-transparent px-4 py-3 text-[#17201f] outline-none md:min-h-[65px]"
          />

          <div className="flex min-h-10 flex-wrap items-center justify-between gap-2 border-t border-[#d5ded9] px-3 py-2">
            <input
              ref={imageInputRef}
              type="file"
              accept={CHAT_IMAGE_ACCEPT}
              multiple
              className="hidden"
              onChange={(event) => onSelectImages(event.target.files)}
            />
            <button
              type="button"
              onClick={() => imageInputRef.current?.click()}
              disabled={isImageSelectionDisabled}
              className="inline-flex items-center gap-2 px-1 py-0.5 text-xs font-semibold text-[#176b62] transition hover:text-[#105149] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#176b62] disabled:text-[#91aaa4]"
            >
              <svg
                aria-hidden="true"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                className="h-4 w-4"
              >
                <path
                  d="M4 16.5 8.5 12l3 3 2.5-2.5 6 6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d="M5.5 4.5h13a1.5 1.5 0 0 1 1.5 1.5v12a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18V6a1.5 1.5 0 0 1 1.5-1.5Z"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <circle cx="9" cy="9" r="1.25" />
              </svg>
              {hasPendingImages
                ? `添加图片 ${pendingImages.length}/${CHAT_IMAGE_MAX_FILES}`
                : "添加图片"}
            </button>
            <span className="font-utility text-[10px] text-[#7b8884]">
              ⌘V / Ctrl+V 粘贴截图
            </span>
          </div>
        </div>

        <div className="flex shrink-0 md:h-[104px] md:w-48">
          <button
            type="button"
            onClick={() => {
              void onSubmit();
            }}
            disabled={isSubmitDisabled}
            className="h-12 flex-1 bg-[#176b62] px-4 text-sm font-semibold text-white transition hover:bg-[#105149] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#176b62] disabled:bg-[#91aaa4] md:h-auto"
          >
            {isCreatingSession
              ? "创建中..."
              : isUploadingImages
                ? "上传中..."
                : isCurrentSessionLoading
                  ? "思考中..."
                  : isRetryLimited
                    ? `${retryAfterSeconds} 秒后可重试`
                    : "发送问题"}
          </button>
        </div>
      </div>
      <p className="mt-2 text-xs text-[#7b8884]">
        图片支持 PNG、JPEG、WebP；可选择文件或直接粘贴，最多{" "}
        {CHAT_IMAGE_MAX_FILES} 张，每张不超过{" "}
        {formatFileSize(CHAT_IMAGE_MAX_FILE_SIZE_BYTES)}。
      </p>
    </div>
  );
}
