import { expect, type Page, test } from '@playwright/test';

import { openApp, replayToResults, settle, THEMES } from './support';

const WIDTHS = [320, 768, 1024, 1440] as const;
const HEIGHT = 900;
/** Two wrapped rows of tabs; stretched beside the results column they measured ~630px. */
const MAX_TABLIST_HEIGHT_PX = 120;
/** A tab is one line of text plus padding (28px minimum). */
const MAX_TAB_HEIGHT_PX = 48;

/** Wall-clock figures differ every run, so they are masked out of the comparison. */
function volatile(page: Page) {
  return [page.getByRole('row', { name: /Time in this run/ })];
}

async function hasHorizontalOverflow(page: Page): Promise<boolean> {
  return page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
}

for (const theme of THEMES) {
  // Settled frames only: screenshots of a moving UI never match.
  test.describe(`${theme} theme`, () => {
    test.use({ colorScheme: theme, contextOptions: { reducedMotion: 'reduce' } });
    for (const width of WIDTHS) {
      test(`${theme} at ${String(width)}px: idle and with results`, async ({ page }) => {
        await page.setViewportSize({ width, height: HEIGHT });
        await openApp(page);

        expect(await hasHorizontalOverflow(page)).toBe(false);
        await settle(page);
        await expect(page).toHaveScreenshot(`idle-${theme}-${String(width)}.png`, {
          fullPage: true,
        });

        await replayToResults(page);

        expect(await hasHorizontalOverflow(page)).toBe(false);
        await settle(page);
        await expect(page).toHaveScreenshot(`results-${theme}-${String(width)}.png`, {
          fullPage: true,
          mask: volatile(page),
        });
      });
    }
  });
}

test.describe('three-column layout', () => {
  test.use({
    viewport: { width: 1440, height: HEIGHT },
    contextOptions: { reducedMotion: 'reduce' },
  });

  test('keeps the source tabs and legend compact beside a long results column', async ({
    page,
  }) => {
    await openApp(page);
    await replayToResults(page);

    const tabs = await page.getByRole('tablist', { name: 'Documents' }).boundingBox();
    const tab = await page.getByRole('tab').first().boundingBox();
    expect(tabs?.height).toBeLessThan(MAX_TABLIST_HEIGHT_PX);
    expect(tab?.height).toBeLessThan(MAX_TAB_HEIGHT_PX);
  });
});

// Full-page shots tolerate 1% change, which a moved Results row stays under; a shot of the
// scorecard table alone makes any changed row or value a large share of the image.
const SCENARIOS = [
  ['s1', 'Contract-to-invoice reconciliation'],
  ['s2', 'Clause risk review'],
  ['s3', 'Citation check'],
] as const;

for (const theme of THEMES) {
  test.describe(`${theme} scorecards`, () => {
    test.use({
      viewport: { width: 1440, height: HEIGHT },
      colorScheme: theme,
      contextOptions: { reducedMotion: 'reduce' },
    });
    for (const [id, title] of SCENARIOS) {
      test(`${id} scorecard table in ${theme}`, async ({ page }) => {
        await openApp(page);
        await page.getByLabel('Scenario').selectOption({ label: title });
        await replayToResults(page);
        await settle(page);

        const scorecard = page.getByRole('table', { name: 'Scorecard against the answer key' });
        // Text-only changes (a swapped label) are well under 1% of the table, so the
        // tolerance here is ten times tighter than for full pages.
        await expect(scorecard).toHaveScreenshot(`scorecard-${id}-${theme}.png`, {
          maxDiffPixelRatio: 0.001,
        });
      });
    }
  });
}

test.describe('consistency at phone width', () => {
  test.use({
    viewport: { width: 320, height: HEIGHT },
    contextOptions: { reducedMotion: 'reduce' },
  });

  test('the open Consistency ×3 tables never push the page sideways', async ({ page }) => {
    await openApp(page);
    await page.getByLabel('Scenario').selectOption({ label: 'Citation check' });
    await page.getByRole('button', { name: 'Consistency ×3' }).click();
    await expect(page.getByRole('table', { name: /Plain LLM/ })).toBeVisible();

    expect(await hasHorizontalOverflow(page)).toBe(false);
  });
});
