const OCR_STRATEGY_LABELS: Record<string, string> = {
  baseline_auto: "原图自动布局",
  single_block_gray: "灰度单块文本",
  single_block_binary: "二值化单块文本",
  rotate_90_gray: "旋转 90° 灰度",
  rotate_180_gray: "旋转 180° 灰度",
  rotate_270_gray: "旋转 270° 灰度",
};

/** 返回面向用户的 OCR 候选策略名称。 */
export function formatOcrStrategyLabel(strategy: string) {
  return OCR_STRATEGY_LABELS[strategy] || "标准 OCR";
}

/** 组合 PSM 与旋转信息，便于在紧凑列表中解释选优结果。 */
export function formatOcrStrategyDetail(psm: number, rotation: number) {
  return `PSM ${psm}${rotation ? ` · ${rotation}°` : ""}`;
}
