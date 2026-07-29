import { describe, expect, it, vi } from "vitest";
import {
  CHAT_IMAGE_MAX_FILE_SIZE_BYTES,
  createPendingChatImages,
  getChatImageSelectionError,
  getPastedChatImageFiles,
  revokePendingChatImages,
} from "./use-pending-chat-images";

describe("usePendingChatImages helpers", () => {
  it("keeps the existing count, type, and size validation priority", () => {
    const png = new File(["png"], "chart.png", { type: "image/png" });
    const text = new File(["text"], "notes.txt", { type: "text/plain" });
    const oversized = new File(
      [new Uint8Array(CHAT_IMAGE_MAX_FILE_SIZE_BYTES + 1)],
      "scan.webp",
      { type: "image/webp" },
    );

    expect(getChatImageSelectionError(2, [png, png])).toBe(
      "单轮最多只能附加 3 张图片。",
    );
    expect(getChatImageSelectionError(0, [text])).toBe(
      "仅支持 PNG、JPEG 或 WebP 图片。",
    );
    expect(getChatImageSelectionError(0, [oversized])).toBe(
      "单张图片不能超过 5MB。",
    );
    expect(getChatImageSelectionError(0, [png])).toBe("");
  });

  it("keeps only clipboard image files", () => {
    const image = new File(["image"], "paste.png", { type: "image/png" });
    const items = [
      {
        kind: "string",
        type: "text/plain",
        getAsFile: () => null,
      },
      {
        kind: "file",
        type: "image/png",
        getAsFile: () => image,
      },
    ] as DataTransferItem[];

    expect(getPastedChatImageFiles(items)).toEqual([image]);
  });

  it("creates stable preview records with injected browser resources", () => {
    const file = new File(["image"], "paste.png", {
      type: "image/png",
      lastModified: 123,
    });

    expect(
      createPendingChatImages(
        [file],
        (selectedFile) => `blob:${selectedFile.name}`,
        () => "image-id",
      ),
    ).toEqual([
      {
        id: `paste.png-${file.size}-123-image-id`,
        file,
        previewUrl: "blob:paste.png",
      },
    ]);
  });

  it("releases every preview URL", () => {
    const revokeObjectUrl = vi.fn();

    revokePendingChatImages(
      [
        {
          id: "image-1",
          file: new File(["one"], "one.png", { type: "image/png" }),
          previewUrl: "blob:one",
        },
        {
          id: "image-2",
          file: new File(["two"], "two.webp", { type: "image/webp" }),
          previewUrl: "blob:two",
        },
      ],
      revokeObjectUrl,
    );

    expect(revokeObjectUrl).toHaveBeenNthCalledWith(1, "blob:one");
    expect(revokeObjectUrl).toHaveBeenNthCalledWith(2, "blob:two");
  });
});
