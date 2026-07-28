import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import {
  MarkdownContent,
  MessageAttachmentGrid,
} from "./MessageContent";

describe("MarkdownContent", () => {
  it("renders headings, inline styles, lists, and fenced code", () => {
    const markup = renderToStaticMarkup(
      <MarkdownContent
        content={[
          "## 检索结果",
          "",
          "包含 **重点** 与 `代码`。",
          "",
          "1. 第一项",
          "2. 第二项",
          "",
          "- 来源 A",
          "- 来源 B",
          "",
          "```ts",
          "const answer = 42;",
          "```",
        ].join("\n")}
        isUserMessage={false}
      />
    );

    expect(markup).toContain("<h3");
    expect(markup).toContain("<strong");
    expect(markup).toContain("<code");
    expect(markup).toContain("<ol");
    expect(markup).toContain("<ul");
    expect(markup).toContain("const answer = 42;");
  });

  it("keeps the user-message color treatment", () => {
    const markup = renderToStaticMarkup(
      <MarkdownContent content="`用户代码`" isUserMessage />
    );

    expect(markup).toContain("bg-white/15");
    expect(markup).toContain("text-white");
  });
});

describe("MessageAttachmentGrid", () => {
  it("renders local previews without requesting remote content", () => {
    const markup = renderToStaticMarkup(
      <MessageAttachmentGrid
        attachments={[
          {
            id: "attachment-1",
            originalName: "evidence.png",
            mimeType: "image/png",
            sizeBytes: 128,
            contentUrl: "/api/chat/attachments/attachment-1/content",
            localPreviewUrl: "blob:local-preview",
          },
        ]}
        isUserMessage={false}
      />
    );

    expect(markup).toContain('src="blob:local-preview"');
    expect(markup).toContain('alt="evidence.png"');
    expect(markup).toContain("evidence.png");
  });

  it("renders nothing for an empty attachment list", () => {
    const markup = renderToStaticMarkup(
      <MessageAttachmentGrid attachments={[]} isUserMessage={false} />
    );

    expect(markup).toBe("");
  });
});
