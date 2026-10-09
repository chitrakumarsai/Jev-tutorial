import { describe, expect, it } from 'vitest';

import {
  formatCost,
  formatCount,
  formatDate,
  formatDuration,
  formatMoney,
  formatPercent,
} from './format';

describe('formatMoney', () => {
  it.each([
    ['98510.71', '$98,510.71'],
    ['-170.00', '-$170.00'],
    ['0E-8', '$0.00'],
    // Beyond float precision: a Number round-trip would print ...012,345.67 or worse.
    ['123456789012345.675', '$123,456,789,012,345.68'],
  ])('formats %s exactly as %s', (input, expected) => {
    expect(formatMoney(input)).toBe(expected);
  });
});

describe('formatCost', () => {
  it('keeps three significant digits of a fraction of a cent', () => {
    expect(formatCost('0.000754572')).toBe('$0.000755');
    expect(formatCost('0.0025728')).toBe('$0.00257');
  });
});

describe('small formats', () => {
  it('formats probabilities, counts, durations and dates', () => {
    expect(formatPercent(0.7)).toBe('70%');
    expect(formatPercent(1)).toBe('100%');
    expect(formatCount(17966)).toBe('17,966');
    expect(formatDuration(323)).toBe('323 ms');
    expect(formatDuration(34373)).toBe('34.4 s');
    expect(formatDate('2026-10-09T18:30:56.830087+00:00')).toBe('Oct 9, 2026');
    expect(formatDate('not a date')).toBe('not a date');
  });
});
