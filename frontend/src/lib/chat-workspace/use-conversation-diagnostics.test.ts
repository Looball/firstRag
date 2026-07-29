import { describe, expect, it, vi } from "vitest";
import type { MessageDiagnostic } from "./types";
import {
  buildDiagnosticPanelKey,
  findMessageDiagnostic,
  shouldLoadConversationDiagnostics,
} from "./use-conversation-diagnostics";

vi.mock("@/lib/frontend-api", () => ({
  authenticatedFetch: vi.fn(),
  authenticatedJson: vi.fn(),
  authenticatedText: vi.fn(),
}));

const diagnostics = [
  {
    messageId: "message-1",
  } as MessageDiagnostic,
];

describe("useConversationDiagnostics helpers", () => {
  it("builds a conversation-scoped diagnostic panel key", () => {
    expect(buildDiagnosticPanelKey("conversation-1", "message-2")).toBe(
      "conversation-1:message-2",
    );
  });

  it("finds only the persisted target message diagnostic", () => {
    expect(findMessageDiagnostic(diagnostics, "message-1")).toBe(
      diagnostics[0],
    );
    expect(findMessageDiagnostic(diagnostics, "message-2")).toBeNull();
    expect(findMessageDiagnostic(diagnostics)).toBeNull();
  });

  it("loads only when opening an uncached conversation that is not loading", () => {
    expect(
      shouldLoadConversationDiagnostics(true, undefined, false),
    ).toBe(true);
    expect(shouldLoadConversationDiagnostics(false, undefined, false)).toBe(
      false,
    );
    expect(shouldLoadConversationDiagnostics(true, [], false)).toBe(false);
    expect(shouldLoadConversationDiagnostics(true, undefined, true)).toBe(
      false,
    );
  });
});
