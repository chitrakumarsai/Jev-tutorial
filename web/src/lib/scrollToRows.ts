/**
 * How far to scroll so a group of rows sits in view: centred together when they fit in the
 * viewport, otherwise the first row centred. Pure, so it can be tested without layout.
 */
export function scrollOffset(
  rects: readonly { top: number; bottom: number }[],
  viewportHeight: number,
): number {
  const [first] = rects;
  if (!first) return 0;
  const top = Math.min(...rects.map((r) => r.top));
  const bottom = Math.max(...rects.map((r) => r.bottom));
  const [from, to] = bottom - top <= viewportHeight ? [top, bottom] : [first.top, first.bottom];
  return (from + to) / 2 - viewportHeight / 2;
}
