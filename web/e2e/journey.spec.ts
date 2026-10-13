import { expect, test } from '@playwright/test';

import { openApp, replayToResults } from './support';

test.describe('replay journey', () => {
  test.beforeEach(async ({ page }) => {
    await openApp(page);
  });

  test('shows the scenario, its sources and which recording a replay uses', async ({ page }) => {
    await expect(page.getByRole('heading', { level: 2, name: 'Source documents' })).toBeVisible();
    await expect(page.getByRole('tablist', { name: 'Documents' })).toBeVisible();
    const runControls = page.getByRole('banner');
    await expect(runControls.getByText('Recorded', { exact: true })).toBeVisible();
    await expect(runControls.locator('time')).toBeVisible();
  });

  test('replays a recorded run through to the results', async ({ page }) => {
    await replayToResults(page);

    const results = page.getByRole('region', { name: 'Results' });
    await expect(results.getByRole('table', { name: /Scorecard/ })).toBeVisible();
    await expect(results.getByRole('table', { name: 'Cost and latency' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Replay recorded run' })).toBeEnabled();
  });

  test('traces a finding back to the passage it quotes', async ({ page }) => {
    await replayToResults(page);

    await page
      .getByRole('button', { name: /, show in / })
      .first()
      .click();

    await expect(
      page.getByRole('status').filter({ hasText: 'Showing the passage in' }),
    ).toBeVisible();
  });

  test('refuses live mode on a server with live calls turned off', async ({ page }) => {
    await page.getByRole('radio', { name: 'Live' }).check();

    await expect(page.getByText('Live calls are turned off on this server.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Run live' })).toBeDisabled();
  });

  test('replays the clause review and shows the missing clause caught', async ({ page }) => {
    await page.getByLabel('Scenario').selectOption({ label: 'Clause risk review' });
    await expect(page.getByRole('heading', { level: 2, name: 'Clause risk review' })).toBeVisible();
    await expect(page.getByRole('tab', { name: /Data processing addendum/ })).toBeVisible();

    await replayToResults(page);

    const scorecard = page.getByRole('table', { name: /Scorecard/ });
    await expect(scorecard.getByRole('row', { name: /Missing clause caught/ })).toContainText(
      'Yes',
    );
    await expect(page.getByText('Not in the agreement').first()).toBeVisible();
  });

  test('replays the citation check and catches every planted error', async ({ page }) => {
    await page.getByLabel('Scenario').selectOption({ label: 'Citation check' });
    await expect(page.getByRole('tab', { name: /Audit memo/ })).toBeVisible();

    await replayToResults(page);

    const scorecard = page.getByRole('table', { name: /Scorecard/ });
    await expect(scorecard.getByRole('row', { name: /Fabricated quote caught/ })).toContainText(
      'Yes',
    );
    await expect(scorecard.getByRole('row', { name: /Planted errors caught/ })).toContainText(
      '3 of 3',
    );
    await expect(page.getByText('Citation C3').first()).toBeVisible();
  });

  test('shows Consistency ×3 for the citation check: Jev steady, the LLM changing on C5', async ({
    page,
  }) => {
    await page.getByLabel('Scenario').selectOption({ label: 'Citation check' });

    await page.getByRole('button', { name: 'Consistency ×3' }).click();

    const jev = page.getByRole('table', { name: /Jev \+ code/ });
    await expect(jev).toHaveAccessibleName(/same answer on all 10 items in 3 runs/);
    const llm = page.getByRole('table', { name: /Plain LLM/ });
    await expect(llm).toHaveAccessibleName(/1 item changed/);
    await expect(llm.getByRole('row', { name: /C5/ })).toContainText('changed');
  });

  test('links a memo citation to its rows on both sides, from the keyboard', async ({ page }) => {
    await page.getByLabel('Scenario').selectOption({ label: 'Citation check' });
    await page.getByRole('tab', { name: /Memo/ }).click();
    const c3 = page.getByRole('button', { name: 'Show citation C3 in the ledgers' });

    await c3.focus();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('status').filter({ hasText: 'Citation C3' })).toHaveText(
      /no ledger rows yet/,
    );

    await replayToResults(page);
    await c3.focus();
    await page.keyboard.press('Enter');

    const current = page.locator('li[aria-current="true"]');
    await expect(current).toHaveCount(2);
    await expect(current.first()).toContainText('Citation C3');
    await expect(current.first()).toBeInViewport();
    await expect(current.last()).toBeInViewport();
    await expect(page.getByRole('status').filter({ hasText: 'Citation C3' })).toHaveText(
      /2 ledger rows marked/,
    );
  });
});
