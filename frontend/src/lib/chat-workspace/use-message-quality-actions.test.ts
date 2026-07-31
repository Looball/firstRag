import { describe, expect, it, vi } from "vitest";
import type {
  ChatSession,
  MessageFeedback,
} from "./types";
import {
  serializeEvalCaseDraft,
  updateMessageFeedbackInSessions,
} from "./use-message-quality-actions";

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

describe("useMessageQualityActions helpers", () => {
  it("updates feedback only on the target session message", () => {
    const feedback: MessageFeedback = {
      id: "feedback-1",
      rating: "negative",
      reason: "hallucination",
      note: "事实不一致",
    };
    const updated = updateMessageFeedbackInSessions(
      sessions,
      "session-1",
      "message-1",
      feedback,
    );

    expect(updated[0].messages[0].feedback).toEqual(feedback);
    expect(updated[1]).toBe(sessions[1]);
    expect(sessions[0].messages[0].feedback).toBeUndefined();
  });

  it("serializes eval drafts with normalized and fallback file names", () => {
    expect(
      serializeEvalCaseDraft({ id: "  eval-case-1  ", query: "问题" }, "m-1"),
    ).toEqual({
      fileName: "eval-case-1.json",
      content: '{\n  "id": "  eval-case-1  ",\n  "query": "问题"\n}\n',
    });
    expect(serializeEvalCaseDraft({ query: "问题" }, "m-2").fileName).toBe(
      "draft_message_m-2.json",
    );
  });
});
