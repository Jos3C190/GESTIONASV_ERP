export interface GridItemRect {
  index: number;
  left: number;
  top: number;
  width: number;
  height: number;
}

export function gridNavigationIndex(
  layout: GridItemRect[],
  currentIndex: number,
  key: string
): number {
  const current = layout.find((entry) => entry.index === currentIndex);
  if (!current) return currentIndex;

  const tolerance = Math.max(8, current.height * 0.4);
  const sameRow = layout
    .filter((entry) => Math.abs(entry.top - current.top) <= tolerance)
    .sort((left, right) => left.left - right.left);

  if (key === 'ArrowLeft' || key === 'ArrowRight') {
    const currentPosition = sameRow.findIndex((entry) => entry.index === currentIndex);
    if (key === 'ArrowLeft') return currentPosition > 0 ? sameRow[currentPosition - 1]!.index : currentIndex;
    return currentPosition >= 0 && currentPosition < sameRow.length - 1
      ? sameRow[currentPosition + 1]!.index
      : currentIndex;
  }

  if (key !== 'ArrowUp' && key !== 'ArrowDown') return currentIndex;
  const rows = layout
    .filter((entry) => key === 'ArrowUp' ? entry.top < current.top - tolerance : entry.top > current.top + tolerance)
    .map((entry) => entry.top);
  if (!rows.length) return currentIndex;

  const targetTop = key === 'ArrowUp' ? Math.max(...rows) : Math.min(...rows);
  const currentCenter = current.left + current.width / 2;
  return layout
    .filter((entry) => Math.abs(entry.top - targetTop) <= tolerance)
    .sort((left, right) =>
      Math.abs(left.left + left.width / 2 - currentCenter) -
      Math.abs(right.left + right.width / 2 - currentCenter)
    )[0]?.index ?? currentIndex;
}
