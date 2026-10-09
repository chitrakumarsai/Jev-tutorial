import { describe, expect, it } from 'vitest';

import { contrastRatio, parseHex } from './color';

describe('parseHex', () => {
  it('parses six-digit hex in either case', () => {
    expect(parseHex('#1b2333')).toEqual([0x1b, 0x23, 0x33]);
    expect(parseHex('#F7F3EA')).toEqual([0xf7, 0xf3, 0xea]);
  });

  it.each(['1b2333', '#fff', '#12345g', '#1234567', ''])('rejects %j', (value) => {
    expect(() => parseHex(value)).toThrow(/hex colour/);
  });
});

describe('contrastRatio', () => {
  it('is 21 for black on white and 1 for identical colours', () => {
    expect(contrastRatio('#000000', '#ffffff')).toBeCloseTo(21, 5);
    expect(contrastRatio('#777777', '#777777')).toBeCloseTo(1, 5);
  });

  it('is symmetric', () => {
    expect(contrastRatio('#1f7a4d', '#f7f3ea')).toBeCloseTo(
      contrastRatio('#f7f3ea', '#1f7a4d'),
      10,
    );
  });

  it('matches the WCAG reference value for mid grey on white', () => {
    // #767676 on white is the classic 4.54:1 boundary case.
    expect(contrastRatio('#767676', '#ffffff')).toBeCloseTo(4.54, 2);
  });
});
