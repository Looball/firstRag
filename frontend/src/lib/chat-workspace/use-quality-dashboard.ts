"use client";

import { useCallback, useEffect, useState } from "react";
import * as chatApi from "./api";
import type { QualityDashboard } from "./types";

type UseQualityDashboardOptions = {
  isAdvancedMode: boolean;
  windowDays?: number;
};

/**
 * 判断打开质量看板时是否需要触发首次数据请求。
 */
export function shouldLoadQualityDashboard(
  shouldOpen: boolean,
  dashboard: QualityDashboard | null,
  isLoading: boolean,
) {
  return shouldOpen && dashboard === null && !isLoading;
}

/**
 * 将未知请求异常转换为现有用户可见错误文案。
 */
export function getQualityDashboardErrorMessage(error: unknown) {
  return error instanceof Error
    ? error.message
    : "加载质量看板失败，请稍后再试。";
}

/**
 * 管理高级模式质量看板的缓存、加载、错误和展开状态。
 */
export function useQualityDashboard({
  isAdvancedMode,
  windowDays = 7,
}: UseQualityDashboardOptions) {
  const [isQualityDashboardOpen, setIsQualityDashboardOpen] = useState(false);
  const [qualityDashboard, setQualityDashboard] =
    useState<QualityDashboard | null>(null);
  const [isLoadingQualityDashboard, setIsLoadingQualityDashboard] =
    useState(false);
  const [qualityDashboardError, setQualityDashboardError] = useState("");

  useEffect(() => {
    if (!isAdvancedMode) {
      setIsQualityDashboardOpen(false);
    }
  }, [isAdvancedMode]);

  const loadQualityDashboard = useCallback(async () => {
    if (!isAdvancedMode) {
      return;
    }

    setIsLoadingQualityDashboard(true);
    setQualityDashboardError("");

    try {
      const dashboard = await chatApi.loadQualityDashboard(windowDays);
      setQualityDashboard(dashboard);
    } catch (error) {
      setQualityDashboardError(getQualityDashboardErrorMessage(error));
    } finally {
      setIsLoadingQualityDashboard(false);
    }
  }, [isAdvancedMode, windowDays]);

  const toggleQualityDashboard = useCallback(async () => {
    if (!isAdvancedMode) {
      return;
    }

    const shouldOpen = !isQualityDashboardOpen;
    setIsQualityDashboardOpen(shouldOpen);

    if (
      shouldLoadQualityDashboard(
        shouldOpen,
        qualityDashboard,
        isLoadingQualityDashboard,
      )
    ) {
      await loadQualityDashboard();
    }
  }, [
    isAdvancedMode,
    isLoadingQualityDashboard,
    isQualityDashboardOpen,
    loadQualityDashboard,
    qualityDashboard,
  ]);

  const refreshQualityDashboard = useCallback(async () => {
    await loadQualityDashboard();
  }, [loadQualityDashboard]);

  return {
    isLoadingQualityDashboard,
    isQualityDashboardOpen,
    qualityDashboard,
    qualityDashboardError,
    refreshQualityDashboard,
    toggleQualityDashboard,
  };
}
