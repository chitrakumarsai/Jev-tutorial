/** Where to draw the line from a figure to its passage, in viewport coordinates. Pure. */
export interface Box {
  readonly left: number;
  readonly top: number;
  readonly right: number;
  readonly bottom: number;
}

export interface Point {
  readonly x: number;
  readonly y: number;
}

export interface TracePath {
  readonly d: string;
  readonly end: Point;
}

function isVisible(box: Box, width: number, height: number): boolean {
  const hasSize = box.right > box.left && box.bottom > box.top;
  const isOnScreen = box.bottom > 0 && box.top < height && box.right > 0 && box.left < width;
  return hasSize && isOnScreen;
}

const midX = (box: Box) => (box.left + box.right) / 2;
const midY = (box: Box) => (box.top + box.bottom) / 2;
const round = (n: number) => Math.round(n * 10) / 10;

/**
 * A curve from the figure's nearest side to the passage's. Side by side, it leaves and
 * arrives horizontally; stacked (narrow screens), vertically. Null when either end is off
 * screen or has no size: a line to nowhere would mislead.
 */
export function tracePath(from: Box, to: Box, width: number, height: number): TracePath | null {
  if (!isVisible(from, width, height) || !isVisible(to, width, height)) return null;
  let start: Point;
  let end: Point;
  let horizontal = true;
  if (to.right <= from.left) {
    start = { x: from.left, y: midY(from) };
    end = { x: to.right, y: midY(to) };
  } else if (to.left >= from.right) {
    start = { x: from.right, y: midY(from) };
    end = { x: to.left, y: midY(to) };
  } else {
    horizontal = false;
    const isAbove = to.bottom <= from.top;
    start = { x: midX(from), y: isAbove ? from.top : from.bottom };
    end = { x: midX(to), y: isAbove ? to.bottom : to.top };
  }
  const c1 = horizontal
    ? { x: (start.x + end.x) / 2, y: start.y }
    : { x: start.x, y: (start.y + end.y) / 2 };
  const c2 = horizontal
    ? { x: (start.x + end.x) / 2, y: end.y }
    : { x: end.x, y: (start.y + end.y) / 2 };
  const p = (pt: Point) => `${String(round(pt.x))} ${String(round(pt.y))}`;
  return { d: `M ${p(start)} C ${p(c1)}, ${p(c2)}, ${p(end)}`, end };
}
