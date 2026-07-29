"use client";

import {
  type ClipboardEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

export const CHAT_IMAGE_ACCEPT = "image/png,image/jpeg,image/webp";
export const CHAT_IMAGE_MAX_FILES = 3;
export const CHAT_IMAGE_MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024;

export type PendingChatImage = {
  id: string;
  file: File;
  previewUrl: string;
};

type UsePendingChatImagesOptions = {
  onError: (message: string) => void;
};

const acceptedChatImageTypes = new Set(CHAT_IMAGE_ACCEPT.split(","));

/**
 * 按现有优先级校验待加入的聊天图片，并返回用户可见错误文案。
 */
export function getChatImageSelectionError(
  currentImageCount: number,
  files: File[],
) {
  if (currentImageCount + files.length > CHAT_IMAGE_MAX_FILES) {
    return `单轮最多只能附加 ${CHAT_IMAGE_MAX_FILES} 张图片。`;
  }

  for (const file of files) {
    if (!acceptedChatImageTypes.has(file.type)) {
      return "仅支持 PNG、JPEG 或 WebP 图片。";
    }
    if (file.size > CHAT_IMAGE_MAX_FILE_SIZE_BYTES) {
      return "单张图片不能超过 5MB。";
    }
  }

  return "";
}

/**
 * 从剪贴板条目中筛选可交给统一校验流程的图片文件。
 */
export function getPastedChatImageFiles(
  items: ArrayLike<DataTransferItem>,
) {
  return Array.from(items)
    .filter((item) => item.kind === "file" && item.type.startsWith("image/"))
    .map((item) => item.getAsFile())
    .filter((file): file is File => file !== null);
}

/**
 * 为通过校验的文件创建本地预览与稳定列表键。
 */
export function createPendingChatImages(
  files: File[],
  createObjectUrl: (file: File) => string = (file) =>
    URL.createObjectURL(file),
  createId: () => string = () => crypto.randomUUID(),
) {
  return files.map((file) => ({
    id: `${file.name}-${file.size}-${file.lastModified}-${createId()}`,
    file,
    previewUrl: createObjectUrl(file),
  }));
}

/**
 * 释放一组待发送图片持有的 Object URL。
 */
export function revokePendingChatImages(
  images: PendingChatImage[],
  revokeObjectUrl: (url: string) => void = (url) =>
    URL.revokeObjectURL(url),
) {
  images.forEach((image) => {
    revokeObjectUrl(image.previewUrl);
  });
}

/**
 * 管理待发送聊天图片的校验、预览和 Object URL 生命周期。
 */
export function usePendingChatImages({
  onError,
}: UsePendingChatImagesOptions) {
  const [pendingChatImages, setPendingChatImages] = useState<
    PendingChatImage[]
  >([]);
  const pendingChatImagesRef = useRef<PendingChatImage[]>([]);
  const chatImageInputRef = useRef<HTMLInputElement | null>(null);

  const resetImageInput = useCallback(() => {
    if (chatImageInputRef.current) {
      chatImageInputRef.current.value = "";
    }
  }, []);

  const clearPendingChatImages = useCallback(() => {
    revokePendingChatImages(pendingChatImagesRef.current);
    pendingChatImagesRef.current = [];
    setPendingChatImages([]);
    resetImageInput();
  }, [resetImageInput]);

  const removePendingChatImage = useCallback((imageId: string) => {
    const currentImages = pendingChatImagesRef.current;
    const removedImage = currentImages.find((image) => image.id === imageId);

    if (removedImage) {
      revokePendingChatImages([removedImage]);
    }

    const nextImages = currentImages.filter((image) => image.id !== imageId);
    pendingChatImagesRef.current = nextImages;
    setPendingChatImages(nextImages);
  }, []);

  const handleSelectChatImages = useCallback(
    (files: FileList | File[] | null) => {
      if (!files?.length) {
        return;
      }

      const selectedFiles = Array.from(files);
      const validationError = getChatImageSelectionError(
        pendingChatImagesRef.current.length,
        selectedFiles,
      );

      if (validationError) {
        onError(validationError);
        resetImageInput();
        return;
      }

      const nextImages = createPendingChatImages(selectedFiles);
      const updatedImages = [
        ...pendingChatImagesRef.current,
        ...nextImages,
      ];

      onError("");
      pendingChatImagesRef.current = updatedImages;
      setPendingChatImages(updatedImages);
      resetImageInput();
    },
    [onError, resetImageInput],
  );

  const handlePasteChatImages = useCallback(
    (event: ClipboardEvent<HTMLTextAreaElement>) => {
      const pastedImages = getPastedChatImageFiles(event.clipboardData.items);

      if (pastedImages.length === 0) {
        return;
      }

      event.preventDefault();
      handleSelectChatImages(pastedImages);
    },
    [handleSelectChatImages],
  );

  useEffect(() => {
    return () => {
      revokePendingChatImages(pendingChatImagesRef.current);
    };
  }, []);

  return {
    chatImageInputRef,
    clearPendingChatImages,
    handlePasteChatImages,
    handleSelectChatImages,
    pendingChatImages,
    removePendingChatImage,
  };
}
