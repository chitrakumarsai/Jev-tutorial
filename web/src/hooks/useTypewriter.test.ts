import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useTypewriter } from './useTypewriter';

function stubReducedMotion(matches: boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({ matches, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
  );
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['requestAnimationFrame', 'cancelAnimationFrame', 'performance'] });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('useTypewriter', () => {
  it('reveals the text a few characters per frame, then reports done', () => {
    const { result } = renderHook(() => useTypewriter('abcdefghij', 120));

    expect(result.current).toEqual({ text: '', done: false });
    act(() => {
      vi.advanceTimersByTime(16 * 3);
    });
    expect(result.current.text.length).toBeGreaterThan(0);
    expect(result.current.text.length).toBeLessThan(10);
    expect('abcdefghij'.startsWith(result.current.text)).toBe(true);

    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(result.current).toEqual({ text: 'abcdefghij', done: true });
  });

  it('keeps what is typed when the text grows, and restarts when it changes', () => {
    const { result, rerender } = renderHook(({ text }) => useTypewriter(text, 10_000), {
      initialProps: { text: 'first line' },
    });
    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(result.current.text).toBe('first line');

    rerender({ text: 'first line\nsecond' });
    expect(result.current.text).toBe('first line');

    rerender({ text: 'other' });
    expect(result.current.text).toBe('');
  });

  it('shows everything at once when reduced motion is asked for', () => {
    stubReducedMotion(true);

    const { result } = renderHook(() => useTypewriter('all of it'));

    expect(result.current).toEqual({ text: 'all of it', done: true });
  });
});
