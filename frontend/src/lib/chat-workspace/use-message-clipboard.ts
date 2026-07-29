"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export const MESSAGE_COPY_RESET_MS = 1500;

type CopyMessageTextOptions = {
  writeText?: (content: string) => Promise<void>;
  fallbackCopy: (content: string) => void;
  onPrimaryError: (error: unknown) => void;
  onFallbackError: (error: unknown) => void;
};

/**
 * 使用隐藏 textarea 执行旧浏览器兼容的同步复制。
 */
export function copyTextWithTextarea(
  content: string,
  documentObject: Document = document,
) {
  const textarea = documentObject.createElement("textarea");
  textarea.value = content;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  documentObject.body.appendChild(textarea);

  try {
    textarea.select();
    documentObject.execCommand("copy");
  } finally {
    documentObject.body.removeChild(textarea);
  }
}

/**
 * 优先调用 Clipboard API，并在主路径失败时重试 textarea fallback。
 */
export async function copyMessageText(
  content: string,
  {
    writeText,
    fallbackCopy,
    onPrimaryError,
    onFallbackError,
  }: CopyMessageTextOptions,
) {
  try {
    if (writeText) {
      await writeText(content);
    } else {
      fallbackCopy(content);
    }

    return true;
  } catch (error) {
    onPrimaryError(error);

    try {
      fallbackCopy(content);
      return true;
    } catch (fallbackError) {
      onFallbackError(fallbackError);
      return false;
    }
  }
}

/**
 * 仅允许目标消息自己的计时器清除复制提示。
 */
export function clearCopiedMessageKey(
  currentMessageKey: string,
  copiedMessageKey: string,
) {
  return currentMessageKey === copiedMessageKey ? "" : currentMessageKey;
}

/**
 * 管理回答复制策略、当前提示目标和 1.5 秒复位计时器。
 */
export function useMessageClipboard() {
  const [copiedMessageKey, setCopiedMessageKey] = useState("");
  const resetTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (resetTimerRef.current !== null) {
        window.clearTimeout(resetTimerRef.current);
      }
    };
  }, []);

  const copyMessage = useCallback(
    async (messageKey: string, content: string) => {
      const clipboard = navigator.clipboard;
      const didCopy = await copyMessageText(content, {
        writeText: clipboard?.writeText
          ? clipboard.writeText.bind(clipboard)
          : undefined,
        fallbackCopy: copyTextWithTextarea,
        onPrimaryError: (error) => {
          console.error("Failed to copy message:", error);
        },
        onFallbackError: (error) => {
          console.error("Fallback copy also failed:", error);
        },
      });

      if (!didCopy) {
        return;
      }

      setCopiedMessageKey(messageKey);
      if (resetTimerRef.current !== null) {
        window.clearTimeout(resetTimerRef.current);
      }
      resetTimerRef.current = window.setTimeout(() => {
        setCopiedMessageKey((current) =>
          clearCopiedMessageKey(current, messageKey),
        );
        resetTimerRef.current = null;
      }, MESSAGE_COPY_RESET_MS);
    },
    [],
  );

  return {
    copiedMessageKey,
    copyMessage,
  };
}
