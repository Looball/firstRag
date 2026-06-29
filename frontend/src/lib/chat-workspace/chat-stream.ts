import type {
  ChatSource,
  RetrievalState,
} from "./types";
import {
  getAssistantContent,
  getAssistantMessageId,
  getChatSources,
  getRetrievalState,
  getSseAnswerContent,
  parseJsonValue,
  parseSseBlock,
} from "./utils";

const EMPTY_ASSISTANT_FALLBACK = "模型暂时没有返回内容。";

type ChatStreamHandlers = {
  appendAssistantContent: (content: string) => void;
  setAssistantFallback: (content: string) => void;
  setAssistantMessageId: (messageId: string) => void;
  setAssistantRetrieval: (retrieval: RetrievalState) => void;
  setAssistantSources: (sources: ChatSource[]) => void;
  onDone?: () => void;
};

type HandleSseBlockResult = {
  isDone: boolean;
  streamedAnswer: string;
};

function waitForNextPaint() {
  return new Promise<void>((resolve) => {
    requestAnimationFrame(() => resolve());
  });
}

export function applyJsonChatPayload(
  data: unknown,
  handlers: ChatStreamHandlers,
) {
  const answer = getAssistantContent(data);
  const sources = getChatSources(data);
  const retrieval = getRetrievalState(data);
  const messageId = getAssistantMessageId(data);

  if (retrieval) {
    handlers.setAssistantRetrieval(retrieval);
  }
  handlers.setAssistantMessageId(messageId);
  handlers.setAssistantSources(sources);
  handlers.setAssistantFallback(answer || EMPTY_ASSISTANT_FALLBACK);
}

export function handleChatSseBlock(
  block: string,
  streamedAnswer: string,
  handlers: ChatStreamHandlers,
): HandleSseBlockResult {
  const { event, data } = parseSseBlock(block);

  if (event === "retrieval") {
    const retrieval = getRetrievalState(data);

    if (retrieval) {
      handlers.setAssistantRetrieval(retrieval);
    }

    return { isDone: false, streamedAnswer };
  }

  if (event === "sources") {
    handlers.setAssistantSources(getChatSources(data));
    return { isDone: false, streamedAnswer };
  }

  if (event === "answer") {
    const answerContent = getSseAnswerContent(data);

    if (!answerContent) {
      return { isDone: false, streamedAnswer };
    }

    handlers.appendAssistantContent(answerContent);
    return {
      isDone: false,
      streamedAnswer: `${streamedAnswer}${answerContent}`,
    };
  }

  if (event === "done") {
    const parsedData = parseJsonValue(data);
    const retrieval = getRetrievalState(parsedData);
    const doneSources = getChatSources(parsedData);
    const messageId = getAssistantMessageId(parsedData);

    if (retrieval) {
      handlers.setAssistantRetrieval(retrieval);
    }

    handlers.setAssistantMessageId(messageId);
    handlers.setAssistantSources(doneSources);
    handlers.onDone?.();

    const doneAnswer = getAssistantContent(parsedData);

    let nextStreamedAnswer = streamedAnswer;

    if (doneAnswer) {
      if (!streamedAnswer) {
        handlers.appendAssistantContent(doneAnswer);
        nextStreamedAnswer = doneAnswer;
      } else if (doneAnswer !== streamedAnswer) {
        handlers.setAssistantFallback(doneAnswer);
      }
    } else if (!streamedAnswer) {
      handlers.setAssistantFallback(EMPTY_ASSISTANT_FALLBACK);
    }

    return { isDone: true, streamedAnswer: nextStreamedAnswer };
  }

  if (!data) {
    return { isDone: false, streamedAnswer };
  }

  const answerContent = getSseAnswerContent(data);

  if (!answerContent) {
    return { isDone: false, streamedAnswer };
  }

  handlers.appendAssistantContent(answerContent);
  return {
    isDone: false,
    streamedAnswer: `${streamedAnswer}${answerContent}`,
  };
}

export async function streamChatResponse(
  response: Response,
  handlers: ChatStreamHandlers,
  options?: {
    waitForPaint?: () => Promise<void>;
  },
) {
  handlers.appendAssistantContent("");

  const contentType = response.headers.get("Content-Type") || "";

  if (contentType.includes("application/json")) {
    const data = (await response.json()) as unknown;
    applyJsonChatPayload(data, handlers);
    return;
  }

  if (!response.body) {
    const answer = await response.text();
    handlers.setAssistantFallback(answer || EMPTY_ASSISTANT_FALLBACK);
    return;
  }

  const waitForPaint = options?.waitForPaint || waitForNextPaint;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const isSseStream = contentType.includes("text/event-stream");
  let streamedAnswer = "";
  let sseBuffer = "";
  let shouldStop = false;

  while (!shouldStop) {
    const { done, value } = await reader.read();

    if (done) {
      break;
    }

    const chunk = decoder.decode(value, { stream: true });

    if (chunk && isSseStream) {
      sseBuffer += chunk;

      while (true) {
        const separatorIndex = sseBuffer.search(/\r?\n\r?\n/);

        if (separatorIndex === -1) {
          break;
        }

        const block = sseBuffer.slice(0, separatorIndex);
        const separatorMatch = sseBuffer
          .slice(separatorIndex)
          .match(/^\r?\n\r?\n/);
        sseBuffer = sseBuffer.slice(
          separatorIndex + (separatorMatch?.[0].length || 2),
        );

        const result = handleChatSseBlock(
          block,
          streamedAnswer,
          handlers,
        );
        streamedAnswer = result.streamedAnswer;

        if (result.isDone) {
          shouldStop = true;
          await reader.cancel();
          break;
        }
      }

      await waitForPaint();
      continue;
    }

    if (chunk) {
      streamedAnswer += chunk;
      handlers.appendAssistantContent(chunk);
      await waitForPaint();
    }
  }

  const finalChunk = decoder.decode();

  if (finalChunk && isSseStream) {
    sseBuffer += finalChunk;
  } else if (finalChunk) {
    streamedAnswer += finalChunk;
    handlers.appendAssistantContent(finalChunk);
    await waitForPaint();
  }

  if (!shouldStop && isSseStream && sseBuffer.trim()) {
    const result = handleChatSseBlock(
      sseBuffer.trim(),
      streamedAnswer,
      handlers,
    );
    streamedAnswer = result.streamedAnswer;
    await waitForPaint();
  }

  if (!streamedAnswer) {
    handlers.setAssistantFallback(EMPTY_ASSISTANT_FALLBACK);
  }
}
