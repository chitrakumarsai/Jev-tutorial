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
});
