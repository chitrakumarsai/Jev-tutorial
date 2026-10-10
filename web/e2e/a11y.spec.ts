import AxeBuilder from '@axe-core/playwright';
import { expect, type Page, test } from '@playwright/test';

import { openApp, replayToResults, settle, THEMES } from './support';

const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

/** axe violations as "rule: target" lines, so a failure names what to fix. */
async function violations(page: Page): Promise<string[]> {
  await settle(page);
  const { violations: found } = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  return found.flatMap((v) => v.nodes.map((node) => `${v.id}: ${node.target.join(' ')}`));
}

for (const theme of THEMES) {
  test.describe(`${theme} theme`, () => {
    // Settled frames only: axe measures contrast, and a mid-fade element reads as too faint.
    test.use({ colorScheme: theme, contextOptions: { reducedMotion: 'reduce' } });

    test('has no WCAG A/AA violations before a run', async ({ page }) => {
      await openApp(page);

      expect(await violations(page)).toEqual([]);
    });

    test('has no WCAG A/AA violations once the results are in', async ({ page }) => {
      await openApp(page);
      await replayToResults(page);

      expect(await violations(page)).toEqual([]);
    });
  });
}

/** Enough presses to cross the masthead's controls; more means the button is out of reach. */
const MAX_TAB_PRESSES = 20;

test('starts a replay from the keyboard alone', async ({ page, browserName }) => {
  // Safari on macOS skips buttons on Tab; Option+Tab is how its keyboard users reach them.
  // WebKit elsewhere (Linux CI) tabs to buttons as other browsers do.
  const nextControl = browserName === 'webkit' && process.platform === 'darwin' ? 'Alt+Tab' : 'Tab';
  await openApp(page);
  const runButton = page.getByRole('button', { name: 'Replay recorded run' });
  const isFocused = () => runButton.evaluate((button) => button === document.activeElement);

  for (let presses = 0; presses < MAX_TAB_PRESSES && !(await isFocused()); presses++) {
    await page.keyboard.press(nextControl);
  }
  await expect(runButton).toBeFocused();
  await page.keyboard.press('Enter');

  await expect(page.getByRole('heading', { level: 2, name: 'Results' })).toBeVisible({
    timeout: 20_000,
  });
});
