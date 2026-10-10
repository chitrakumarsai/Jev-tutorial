import { expect, type Page, test } from '@playwright/test';

import { openApp, replayToResults } from './support';

interface MotionLog {
  /** Whether the typewriter caret was ever added. */
  readonly sawCaret: boolean;
  /** Elements whose inline transform passed through in-between values (JS-driven movement). */
  readonly movedElements: number;
}

/**
 * Distinct inline transforms that make an animation rather than a snap. A snap shows up to
 * three (the initial offset, Motion's one-frame layout correction for `layoutId`, then none);
 * a spring or tween passes through dozens.
 */
const ANIMATED_STEPS = 5;

/**
 * Records, from before the first paint, what motion actually happened. Motion drives transforms
 * from JS through inline styles, which document.getAnimations() never sees, so this watches the
 * DOM instead of sampling it, and can't miss a frame.
 */
async function recordMotion(page: Page): Promise<void> {
  await page.addInitScript((steps) => {
    const transforms = new Map<Element, Set<string>>();
    const log = { sawCaret: false, movedElements: 0 };
    Object.assign(window, { __motionLog: log });
    new MutationObserver((records) => {
      for (const record of records) {
        if (record.type === 'childList') {
          for (const node of record.addedNodes) {
            if (
              node instanceof Element &&
              (node.matches('.llm-response__caret') || node.querySelector('.llm-response__caret'))
            ) {
              log.sawCaret = true;
            }
          }
        } else if (record.target instanceof HTMLElement && record.target.style.transform) {
          const seen = transforms.get(record.target) ?? new Set<string>();
          seen.add(record.target.style.transform);
          transforms.set(record.target, seen);
          if (seen.size === steps) log.movedElements += 1;
        }
      }
    }).observe(document, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ['style'],
    });
  }, ANIMATED_STEPS);
}

async function replayAndReadLog(page: Page): Promise<MotionLog> {
  await recordMotion(page);
  await openApp(page);
  await replayToResults(page);
  return page.evaluate(() => (window as unknown as { __motionLog: MotionLog }).__motionLog);
}

test.describe('with reduced motion', () => {
  test.use({ contextOptions: { reducedMotion: 'reduce' } });

  test('shows the parsed LLM result at once and moves nothing', async ({ page }) => {
    const log = await replayAndReadLog(page);

    expect(log.sawCaret).toBe(false);
    expect(log.movedElements).toBe(0);
  });

  test('keeps CSS transitions instant', async ({ page }) => {
    await openApp(page);

    const runButton = page.getByRole('button', { name: 'Replay recorded run' });
    await expect(runButton).toHaveCSS('transition-duration', /^(1e-05s|0\.00001s)(, .*)?$/);
  });
});

test.describe('with full motion', () => {
  test.use({ contextOptions: { reducedMotion: 'no-preference' } });

  // The control: the same recorder does see typing and movement when motion is allowed.
  test('types the parsed LLM result out and animates', async ({ page }) => {
    const log = await replayAndReadLog(page);

    expect(log.sawCaret).toBe(true);
    expect(log.movedElements).toBeGreaterThan(0);
  });
});
