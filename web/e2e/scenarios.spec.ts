import { expect, type Page, test } from '@playwright/test';

import { openApp, replayToResults, settle, THEMES } from './support';

const WIDTHS = [320, 768, 1024, 1440] as const;
const SHOT_WIDTHS = new Set([320, 1440]); // full-page baselines (~1 MB each) at the extremes
const HEIGHT = 900;
const SCENARIOS = [
  { id: 's2', title: 'Clause risk review' },
  { id: 's3', title: 'Citation check' },
] as const;

async function hasHorizontalOverflow(page: Page): Promise<boolean> {
  return page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
}

async function replay(page: Page, title: string): Promise<void> {
  await openApp(page);
  await page.getByLabel('Scenario').selectOption({ label: title });
  await replayToResults(page);
  await settle(page);
}

for (const theme of THEMES) {
  test.describe(`${theme} theme`, () => {
    test.use({ colorScheme: theme, contextOptions: { reducedMotion: 'reduce' } });
    for (const { id, title } of SCENARIOS) {
      for (const width of WIDTHS) {
        test(`${id} results at ${String(width)}px`, async ({ page }) => {
          await page.setViewportSize({ width, height: HEIGHT });
          await replay(page, title);

          expect(await hasHorizontalOverflow(page)).toBe(false);
          if (SHOT_WIDTHS.has(width)) {
            await expect(page).toHaveScreenshot(`${id}-results-${theme}-${String(width)}.png`, {
              fullPage: true,
              mask: [page.getByRole('row', { name: /Time in this run/ })],
            });
          }
        });
      }
    }
  });
}

test.describe('evidence highlights', () => {
  test.use({ contextOptions: { reducedMotion: 'reduce' } });

  test('s2 marks the liability clause both sides point at', async ({ page }) => {
    await replay(page, 'Clause risk review');

    const marks = page.locator('mark');
    await expect(marks.filter({ hasText: 'total liability under this Addendum' })).not.toHaveCount(
      0,
    );
  });

  test('s3 marks the real §3.1 rates behind the wrong-section citation', async ({ page }) => {
    await replay(page, 'Citation check');

    await expect(page.locator('mark').filter({ hasText: 'Zone A: $1,250.00' })).not.toHaveCount(0);
  });
});
