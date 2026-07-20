"use client";

import { useCallback, useEffect, useState } from "react";
import { getErrorRetryAfterSeconds } from "./rate-limit";

/** 管理命中 429 后的可复用重试倒计时，仅在倒计时期间启动 timer。 */
export function useRetryAfterCountdown() {
  const [deadlineMs, setDeadlineMs] = useState(0);
  const [retryAfterSeconds, setRetryAfterSeconds] = useState(0);

  useEffect(() => {
    if (deadlineMs <= 0) {
      return;
    }

    let intervalId = 0;
    const updateRemainingSeconds = () => {
      const remainingSeconds = Math.max(
        0,
        Math.ceil((deadlineMs - Date.now()) / 1000),
      );
      setRetryAfterSeconds(remainingSeconds);

      if (remainingSeconds === 0 && intervalId) {
        window.clearInterval(intervalId);
      }
    };

    updateRemainingSeconds();
    intervalId = window.setInterval(updateRemainingSeconds, 1_000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [deadlineMs]);

  const startCountdown = useCallback((seconds: number | null | undefined) => {
    if (!seconds || !Number.isFinite(seconds) || seconds <= 0) {
      return false;
    }

    const normalizedSeconds = Math.ceil(seconds);
    setRetryAfterSeconds(normalizedSeconds);
    setDeadlineMs(Date.now() + normalizedSeconds * 1_000);
    return true;
  }, []);

  const startCountdownFromError = useCallback(
    (error: unknown) => startCountdown(getErrorRetryAfterSeconds(error)),
    [startCountdown],
  );

  return {
    isRateLimited: retryAfterSeconds > 0,
    retryAfterSeconds,
    startCountdown,
    startCountdownFromError,
  };
}
