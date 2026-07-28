import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import {
  SidebarAccountModeControls,
  type SidebarAccountModeControlsProps,
} from "./SidebarAccountModeControls";

const baseProps: SidebarAccountModeControlsProps = {
  currentUsername: "researcher",
  isAdvancedMode: false,
  onLogout: () => undefined,
  onAdvancedModeChange: () => undefined,
};

describe("SidebarAccountModeControls", () => {
  it("renders the account settings and logout controls", () => {
    const markup = renderToStaticMarkup(
      <SidebarAccountModeControls {...baseProps} />,
    );

    expect(markup).toContain("FirstRAG");
    expect(markup).toContain("researcher");
    expect(markup).toContain('href="/settings"');
    expect(markup).toContain("打开用户设置");
    expect(markup).toContain("退出");
  });

  it("falls back to the signed-in label when the username is empty", () => {
    const markup = renderToStaticMarkup(
      <SidebarAccountModeControls {...baseProps} currentUsername="" />,
    );

    expect(markup).toContain("已登录");
  });

  it("marks the selected normal or advanced mode as pressed", () => {
    const normalMarkup = renderToStaticMarkup(
      <SidebarAccountModeControls {...baseProps} />,
    );
    const advancedMarkup = renderToStaticMarkup(
      <SidebarAccountModeControls {...baseProps} isAdvancedMode />,
    );

    expect(normalMarkup).toMatch(/aria-pressed="true"[^>]*>普通<\/button>/);
    expect(normalMarkup).toMatch(/aria-pressed="false"[^>]*>高级<\/button>/);
    expect(advancedMarkup).toMatch(/aria-pressed="false"[^>]*>普通<\/button>/);
    expect(advancedMarkup).toMatch(/aria-pressed="true"[^>]*>高级<\/button>/);
  });
});
