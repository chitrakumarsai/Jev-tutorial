import { describe, expect, it } from 'vitest';

import { contrastRatio } from '../lib/color';
import { readThemePairs } from '../lib/themeTokens';
import tokensCss from './tokens.css?raw';

const pairs = readThemePairs(tokensCss);
const THEMES = ['light', 'dark'] as const;

// WCAG 2.2: 4.5:1 for body text (1.4.3), 3:1 for UI parts and graphics (1.4.11).
const TEXT_MIN = 4.5;
const UI_MIN = 3;
const BACKGROUNDS = ['--color-paper', '--color-surface'] as const;
const TEXT_TOKENS = [
  '--color-ink',
  '--color-muted',
  '--color-verified',
  '--color-review',
  '--color-discrepancy',
  '--color-jev',
  '--color-llm',
] as const;
const UI_TOKENS = ['--color-focus'] as const;

function colour(token: string, theme: (typeof THEMES)[number]): string {
  const pair = pairs.get(token);
  if (!pair) throw new Error(`${token} is not defined with light-dark() in tokens.css`);
  return pair[theme];
}

describe('tokens.css', () => {
  it('defines every colour token for both themes', () => {
    for (const token of [...BACKGROUNDS, ...TEXT_TOKENS, ...UI_TOKENS, '--color-rule']) {
      expect(pairs.has(token), token).toBe(true);
    }
  });

  describe.each(THEMES)('%s theme', (theme) => {
    it.each(TEXT_TOKENS.flatMap((fg) => BACKGROUNDS.map((bg) => [fg, bg] as const)))(
      '%s on %s meets 4.5:1',
      (fg, bg) => {
        expect(contrastRatio(colour(fg, theme), colour(bg, theme))).toBeGreaterThanOrEqual(
          TEXT_MIN,
        );
      },
    );

    it.each(UI_TOKENS.flatMap((fg) => BACKGROUNDS.map((bg) => [fg, bg] as const)))(
      '%s on %s meets 3:1',
      (fg, bg) => {
        expect(contrastRatio(colour(fg, theme), colour(bg, theme))).toBeGreaterThanOrEqual(UI_MIN);
      },
    );
  });
});
