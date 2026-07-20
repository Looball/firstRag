import { describe, expect, it } from "vitest";

import {
  formatRateLimitMessage,
  getErrorRetryAfterSeconds,
  parseRetryAfterSeconds,
} from "./rate-limit";

describe("rate limit helpers", () => {
  it("parses numeric and HTTP-date Retry-After values", () => {
    expect(parseRetryAfterSeconds("27")).toBe(27);
    expect(parseRetryAfterSeconds("1.2")).toBe(2);
    expect(
      parseRetryAfterSeconds("Wed, 21 Oct 2015 07:28:00 GMT", 1_445_412_470_000),
    ).toBe(10);
  });

  it("rejects missing, expired, and malformed Retry-After values", () => {
    expect(parseRetryAfterSeconds(null)).toBeNull();
    expect(parseRetryAfterSeconds("0")).toBeNull();
    expect(parseRetryAfterSeconds("not-a-date")).toBeNull();
  });

  it("adds an actionable countdown without duplicating the old retry hint", () => {
    expect(formatRateLimitMessage("聊天请求过于频繁，请稍后再试。", 60)).toBe(
      "聊天请求过于频繁。请在 60 秒后重试。",
    );
    expect(formatRateLimitMessage("请求失败", null)).toBe("请求失败");
  });

  it("reads retry seconds only from compatible errors", () => {
    expect(getErrorRetryAfterSeconds({ retryAfterSeconds: 30 })).toBe(30);
    expect(getErrorRetryAfterSeconds({ retryAfterSeconds: 0 })).toBeNull();
    expect(getErrorRetryAfterSeconds(new Error("failed"))).toBeNull();
  });
});
