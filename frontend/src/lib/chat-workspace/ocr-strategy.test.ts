import { describe, expect, it } from "vitest";

import {
  formatOcrStrategyDetail,
  formatOcrStrategyLabel,
} from "./ocr-strategy";

describe("ocr strategy formatting", () => {
  it("formats known and unknown strategy labels", () => {
    expect(formatOcrStrategyLabel("single_block_binary")).toBe("二值化单块文本");
    expect(formatOcrStrategyLabel("future_strategy")).toBe("标准 OCR");
  });

  it("shows rotation only when applied", () => {
    expect(formatOcrStrategyDetail(3, 0)).toBe("PSM 3");
    expect(formatOcrStrategyDetail(6, 90)).toBe("PSM 6 · 90°");
  });
});
