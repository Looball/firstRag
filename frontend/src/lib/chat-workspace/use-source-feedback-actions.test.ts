import { describe, expect, it, vi } from "vitest";
import type {
  ChatSession,
  MessageSourceFeedback,
} from "./types";
import { updateSourceFeedbackInSessions } from "./use-source-feedback-actions";

vi.mock("@/lib/frontend-api", () => ({
  authenticatedFetch: vi.fn(),
  authenticatedJson: vi.fn(),
  authenticatedText: vi.fn(),
}));

const sessions: ChatSession[] = [
  {
    id: "session-1",
    title: "目标会话",
    knowledgeBaseId: "kb-1",
    messages: [
      {
        id: "message-1",
        role: "assistant",
        content: "回答",
        sources: [
          {
            title: "显式索引",
            content: "",
            metadata: "",
            index: 4,
          },
          {
            title: "位置索引",
            content: "",
            metadata: "",
          },
        ],
      },
    ],
  },
  {
    id: "session-2",
    title: "其他会话",
    knowledgeBaseId: "kb-1",
    messages: [],
  },
];

describe("useSourceFeedbackActions helpers", () => {
  it("matches source feedback by explicit index or fallback position", () => {
    const explicitFeedback: MessageSourceFeedback = {
      sourceIndex: 4,
      rating: "useful",
    };
    const fallbackFeedback: MessageSourceFeedback = {
      sourceIndex: 1,
      rating: "irrelevant",
    };
    const withExplicit = updateSourceFeedbackInSessions(
      sessions,
      "session-1",
      "message-1",
      4,
      explicitFeedback,
    );
    const withFallback = updateSourceFeedbackInSessions(
      withExplicit,
      "session-1",
      "message-1",
      1,
      fallbackFeedback,
    );

    expect(withFallback[0].messages[0].sources?.[0].feedback).toEqual(
      explicitFeedback,
    );
    expect(withFallback[0].messages[0].sources?.[1].feedback).toEqual(
      fallbackFeedback,
    );
  });
});
