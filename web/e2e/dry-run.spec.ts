import { expect, type Locator, type Page, test } from '@playwright/test';

import { openApp, replayToResults, settle } from './support';

/**
 * P7-7 dry run of docs/RUN-OF-SHOW.md in Replay: each step checks what the talk track says
 * and saves a screenshot for the doc. Run on demand only, never as part of the suite:
 *   DRY_RUN=1 npm --prefix web run e2e -- --project=chromium dry-run
 */
test.skip(!process.env.DRY_RUN, 'dry run of the run of show; set DRY_RUN=1');
test.use({
  viewport: { width: 1440, height: 900 },
  colorScheme: 'light',
  contextOptions: { reducedMotion: 'reduce' },
});

const OUT = '../docs/run-of-show';

async function shot(target: Page | Locator, name: string): Promise<void> {
  const page = 'page' in target ? target.page() : target;
  await settle(page);
  await target.screenshot({ path: `${OUT}/${name}.jpg`, type: 'jpeg', quality: 80 });
}

function results(page: Page): Locator {
  return page.locator('section', {
    has: page.getByRole('heading', { level: 2, name: 'Results' }),
  });
}

test('S1 contract-to-invoice reconciliation', async ({ page }) => {
  await openApp(page);
  await shot(page, '01-s1-ready');

  await replayToResults(page);
  const jev = page.getByRole('region', { name: 'Jev + code' });
  await jev.getByRole('button', { name: /^Master services agreement/ }).click();
  await shot(
    page.getByRole('region', { name: /^Master services agreement/ }),
    '02-s1-jev-typed-answers',
  );

  // The default replay is the newest recording: the LLM's total is off by $680 there.
  await expect(results(page)).toContainText('$98,510.71, exact');
  await expect(results(page)).toContainText('$99,190.71');
  await shot(results(page), '03-s1-results');

  await jev
    .getByRole('button', { name: /, show in / })
    .first()
    .click();
  await expect(
    page.getByRole('status').filter({ hasText: 'Showing the passage in' }),
  ).toBeVisible();
  await shot(page, '04-s1-trace');
});

test('S2 clause risk review', async ({ page }) => {
  await openApp(page);
  await page.getByLabel('Scenario').selectOption({ label: 'Clause risk review' });
  await replayToResults(page);

  const lane = page.getByText('Review lane', { exact: true }).locator('..');
  await expect(lane).toContainText('Audit rights');
  await expect(lane).toContainText('Insurance');
  await shot(lane, '05-s2-review-lane');
  await expect(results(page)).toContainText('Missing clause caught');
  await shot(results(page), '06-s2-results');
});

test('S3 citation check with Consistency ×3', async ({ page }) => {
  await openApp(page);
  await page.getByLabel('Scenario').selectOption({ label: 'Citation check' });
  await replayToResults(page);
  await shot(results(page), '07-s3-results');

  await page.getByRole('tab', { name: /Memo/ }).click();
  await page.getByRole('button', { name: 'C5, show in the ledgers' }).click();
  await expect(page.locator('li[aria-current="true"]')).toHaveCount(2);
  await shot(page, '08-s3-memo-c5');

  await page.getByRole('button', { name: 'Consistency ×3' }).click();
  const llm = page.getByRole('table', { name: /Plain LLM/ });
  await expect(llm).toHaveAccessibleName(/1 item changed across 3 runs/);
  await expect(page.getByRole('table', { name: /Jev \+ code/ })).toHaveAccessibleName(
    /same answer on all 10 items in 3 runs/,
  );
  await llm.scrollIntoViewIfNeeded();
  await shot(page.locator('.consistency'), '09-s3-consistency');
});

test('Fallback: live refused on a server with live calls off', async ({ page }) => {
  await openApp(page);
  await page.getByRole('radio', { name: 'Live' }).check();
  await expect(page.getByText('Live calls are turned off on this server.')).toBeVisible();
  await shot(page.locator('header'), '10-live-refused');
});
