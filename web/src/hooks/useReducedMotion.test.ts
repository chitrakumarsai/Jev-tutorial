import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { REDUCED_MOTION_QUERY, useReducedMotion } from './useReducedMotion';

/** A controllable MediaQueryList for the reduced-motion query. */
function stubMatchMedia(initial: boolean) {
  let matches = initial;
  const listeners = new Set<() => void>();
  const matchMedia = vi.fn((query: string) => ({
    get matches() {
      return query === REDUCED_MOTION_QUERY && matches;
    },
    media: query,
    addEventListener: (_type: 'change', listener: () => void) => listeners.add(listener),
    removeEventListener: (_type: 'change', listener: () => void) => listeners.delete(listener),
  }));
  vi.stubGlobal('matchMedia', matchMedia);
  return {
    listeners,
    set(next: boolean) {
      matches = next;
      for (const listener of listeners) listener();
    },
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('useReducedMotion', () => {
  it.each([true, false])('reports the OS setting (%s)', (reduce) => {
    stubMatchMedia(reduce);

    expect(renderHook(() => useReducedMotion()).result.current).toBe(reduce);
  });

  it('follows a change to the OS setting', () => {
    const media = stubMatchMedia(false);
    const { result } = renderHook(() => useReducedMotion());

    act(() => {
      media.set(true);
    });

    expect(result.current).toBe(true);
  });

  it('stops listening on unmount', () => {
    const media = stubMatchMedia(false);
    const { unmount } = renderHook(() => useReducedMotion());
    expect(media.listeners.size).toBe(1);

    unmount();

    expect(media.listeners.size).toBe(0);
  });

  it('assumes full motion where matchMedia is missing', () => {
    vi.stubGlobal('matchMedia', undefined);

    expect(renderHook(() => useReducedMotion()).result.current).toBe(false);
  });
});
