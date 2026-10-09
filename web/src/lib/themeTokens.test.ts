import { describe, expect, it } from 'vitest';

import { readThemePairs } from './themeTokens';

describe('readThemePairs', () => {
  it('reads light-dark() custom properties', () => {
    const css = `:root {
      --color-paper: light-dark(#F7F3EA, #101827);
      --color-ink:light-dark( #1b2333 ,#ede7da );
      --space-1: 4px;
    }`;

    const pairs = readThemePairs(css);

    expect(pairs.get('--color-paper')).toEqual({ light: '#f7f3ea', dark: '#101827' });
    expect(pairs.get('--color-ink')).toEqual({ light: '#1b2333', dark: '#ede7da' });
    expect(pairs.has('--space-1')).toBe(false);
  });

  it.each([
    '--color-x: oklch(50% 0.1 250);',
    '--color-x: light-dark(#fff, #000);',
    '--color-x: #1b2333;',
  ])('rejects a colour token it cannot check: %s', (css) => {
    expect(() => readThemePairs(css)).toThrow(/--color-x must be light-dark\(#rrggbb, #rrggbb\)/);
  });

  it('rejects a token defined twice', () => {
    const css = '--a: light-dark(#000000, #ffffff); --a: light-dark(#111111, #eeeeee);';

    expect(() => readThemePairs(css)).toThrow(/--a is defined more than once/);
  });
});
