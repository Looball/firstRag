import { describe, expect, it } from "vitest";

import {
  DEFAULT_USER_LLM_SETTINGS,
  toUserLLMModelDiscoveryPayload,
} from "./user-settings";

describe("toUserLLMModelDiscoveryPayload", () => {
  it("omits a stale selected model while retaining the new API Key", () => {
    const payload = toUserLLMModelDiscoveryPayload(
      { ...DEFAULT_USER_LLM_SETTINGS, provider: "qwen", model: "old-model" },
      " new-api-key ",
      false
    );

    expect(payload).not.toHaveProperty("model");
    expect(payload).toMatchObject({
      credential_mode: "user",
      provider: "qwen",
      api_key: "new-api-key",
    });
  });
});
