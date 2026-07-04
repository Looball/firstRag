import { describe, expect, it } from "vitest";

import {
  getAuthErrorMessage,
  readAuthResponse,
} from "./auth";

describe("auth helpers", () => {
  it("shows the public demo registration disabled detail", async () => {
    const response = new Response(
      JSON.stringify({
        detail: "当前演示环境暂不开放注册，请使用已提供的账号登录。",
      }),
      {
        status: 403,
        headers: { "Content-Type": "application/json" },
      },
    );

    const data = await readAuthResponse(response);
    const message = getAuthErrorMessage(data, "注册失败，请稍后再试。");

    expect(message).toBe("当前演示环境暂不开放注册，请使用已提供的账号登录。");
  });
});
