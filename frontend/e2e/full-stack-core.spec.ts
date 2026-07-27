import { expect, test } from "@playwright/test";

const USERNAME = process.env.FIRSTRAG_E2E_USERNAME;
const PASSWORD = process.env.FIRSTRAG_E2E_PASSWORD;
const FILE_NAME = "t089-full-stack-source.txt";
const SOURCE_MARKER = "T089 FULL STACK SOURCE";

test("真实服务完成登录、上传、向量化、SSE 回答和引用展示", async ({
  page,
}) => {
  test.setTimeout(120_000);
  expect(USERNAME, "缺少 FIRSTRAG_E2E_USERNAME").toBeTruthy();
  expect(PASSWORD, "缺少 FIRSTRAG_E2E_PASSWORD").toBeTruthy();

  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      consoleErrors.push(message.text());
    }
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.goto("/login");
  await page.getByLabel("用户名").fill(USERNAME!);
  await page.getByLabel("密码").fill(PASSWORD!);
  await page.getByRole("button", { name: "登录", exact: true }).click();

  await expect(page.getByRole("heading", { name: "新对话" })).toBeVisible();
  await expect(page.getByLabel("Knowledge Base")).toHaveValue(/.+/);

  const fileChooserPromise = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "上传文件" }).click();
  const fileChooser = await fileChooserPromise;
  await fileChooser.setFiles({
    name: FILE_NAME,
    mimeType: "text/plain",
    buffer: Buffer.from(
      `FirstRAG credential-free full-stack evidence: ${SOURCE_MARKER}.`,
      "utf-8",
    ),
  });

  const fileDialog = page.getByRole("dialog", { name: "知识库文件" });
  await expect(fileDialog.getByText(FILE_NAME)).toBeVisible();
  await fileDialog
    .getByRole("button", { name: "向量化当前知识库" })
    .click();
  await expect(fileDialog.getByText("知识库向量化完成。")).toBeVisible({
    timeout: 60_000,
  });
  await expect(fileDialog.getByText("已向量化")).toBeVisible();
  await fileDialog.getByRole("button", { name: "关闭文件管理" }).click();

  await page
    .getByLabel("Add To Research Log")
    .fill(`请返回资料中的验收标识 ${SOURCE_MARKER}`);
  await page.getByRole("button", { name: "发送问题" }).click();

  await expect(
    page
      .getByRole("paragraph")
      .filter({
        hasText: `FirstRAG 全栈验收标识是 ${SOURCE_MARKER}。`,
      }),
  ).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("引用来源")).toBeVisible();
  await expect(page.getByText(FILE_NAME)).toBeVisible();
  expect(consoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
});
