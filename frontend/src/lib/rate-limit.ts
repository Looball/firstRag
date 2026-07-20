const RETRY_AFTER_SECONDS_PATTERN = /^\d+(?:\.\d+)?$/;

/** 将 Retry-After 响应头解析为向上取整的秒数。 */
export function parseRetryAfterSeconds(
  value: string | null,
  nowMs = Date.now(),
) {
  if (!value) {
    return null;
  }

  const normalizedValue = value.trim();

  if (RETRY_AFTER_SECONDS_PATTERN.test(normalizedValue)) {
    const seconds = Math.ceil(Number(normalizedValue));
    return Number.isFinite(seconds) && seconds > 0 ? seconds : null;
  }

  const retryAtMs = Date.parse(normalizedValue);

  if (!Number.isFinite(retryAtMs)) {
    return null;
  }

  return Math.max(1, Math.ceil((retryAtMs - nowMs) / 1000));
}

/** 从 HTTP 响应读取可选的 Retry-After 秒数。 */
export function getResponseRetryAfterSeconds(response: Response) {
  return parseRetryAfterSeconds(response.headers.get("Retry-After"));
}

/** 为 429 错误补充明确的重试倒计时提示。 */
export function formatRateLimitMessage(
  message: string,
  retryAfterSeconds: number | null,
) {
  const normalizedMessage = message.trim() || "请求过于频繁，请稍后再试。";

  if (!retryAfterSeconds || retryAfterSeconds <= 0) {
    return normalizedMessage;
  }

  const baseMessage = normalizedMessage
    .replace(/[，,]?请稍后再试。?$/, "")
    .trim();
  return `${baseMessage}${baseMessage.endsWith("。") ? "" : "。"}请在 ${retryAfterSeconds} 秒后重试。`;
}

/** 从未知错误中安全读取 Retry-After 秒数。 */
export function getErrorRetryAfterSeconds(error: unknown) {
  if (
    typeof error !== "object" ||
    error === null ||
    !("retryAfterSeconds" in error)
  ) {
    return null;
  }

  const retryAfterSeconds = (error as { retryAfterSeconds?: unknown })
    .retryAfterSeconds;

  return typeof retryAfterSeconds === "number" &&
    Number.isFinite(retryAfterSeconds) &&
    retryAfterSeconds > 0
    ? Math.ceil(retryAfterSeconds)
    : null;
}
