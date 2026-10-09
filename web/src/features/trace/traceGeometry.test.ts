import { describe, expect, it } from 'vitest';

import { tracePath, type Box } from './traceGeometry';

const box = (left: number, top: number, right: number, bottom: number): Box => ({
  left,
  top,
  right,
  bottom,
});
const W = 1440;
const H = 900;

describe('tracePath', () => {
  it('leaves a figure on the right for a passage on its left', () => {
    const path = tracePath(box(900, 400, 980, 420), box(100, 200, 160, 220), W, H);

    expect(path).toEqual({ d: 'M 900 410 C 530 410, 530 210, 160 210', end: { x: 160, y: 210 } });
  });

  it('leaves to the right for a passage on the right', () => {
    const path = tracePath(box(100, 100, 150, 120), box(600, 300, 700, 320), W, H);

    expect(path?.d).toBe('M 150 110 C 375 110, 375 310, 600 310');
  });

  it('runs vertically when the two are stacked', () => {
    const path = tracePath(box(100, 700, 200, 720), box(120, 100, 180, 120), W, H);

    expect(path).toEqual({ d: 'M 150 700 C 150 410, 150 410, 150 120', end: { x: 150, y: 120 } });
    expect(tracePath(box(100, 100, 200, 120), box(120, 500, 180, 520), W, H)?.d).toBe(
      'M 150 120 C 150 310, 150 310, 150 500',
    );
  });

  it.each([
    ['the passage is off screen', box(100, 950, 160, 970)],
    ['the passage has no size (jsdom)', box(0, 0, 0, 0)],
  ])('draws nothing when %s', (_label, to) => {
    expect(tracePath(box(900, 400, 980, 420), to, W, H)).toBeNull();
  });
});
