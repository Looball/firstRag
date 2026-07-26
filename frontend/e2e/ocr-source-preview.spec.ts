import { expect, test, type Page, type Route } from "@playwright/test";

const AUTH_STORAGE_KEY = "ai-learning-assistant-auth";
const KNOWLEDGE_BASE_ID = "22222222-2222-4222-8222-222222222222";
const CONVERSATION_ID = "33333333-3333-4333-8333-333333333333";
const FILE_ID = "44444444-4444-4444-8444-444444444444";
const FILE_NAME = "e2e-mixed-pdf.pdf";
const TEST_TOKEN = "e2e-token";
const PNG_BYTES = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=",
  "base64",
);

type PreviewRequestEvidence = {
  authorization: string;
  pathname: string;
} | null;

/** 返回 JSON fixture，并显式禁止浏览器缓存测试响应。 */
async function fulfillJson(route: Route, body: unknown) {
  await route.fulfill({
    body: JSON.stringify(body),
    contentType: "application/json",
    headers: { "Cache-Control": "no-store" },
    status: 200,
  });
}

/** 为 OCR source 点击链路提供最小、确定性的同源 API fixture。 */
async function installOcrSourceFixtures(
  page: Page,
  recordPreviewRequest: (evidence: PreviewRequestEvidence) => void,
) {
  await page.addInitScript(
    ({ storageKey, token }) => {
      window.localStorage.setItem(
        storageKey,
        JSON.stringify({
          access_token: token,
          token_type: "bearer",
          user: { username: "e2e-admin" },
        }),
      );
    },
    { storageKey: AUTH_STORAGE_KEY, token: TEST_TOKEN },
  );

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const authorization = request.headers().authorization || "";

    if (authorization !== `Bearer ${TEST_TOKEN}`) {
      await route.fulfill({
        body: JSON.stringify({ detail: "E2E request missing bearer token" }),
        contentType: "application/json",
        status: 401,
      });
      return;
    }

    if (url.pathname === "/api/chat/knowledge-bases") {
      await fulfillJson(route, {
        knowledge_bases: [
          {
            id: KNOWLEDGE_BASE_ID,
            name: "E2E OCR 知识库",
            is_default: true,
            file_count: 1,
            conversations: [
              {
                id: CONVERSATION_ID,
                knowledge_base_id: KNOWLEDGE_BASE_ID,
                title: "OCR Page Preview E2E",
              },
            ],
          },
        ],
      });
      return;
    }

    if (
      url.pathname ===
      `/api/chat/conversations/${CONVERSATION_ID}/messages`
    ) {
      await fulfillJson(route, {
        messages: [
          {
            id: "message-user",
            role: "user",
            content: "请给出扫描页中的验收标识。",
          },
          {
            id: "message-assistant",
            role: "assistant",
            content: "扫描页验收标识是 T085 PAGE TWO。",
            sources: [
              {
                index: 0,
                title: FILE_NAME,
                content:
                  "FirstRAG Mixed PDF - Scanned Page 2 T085 PAGE TWO",
                file_id: FILE_ID,
                file_name: FILE_NAME,
                file_type: "pdf",
                chunk_index: 2,
                index_version: 0,
                page_number: 2,
                page_count: 3,
                pdf_parse_method: "ocr",
                ocr_confidence: 93.15,
                ocr_quality: "good",
                retrieval_sources: ["fulltext", "vector"],
              },
            ],
          },
        ],
      });
      return;
    }

    if (
      url.pathname ===
      `/api/chat/knowledge-base/${KNOWLEDGE_BASE_ID}/files`
    ) {
      await fulfillJson(route, {
        files: [
          {
            id: FILE_ID,
            original_name: FILE_NAME,
            size_bytes: 1024,
            status: "indexed",
          },
        ],
      });
      return;
    }

    if (url.pathname === "/api/chat/vector-index-jobs/health") {
      await fulfillJson(route, {
        success: true,
        worker: {
          status: "idle",
          is_healthy: true,
          has_recent_activity: false,
          stale_queued: 0,
          stale_processing: 0,
          online_count: 1,
          checked_at: "2026-07-26T10:00:00+08:00",
        },
        queue: {
          status: "idle",
          total: 0,
          active: 0,
          queued: 0,
          processing: 0,
          succeeded: 0,
          failed: 0,
          cancelled: 0,
        },
      });
      return;
    }

    if (
      url.pathname ===
      `/api/chat/knowledge-files/${FILE_ID}/chunks/2`
    ) {
      await fulfillJson(route, {
        file: {
          id: FILE_ID,
          original_name: FILE_NAME,
          mime_type: "application/pdf",
          index_version: 0,
        },
        target_chunk_index: 2,
        chunks: [
          {
            chunk_index: 1,
            content: "T085 NATIVE PAGE ONE",
            location: {
              page_number: 1,
              page_count: 3,
              pdf_parse_method: "native_text",
            },
            is_target: false,
          },
          {
            chunk_index: 2,
            content: "T085 PAGE TWO",
            location: {
              page_number: 2,
              page_count: 3,
              pdf_parse_method: "ocr",
              ocr_confidence: 93.15,
              ocr_quality: "good",
            },
            is_target: true,
          },
          {
            chunk_index: 3,
            content: "T085 NATIVE PAGE THREE",
            location: {
              page_number: 3,
              page_count: 3,
              pdf_parse_method: "native_text",
            },
            is_target: false,
          },
        ],
      });
      return;
    }

    if (
      url.pathname ===
      `/api/chat/knowledge-files/${FILE_ID}/ocr/pages/2/correction`
    ) {
      await fulfillJson(route, {
        correction: {
          file_id: FILE_ID,
          page_number: 2,
          index_version: 0,
          original_text: "T085 PAGE TWO",
          current_text: "T085 PAGE TWO",
          corrected_text: null,
          has_correction: false,
          revision: 0,
          updated_at: null,
          ocr_confidence: 93.15,
          ocr_quality: "good",
        },
      });
      return;
    }

    if (
      url.pathname ===
      `/api/chat/knowledge-files/${FILE_ID}/pages/2/preview`
    ) {
      recordPreviewRequest({ authorization, pathname: url.pathname });
      await route.fulfill({
        body: PNG_BYTES,
        contentType: "image/png",
        headers: { "Cache-Control": "private, max-age=60" },
        status: 200,
      });
      return;
    }

    await route.fulfill({
      body: JSON.stringify({
        detail: `Unexpected E2E API request: ${request.method()} ${url.pathname}`,
      }),
      contentType: "application/json",
      status: 500,
    });
  });
}

test("点击 OCR source 后加载第 2 页 PNG", async ({ page }) => {
  let previewRequest: PreviewRequestEvidence = null;
  await installOcrSourceFixtures(page, (evidence) => {
    previewRequest = evidence;
  });

  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "OCR Page Preview E2E" }),
  ).toBeVisible();

  const sourceButton = page.getByRole("button", { name: "查看原文 →" });
  await expect(sourceButton).toHaveCount(1);
  await sourceButton.click();

  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText("第 2 / 3 页");
  await expect(dialog).toContainText("引用扫描原页 · 第 2 页");
  await expect(dialog).toContainText("Chunk #2 · 当前引用");

  const pageImage = dialog.getByRole("img", {
    name: "引用扫描原页第 2 页",
  });
  await expect(pageImage).toBeVisible();
  await expect
    .poll(() =>
      pageImage.evaluate((image: HTMLImageElement) => ({
        complete: image.complete,
        height: image.naturalHeight,
        sourceIsBlob: image.currentSrc.startsWith("blob:"),
        width: image.naturalWidth,
      })),
    )
    .toEqual({
      complete: true,
      height: 1,
      sourceIsBlob: true,
      width: 1,
    });

  expect(previewRequest).toEqual({
    authorization: `Bearer ${TEST_TOKEN}`,
    pathname: `/api/chat/knowledge-files/${FILE_ID}/pages/2/preview`,
  });
});
