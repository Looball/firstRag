import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import {
  CHAT_IMAGE_ACCEPT,
  ChatComposer,
  type ChatComposerProps,
  type PendingChatImage,
} from "./ChatComposer";

const baseProps: ChatComposerProps = {
  input: "请总结这份报告",
  pendingImages: [],
  imageInputRef: {
    current: null,
  },
  isCurrentSessionLoading: false,
  isCreatingSession: false,
  isUploadingImages: false,
  isChatRateLimited: false,
  chatRetryAfterSeconds: 0,
  isImageRateLimited: false,
  imageRetryAfterSeconds: 0,
  canSendToKnowledgeBase: true,
  onInputChange: () => undefined,
  onPasteImages: () => undefined,
  onSelectImages: () => undefined,
  onRemoveImage: () => undefined,
  onSubmit: () => undefined,
};

describe("ChatComposer", () => {
  it("renders the controlled input and image selection guidance", () => {
    const markup = renderToStaticMarkup(<ChatComposer {...baseProps} />);

    expect(markup).toContain("Add To Research Log");
    expect(markup).toContain("请总结这份报告");
    expect(markup).toContain("Enter 发送 · Shift + Enter 换行");
    expect(markup).toContain(`accept="${CHAT_IMAGE_ACCEPT}"`);
    expect(markup).toContain("添加图片");
    expect(markup).toContain("最多 3 张");
    expect(markup).toContain("5.0 MB");
    expect(markup).toContain("发送问题");
  });

  it("renders pending image previews and the attachment count", () => {
    const pendingImages: PendingChatImage[] = [
      {
        id: "image-1",
        file: new File(["chart"], "chart.png", { type: "image/png" }),
        previewUrl: "blob:chart-preview",
      },
      {
        id: "image-2",
        file: new File(["table"], "table.webp", { type: "image/webp" }),
        previewUrl: "blob:table-preview",
      },
    ];
    const markup = renderToStaticMarkup(
      <ChatComposer {...baseProps} pendingImages={pendingImages} />,
    );

    expect(markup).toContain('src="blob:chart-preview"');
    expect(markup).toContain('alt="chart.png"');
    expect(markup).toContain("table.webp");
    expect(markup).toContain("添加图片 2/3");
    expect(markup.match(/>移除<\/button>/g)).toHaveLength(2);
  });

  it("prioritizes progress and retry labels while disabling blocked sends", () => {
    const creatingMarkup = renderToStaticMarkup(
      <ChatComposer {...baseProps} isCreatingSession />,
    );
    const uploadingMarkup = renderToStaticMarkup(
      <ChatComposer {...baseProps} isUploadingImages />,
    );
    const thinkingMarkup = renderToStaticMarkup(
      <ChatComposer {...baseProps} isCurrentSessionLoading />,
    );
    const retryMarkup = renderToStaticMarkup(
      <ChatComposer
        {...baseProps}
        pendingImages={[
          {
            id: "image-1",
            file: new File(["chart"], "chart.png", { type: "image/png" }),
            previewUrl: "blob:chart-preview",
          },
        ]}
        isChatRateLimited
        chatRetryAfterSeconds={7}
        isImageRateLimited
        imageRetryAfterSeconds={12}
      />,
    );
    const noKnowledgeBaseMarkup = renderToStaticMarkup(
      <ChatComposer {...baseProps} canSendToKnowledgeBase={false} />,
    );

    expect(creatingMarkup).toContain("创建中...");
    expect(uploadingMarkup).toContain("上传中...");
    expect(thinkingMarkup).toContain("思考中...");
    expect(retryMarkup).toContain("12 秒后可重试");
    expect(noKnowledgeBaseMarkup).toContain('disabled=""');
  });
});
