import { describe, expect, it } from 'vitest';

import { scrollOffset } from './scrollToRows';

describe('scrollOffset', () => {
  it('centres rows that fit in the viewport together', () => {
    expect(
      scrollOffset(
        [
          { top: 900, bottom: 1000 },
          { top: 300, bottom: 400 },
        ],
        1000,
      ),
    ).toBe(150);
  });

  it('centres the first row when the group is taller than the viewport', () => {
    expect(
      scrollOffset(
        [
          { top: 2000, bottom: 2100 },
          { top: 100, bottom: 200 },
        ],
        1000,
      ),
    ).toBe(1550);
  });

  it('does not scroll without rows', () => {
    expect(scrollOffset([], 1000)).toBe(0);
  });
});
