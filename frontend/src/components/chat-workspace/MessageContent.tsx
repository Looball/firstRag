"use client";

import { memo, type ReactNode, useEffect, useState } from "react";
import { authenticatedFetch } from "../../lib/frontend-api";
import type { MessageAttachment } from "../../lib/chat-workspace/types";

/**
 * 渲染消息中的行内代码和加粗语法。
 */
function renderInlineMarkdown(
  text: string,
  keyPrefix: string,
  isUserMessage: boolean
) {
  const nodes: ReactNode[] = [];
  const pattern = /(`[^`]*`|\*\*[^*]+\*\*)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let partIndex = 0;

  while ((match = pattern.exec(text))) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }

    const token = match[0];

    if (token.startsWith("`")) {
      nodes.push(
        <code
          key={`${keyPrefix}-code-${partIndex}`}
          className={`rounded px-1.5 py-0.5 font-mono text-[0.92em] ${
            isUserMessage
              ? "bg-white/15 text-white"
              : "bg-[#dfe9e5] text-[#105149]"
          }`}
        >
          {token.slice(1, -1)}
        </code>
      );
    } else {
      nodes.push(
        <strong key={`${keyPrefix}-strong-${partIndex}`} className="font-semibold">
          {token.slice(2, -2)}
        </strong>
      );
    }

    partIndex += 1;
    lastIndex = pattern.lastIndex;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes;
}

/**
 * 判断当前行是否会开始新的 Markdown block。
 */
function isMarkdownBlockStart(line: string) {
  return (
    /^```/.test(line) ||
    /^#{1,6}\s+/.test(line) ||
    /^\s*\d+\.\s+/.test(line) ||
    /^\s*[-*]\s+/.test(line)
  );
}

/**
 * 渲染聊天消息支持的轻量 Markdown 子集。
 */
export const MarkdownContent = memo(function MarkdownContent({
  content,
  isUserMessage,
}: {
  content: string;
  isUserMessage: boolean;
}) {
  const lines = content.split("\n");
  const blocks: ReactNode[] = [];
  let index = 0;
  let blockIndex = 0;

  const inline = (text: string, suffix: string) =>
    renderInlineMarkdown(text, `md-${blockIndex}-${suffix}`, isUserMessage);

  while (index < lines.length) {
    const line = lines[index];

    if (!line.trim()) {
      index += 1;
      continue;
    }

    const codeFenceMatch = line.match(/^```(\w+)?\s*$/);

    if (codeFenceMatch) {
      const codeLines: string[] = [];
      index += 1;

      while (index < lines.length && !/^```\s*$/.test(lines[index])) {
        codeLines.push(lines[index]);
        index += 1;
      }

      if (index < lines.length) {
        index += 1;
      }

      blocks.push(
        <pre
          key={`code-${blockIndex}`}
          className={`overflow-x-auto rounded-xl px-4 py-3 text-sm ${
            isUserMessage
              ? "bg-black/25 text-white"
              : "bg-[#17201f] text-[#eef5f2]"
          }`}
        >
          <code>{codeLines.join("\n")}</code>
        </pre>
      );
      blockIndex += 1;
      continue;
    }

    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);

    if (headingMatch) {
      const level = headingMatch[1].length;
      const text = headingMatch[2];
      const headingClass =
        level <= 1
          ? "text-2xl font-semibold leading-8"
          : level === 2
            ? "text-xl font-semibold leading-8"
            : "text-lg font-semibold leading-7";

      if (level <= 1) {
        blocks.push(
          <h2 key={`heading-${blockIndex}`} className={headingClass}>
            {inline(text, "heading")}
          </h2>
        );
      } else if (level === 2) {
        blocks.push(
          <h3 key={`heading-${blockIndex}`} className={headingClass}>
            {inline(text, "heading")}
          </h3>
        );
      } else {
        blocks.push(
          <h4 key={`heading-${blockIndex}`} className={headingClass}>
            {inline(text, "heading")}
          </h4>
        );
      }

      index += 1;
      blockIndex += 1;
      continue;
    }

    const orderedMatch = line.match(/^\s*\d+\.\s+(.+)$/);

    if (orderedMatch) {
      const items: string[] = [];

      while (index < lines.length) {
        const itemMatch = lines[index].match(/^\s*\d+\.\s+(.+)$/);

        if (!itemMatch) {
          break;
        }

        const itemLines = [itemMatch[1]];
        index += 1;

        while (
          index < lines.length &&
          lines[index].trim() &&
          !isMarkdownBlockStart(lines[index])
        ) {
          itemLines.push(lines[index].trim());
          index += 1;
        }

        items.push(itemLines.join("\n"));
      }

      blocks.push(
        <ol key={`ol-${blockIndex}`} className="list-decimal space-y-2 pl-6">
          {items.map((item, itemIndex) => (
            <li
              key={`ol-${blockIndex}-${itemIndex}`}
              className="whitespace-pre-wrap pl-1"
            >
              {renderInlineMarkdown(
                item,
                `md-${blockIndex}-ol-${itemIndex}`,
                isUserMessage
              )}
            </li>
          ))}
        </ol>
      );
      blockIndex += 1;
      continue;
    }

    const unorderedMatch = line.match(/^\s*[-*]\s+(.+)$/);

    if (unorderedMatch) {
      const items: string[] = [];

      while (index < lines.length) {
        const itemMatch = lines[index].match(/^\s*[-*]\s+(.+)$/);

        if (!itemMatch) {
          break;
        }

        const itemLines = [itemMatch[1]];
        index += 1;

        while (
          index < lines.length &&
          lines[index].trim() &&
          !isMarkdownBlockStart(lines[index])
        ) {
          itemLines.push(lines[index].trim());
          index += 1;
        }

        items.push(itemLines.join("\n"));
      }

      blocks.push(
        <ul key={`ul-${blockIndex}`} className="list-disc space-y-2 pl-6">
          {items.map((item, itemIndex) => (
            <li
              key={`ul-${blockIndex}-${itemIndex}`}
              className="whitespace-pre-wrap pl-1"
            >
              {renderInlineMarkdown(
                item,
                `md-${blockIndex}-ul-${itemIndex}`,
                isUserMessage
              )}
            </li>
          ))}
        </ul>
      );
      blockIndex += 1;
      continue;
    }

    const paragraphLines: string[] = [];

    while (
      index < lines.length &&
      lines[index].trim() &&
      !isMarkdownBlockStart(lines[index])
    ) {
      paragraphLines.push(lines[index]);
      index += 1;
    }

    blocks.push(
      <p key={`p-${blockIndex}`} className="whitespace-pre-wrap">
        {inline(paragraphLines.join("\n"), "paragraph")}
      </p>
    );
    blockIndex += 1;
  }

  return <div className="space-y-3 leading-7 break-words">{blocks}</div>;
});

/**
 * 通过认证请求加载历史消息附件，并在卸载时释放 Blob URL。
 */
function AuthenticatedAttachmentImage({
  attachment,
}: {
  attachment: MessageAttachment;
}) {
  const [remoteObjectUrl, setRemoteObjectUrl] = useState("");
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    if (attachment.localPreviewUrl) {
      return undefined;
    }

    let isCancelled = false;
    let nextObjectUrl = "";

    async function loadImage() {
      try {
        const response = await authenticatedFetch(
          attachment.contentUrl,
          { method: "GET" },
          {
            fallbackMessage: "读取图片失败，请稍后再试。",
            skipAuthRedirect: true,
          }
        );
        const blob = await response.blob();
        if (isCancelled) {
          return;
        }
        nextObjectUrl = URL.createObjectURL(blob);
        setRemoteObjectUrl(nextObjectUrl);
        setHasError(false);
      } catch {
        if (!isCancelled) {
          setHasError(true);
        }
      }
    }

    void loadImage();

    return () => {
      isCancelled = true;
      if (nextObjectUrl) {
        URL.revokeObjectURL(nextObjectUrl);
      }
    };
  }, [attachment.contentUrl, attachment.localPreviewUrl]);

  if (hasError) {
    return (
      <div className="flex aspect-[4/3] items-center justify-center border border-[#cbd5d1] bg-[#eef3f0] px-3 text-center text-xs text-[#64716d]">
        图片暂不可用
      </div>
    );
  }

  const imageUrl = attachment.localPreviewUrl || remoteObjectUrl;

  return imageUrl ? (
    <img
      src={imageUrl}
      alt={attachment.originalName}
      className="aspect-[4/3] w-full object-cover"
    />
  ) : (
    <div className="aspect-[4/3] animate-pulse bg-[#dfe8e4]" />
  );
}

/**
 * 渲染消息图片附件网格。
 */
export const MessageAttachmentGrid = memo(function MessageAttachmentGrid({
  attachments,
  isUserMessage,
}: {
  attachments: MessageAttachment[];
  isUserMessage: boolean;
}) {
  if (attachments.length === 0) {
    return null;
  }

  return (
    <div className="mt-4 grid gap-2 sm:grid-cols-3">
      {attachments.map((attachment) => (
        <figure
          key={attachment.id}
          className={`overflow-hidden border ${
            isUserMessage
              ? "border-white/20 bg-white/10"
              : "border-[#d5ded9] bg-[#fcfdfb]"
          }`}
        >
          <AuthenticatedAttachmentImage attachment={attachment} />
          <figcaption
            className={`truncate px-2 py-1.5 text-[11px] ${
              isUserMessage ? "text-white/75" : "text-[#64716d]"
            }`}
            title={attachment.originalName}
          >
            {attachment.originalName}
          </figcaption>
        </figure>
      ))}
    </div>
  );
});
