import { afterEach, describe, expect, it } from 'vitest';

import html from '../../index.html?raw';
import { THEME_STORAGE_KEY } from '../hooks/useTheme';

// The pre-paint script must run before CSS paints, so it lives inline in index.html.
const script = /<script>([\s\S]*?)<\/script>/.exec(html)?.[1] ?? '';

function runPrePaintScript(): void {
  // Executes our own checked-in index.html script, the same code the browser runs.
  // eslint-disable-next-line @typescript-eslint/no-implied-eval
  const prePaint = new Function(script) as () => void;
  prePaint();
}

afterEach(() => {
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});

describe('index.html pre-paint theme script', () => {
  it('sits in the head, before any stylesheet or module script', () => {
    const head = /<head>([\s\S]*?)<\/head>/.exec(html)?.[1] ?? '';
    expect(head).toContain(script);
    expect(script).toContain(THEME_STORAGE_KEY);
  });

  it.each(['light', 'dark'])('pins a stored %s theme', (theme) => {
    localStorage.setItem(THEME_STORAGE_KEY, theme);

    runPrePaintScript();

    expect(document.documentElement.dataset.theme).toBe(theme);
  });

  it.each(['system', 'sepia', null])('leaves the OS in charge for %j', (stored) => {
    if (stored !== null) localStorage.setItem(THEME_STORAGE_KEY, stored);

    runPrePaintScript();

    expect(document.documentElement.dataset.theme).toBeUndefined();
  });
});
