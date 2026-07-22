export type OcrCorrectionDiffStatus =
  | "added"
  | "modified"
  | "removed"
  | "unchanged";

export type OcrCorrectionDiffSegment = {
  text: string;
  changed: boolean;
};

export type OcrCorrectionDiffRow = {
  status: OcrCorrectionDiffStatus;
  originalLineNumber?: number;
  correctedLineNumber?: number;
  originalSegments: OcrCorrectionDiffSegment[];
  correctedSegments: OcrCorrectionDiffSegment[];
};

export type OcrCorrectionDiff = {
  rows: OcrCorrectionDiffRow[];
  changedRows: number;
  addedRows: number;
  removedRows: number;
  modifiedRows: number;
};

type LineAnchor = {
  originalIndex: number;
  correctedIndex: number;
};

/** 将 OCR 文本规范为稳定的逐行比较输入。 */
function splitOcrLines(value: string) {
  const normalized = value.replace(/\r\n?/g, "\n");
  return normalized ? normalized.split("\n") : [];
}

/** 选择两侧都只出现一次、且顺序不交叉的相同行作为线性空间锚点。 */
function findOrderedLineAnchors(
  originalLines: string[],
  correctedLines: string[],
): LineAnchor[] {
  const originalCounts = new Map<string, number>();
  const correctedIndexes = new Map<string, number>();
  for (const line of originalLines) {
    originalCounts.set(line, (originalCounts.get(line) ?? 0) + 1);
  }
  for (let index = 0; index < correctedLines.length; index += 1) {
    const line = correctedLines[index];
    correctedIndexes.set(
      line,
      correctedIndexes.has(line) ? -1 : index,
    );
  }

  const candidates: LineAnchor[] = [];
  for (let originalIndex = 0; originalIndex < originalLines.length; originalIndex += 1) {
    const line = originalLines[originalIndex];
    const correctedIndex = correctedIndexes.get(line);
    if (originalCounts.get(line) === 1 && correctedIndex !== undefined && correctedIndex >= 0) {
      candidates.push({ originalIndex, correctedIndex });
    }
  }
  if (candidates.length < 2) {
    return candidates;
  }

  const tails: number[] = [];
  const previous = new Array<number>(candidates.length).fill(-1);
  for (let index = 0; index < candidates.length; index += 1) {
    let low = 0;
    let high = tails.length;
    while (low < high) {
      const middle = Math.floor((low + high) / 2);
      if (
        candidates[tails[middle]].correctedIndex <
        candidates[index].correctedIndex
      ) {
        low = middle + 1;
      } else {
        high = middle;
      }
    }
    if (low > 0) previous[index] = tails[low - 1];
    tails[low] = index;
  }

  const anchors: LineAnchor[] = [];
  let cursor = tails.at(-1) ?? -1;
  while (cursor >= 0) {
    anchors.push(candidates[cursor]);
    cursor = previous[cursor];
  }
  return anchors.reverse();
}

/** 将一行拆成未变化前后缀和中间变化段，便于紧凑高亮。 */
export function splitChangedOcrLine(
  original: string,
  corrected: string,
): {
  originalSegments: OcrCorrectionDiffSegment[];
  correctedSegments: OcrCorrectionDiffSegment[];
} {
  if (original === corrected) {
    const segments = original ? [{ text: original, changed: false }] : [];
    return { originalSegments: segments, correctedSegments: segments };
  }

  const maximumPrefix = Math.min(original.length, corrected.length);
  let prefixLength = 0;
  while (
    prefixLength < maximumPrefix &&
    original[prefixLength] === corrected[prefixLength]
  ) {
    prefixLength += 1;
  }

  const maximumSuffix = Math.min(
    original.length - prefixLength,
    corrected.length - prefixLength,
  );
  let suffixLength = 0;
  while (
    suffixLength < maximumSuffix &&
    original[original.length - suffixLength - 1] ===
      corrected[corrected.length - suffixLength - 1]
  ) {
    suffixLength += 1;
  }

  /** 忽略空字符串 segment，减少 React 渲染节点。 */
  function segmentsFor(value: string): OcrCorrectionDiffSegment[] {
    const prefix = value.slice(0, prefixLength);
    const changedEnd = suffixLength ? value.length - suffixLength : value.length;
    const changed = value.slice(prefixLength, changedEnd);
    const suffix = suffixLength ? value.slice(value.length - suffixLength) : "";
    return [
      ...(prefix ? [{ text: prefix, changed: false }] : []),
      ...(changed ? [{ text: changed, changed: true }] : []),
      ...(suffix ? [{ text: suffix, changed: false }] : []),
    ];
  }

  return {
    originalSegments: segmentsFor(original),
    correctedSegments: segmentsFor(corrected),
  };
}

/**
 * 构造线性空间的页级 OCR 差异。
 *
 * 先固定相同的首尾行，再对中间区域逐行配对；这样常见的插入、删除和
 * 局部修改能保持清晰，同时避免长页面使用 O(n*m) LCS 阻塞输入。
 */
export function buildOcrCorrectionDiff(
  originalText: string,
  correctedText: string,
): OcrCorrectionDiff {
  const originalLines = splitOcrLines(originalText);
  const correctedLines = splitOcrLines(correctedText);
  const maximumPrefix = Math.min(originalLines.length, correctedLines.length);
  let prefixLength = 0;
  while (
    prefixLength < maximumPrefix &&
    originalLines[prefixLength] === correctedLines[prefixLength]
  ) {
    prefixLength += 1;
  }

  const maximumSuffix = Math.min(
    originalLines.length - prefixLength,
    correctedLines.length - prefixLength,
  );
  let suffixLength = 0;
  while (
    suffixLength < maximumSuffix &&
    originalLines[originalLines.length - suffixLength - 1] ===
      correctedLines[correctedLines.length - suffixLength - 1]
  ) {
    suffixLength += 1;
  }

  const rows: OcrCorrectionDiffRow[] = [];
  for (let index = 0; index < prefixLength; index += 1) {
    const text = originalLines[index];
    const segments = text ? [{ text, changed: false }] : [];
    rows.push({
      status: "unchanged",
      originalLineNumber: index + 1,
      correctedLineNumber: index + 1,
      originalSegments: segments,
      correctedSegments: segments,
    });
  }

  const originalMiddleEnd = originalLines.length - suffixLength;
  const correctedMiddleEnd = correctedLines.length - suffixLength;
  const originalMiddle = originalLines.slice(prefixLength, originalMiddleEnd);
  const correctedMiddle = correctedLines.slice(prefixLength, correctedMiddleEnd);
  /** 对相邻锚点之间的行按位置配对，额外行明确标记新增或删除。 */
  function appendGap(
    originalStart: number,
    originalEnd: number,
    correctedStart: number,
    correctedEnd: number,
  ) {
    const gapLength = Math.max(
      originalEnd - originalStart,
      correctedEnd - correctedStart,
    );
    for (let offset = 0; offset < gapLength; offset += 1) {
      const originalIndex = originalStart + offset;
      const correctedIndex = correctedStart + offset;
      const original =
        originalIndex < originalEnd ? originalMiddle[originalIndex] : undefined;
      const corrected =
        correctedIndex < correctedEnd
          ? correctedMiddle[correctedIndex]
          : undefined;
      if (original === undefined) {
        rows.push({
          status: "added",
          correctedLineNumber: prefixLength + correctedIndex + 1,
          originalSegments: [],
          correctedSegments: corrected
            ? [{ text: corrected, changed: true }]
            : [],
        });
        continue;
      }
      if (corrected === undefined) {
        rows.push({
          status: "removed",
          originalLineNumber: prefixLength + originalIndex + 1,
          originalSegments: original
            ? [{ text: original, changed: true }]
            : [],
          correctedSegments: [],
        });
        continue;
      }
      const segments = splitChangedOcrLine(original, corrected);
      rows.push({
        status: original === corrected ? "unchanged" : "modified",
        originalLineNumber: prefixLength + originalIndex + 1,
        correctedLineNumber: prefixLength + correctedIndex + 1,
        ...segments,
      });
    }
  }

  let originalCursor = 0;
  let correctedCursor = 0;
  for (const anchor of findOrderedLineAnchors(originalMiddle, correctedMiddle)) {
    appendGap(
      originalCursor,
      anchor.originalIndex,
      correctedCursor,
      anchor.correctedIndex,
    );
    const text = originalMiddle[anchor.originalIndex];
    const segments = text ? [{ text, changed: false }] : [];
    rows.push({
      status: "unchanged",
      originalLineNumber: prefixLength + anchor.originalIndex + 1,
      correctedLineNumber: prefixLength + anchor.correctedIndex + 1,
      originalSegments: segments,
      correctedSegments: segments,
    });
    originalCursor = anchor.originalIndex + 1;
    correctedCursor = anchor.correctedIndex + 1;
  }
  appendGap(
    originalCursor,
    originalMiddle.length,
    correctedCursor,
    correctedMiddle.length,
  );

  for (let index = 0; index < suffixLength; index += 1) {
    const originalIndex = originalLines.length - suffixLength + index;
    const correctedIndex = correctedLines.length - suffixLength + index;
    const text = originalLines[originalIndex];
    const segments = text ? [{ text, changed: false }] : [];
    rows.push({
      status: "unchanged",
      originalLineNumber: originalIndex + 1,
      correctedLineNumber: correctedIndex + 1,
      originalSegments: segments,
      correctedSegments: segments,
    });
  }

  let addedRows = 0;
  let removedRows = 0;
  let modifiedRows = 0;
  for (const row of rows) {
    if (row.status === "added") addedRows += 1;
    if (row.status === "removed") removedRows += 1;
    if (row.status === "modified") modifiedRows += 1;
  }
  return {
    rows,
    addedRows,
    removedRows,
    modifiedRows,
    changedRows: addedRows + removedRows + modifiedRows,
  };
}
