import { describe, expect, it, vi } from "vitest";
import {
  clearCopiedMessageKey,
  copyMessageText,
  copyTextWithTextarea,
} from "./use-message-clipboard";

describe("useMessageClipboard helpers", () => {
  it("copies through a hidden textarea and removes the temporary node", () => {
    const textarea = {
      value: "",
      style: {
        position: "",
        opacity: "",
      },
      select: vi.fn(),
    } as unknown as HTMLTextAreaElement;
    const appendChild = vi.fn();
    const removeChild = vi.fn();
    const execCommand = vi.fn();
    const documentObject = {
      createElement: vi.fn(() => textarea),
      body: {
        appendChild,
        removeChild,
      },
      execCommand,
    } as unknown as Document;

    copyTextWithTextarea("回答内容", documentObject);

    expect(textarea.value).toBe("回答内容");
    expect(textarea.style.position).toBe("fixed");
    expect(textarea.style.opacity).toBe("0");
    expect(appendChild).toHaveBeenCalledWith(textarea);
    expect(textarea.select).toHaveBeenCalledOnce();
    expect(execCommand).toHaveBeenCalledWith("copy");
    expect(removeChild).toHaveBeenCalledWith(textarea);
  });

  it("uses Clipboard API without invoking the fallback when available", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    const fallbackCopy = vi.fn();

    await expect(
      copyMessageText("回答内容", {
        writeText,
        fallbackCopy,
        onPrimaryError: vi.fn(),
        onFallbackError: vi.fn(),
      }),
    ).resolves.toBe(true);
    expect(writeText).toHaveBeenCalledWith("回答内容");
    expect(fallbackCopy).not.toHaveBeenCalled();
  });

  it("uses the textarea fallback when Clipboard API is unavailable", async () => {
    const fallbackCopy = vi.fn();

    await expect(
      copyMessageText("回答内容", {
        fallbackCopy,
        onPrimaryError: vi.fn(),
        onFallbackError: vi.fn(),
      }),
    ).resolves.toBe(true);
    expect(fallbackCopy).toHaveBeenCalledWith("回答内容");
  });

  it("retries with fallback after a Clipboard API failure", async () => {
    const primaryError = new Error("clipboard denied");
    const onPrimaryError = vi.fn();
    const fallbackCopy = vi.fn();

    await expect(
      copyMessageText("回答内容", {
        writeText: vi.fn().mockRejectedValue(primaryError),
        fallbackCopy,
        onPrimaryError,
        onFallbackError: vi.fn(),
      }),
    ).resolves.toBe(true);
    expect(onPrimaryError).toHaveBeenCalledWith(primaryError);
    expect(fallbackCopy).toHaveBeenCalledWith("回答内容");
  });

  it("does not report success when both copy paths fail", async () => {
    const fallbackError = new Error("fallback denied");
    const onFallbackError = vi.fn();

    await expect(
      copyMessageText("回答内容", {
        writeText: vi.fn().mockRejectedValue(new Error("clipboard denied")),
        fallbackCopy: vi.fn(() => {
          throw fallbackError;
        }),
        onPrimaryError: vi.fn(),
        onFallbackError,
      }),
    ).resolves.toBe(false);
    expect(onFallbackError).toHaveBeenCalledWith(fallbackError);
  });

  it("keeps a newer copied target when an older reset runs", () => {
    expect(clearCopiedMessageKey("message-1", "message-1")).toBe("");
    expect(clearCopiedMessageKey("message-2", "message-1")).toBe("message-2");
  });
});
