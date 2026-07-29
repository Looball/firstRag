import { describe, expect, it, vi } from "vitest";
import type { QualityDashboard } from "./types";
import {
  getQualityDashboardErrorMessage,
  shouldLoadQualityDashboard,
} from "./use-quality-dashboard";

vi.mock("@/lib/frontend-api", () => ({
  authenticatedFetch: vi.fn(),
  authenticatedJson: vi.fn(),
  authenticatedText: vi.fn(),
}));

const dashboard = {} as QualityDashboard;

describe("useQualityDashboard helpers", () => {
  it("loads only when opening an uncached dashboard that is not loading", () => {
    expect(shouldLoadQualityDashboard(true, null, false)).toBe(true);
    expect(shouldLoadQualityDashboard(false, null, false)).toBe(false);
    expect(shouldLoadQualityDashboard(true, dashboard, false)).toBe(false);
    expect(shouldLoadQualityDashboard(true, null, true)).toBe(false);
  });

  it("preserves Error messages for user-visible failures", () => {
    expect(
      getQualityDashboardErrorMessage(new Error("质量看板响应格式异常。")),
    ).toBe("质量看板响应格式异常。");
  });

  it("uses the existing fallback for unknown failures", () => {
    expect(getQualityDashboardErrorMessage("network failure")).toBe(
      "加载质量看板失败，请稍后再试。",
    );
  });
});
