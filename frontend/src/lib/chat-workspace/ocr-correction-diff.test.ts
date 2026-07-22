import { describe, expect, it } from "vitest";

import {
  buildOcrCorrectionDiff,
  splitChangedOcrLine,
} from "./ocr-correction-diff";

describe("OCR correction diff", () => {
  it("reports no changes for identical OCR text", () => {
    const diff = buildOcrCorrectionDiff("第一行\n第二行", "第一行\n第二行");

    expect(diff.changedRows).toBe(0);
    expect(diff.rows.map((row) => row.status)).toEqual([
      "unchanged",
      "unchanged",
    ]);
  });

  it("keeps common suffix lines aligned around an insertion", () => {
    const diff = buildOcrCorrectionDiff(
      "标题\n引用编号\n结尾",
      "标题\n新增说明\n引用编号\n结尾",
    );

    expect(diff.addedRows).toBe(1);
    expect(diff.rows.map((row) => row.status)).toEqual([
      "unchanged",
      "added",
      "unchanged",
      "unchanged",
    ]);
    expect(diff.rows[2].correctedLineNumber).toBe(3);
  });

  it("distinguishes modified and removed lines", () => {
    const diff = buildOcrCorrectionDiff(
      "页眉\nOCR 编号 T073\n多余行\n页脚",
      "页眉\n人工编号 T075\n页脚",
    );

    expect(diff.modifiedRows).toBe(1);
    expect(diff.removedRows).toBe(1);
    expect(diff.changedRows).toBe(2);
    expect(diff.rows.at(-1)?.status).toBe("unchanged");
  });

  it("highlights only the changed middle of a modified line", () => {
    const segments = splitChangedOcrLine(
      "Reference T073-BETA end",
      "Reference T075-BETA end",
    );

    expect(segments.originalSegments).toEqual([
      { text: "Reference T07", changed: false },
      { text: "3", changed: true },
      { text: "-BETA end", changed: false },
    ]);
    expect(segments.correctedSegments).toEqual([
      { text: "Reference T07", changed: false },
      { text: "5", changed: true },
      { text: "-BETA end", changed: false },
    ]);
  });

  it("normalizes Windows newlines before comparing", () => {
    expect(buildOcrCorrectionDiff("a\r\nb", "a\nb").changedRows).toBe(0);
  });
});
