import { expect, type Page } from '@playwright/test';

export type Theme = 'light' | 'dark';

export const THEMES: readonly Theme[] = ['light', 'dark'];

/** Starting a run, with or without a trailing slash or query string. */
const RUNS_URL = /\/api\/runs\/?(\?.*)?$/;

/** Generous: a replay's events land in well under a second once pacing is off. */
const RUN_TIMEOUT_MS = 20_000;

/**
 * The UI asks for a paced replay (the recorded latency, ~30 s with the LLM call). E2E keeps
 * every event but drops the waiting, so the journey is fast and deterministic.
 */
export async function skipReplayPacing(page: Page): Promise<void> {
  await page.route(RUNS_URL, async (route) => {
    const request = route.request();
    if (request.method() !== 'POST') {
      await route.continue();
      return;
    }
    const body: unknown = request.postDataJSON();
    if (typeof body !== 'object' || body === null) {
      throw new Error(`Expected a JSON run request, got ${String(request.postData())}`);
    }
    await route.continue({ postData: JSON.stringify({ ...body, pace: false }) });
  });
}

/** Opens the app and waits for the first scenario to load. Set the OS theme with `test.use`. */
export async function openApp(page: Page): Promise<void> {
  await skipReplayPacing(page);
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1, name: 'Jev Audit Lens' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Replay recorded run' })).toBeEnabled();
}

/** Starts a replay and waits until both sides have finished and the results are shown. */
export async function replayToResults(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'Replay recorded run' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Replay complete' })).toBeVisible({
    timeout: RUN_TIMEOUT_MS,
  });
  await expect(page.getByRole('heading', { level: 2, name: 'Results' })).toBeVisible();
}

/**
 * Waits until every finite animation has finished. Reduced motion still fades things in, and
 * a half-faded element would fail a contrast check or a screenshot it passes once settled.
 */
export async function settle(page: Page): Promise<void> {
  await page.waitForFunction(() =>
    document
      .getAnimations()
      .every(
        (animation) =>
          animation.playState !== 'running' ||
          animation.effect?.getComputedTiming().iterations === Infinity,
      ),
  );
}
