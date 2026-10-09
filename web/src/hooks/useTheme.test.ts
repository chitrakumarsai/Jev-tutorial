import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { THEME_STORAGE_KEY, readStoredPreference, useTheme } from './useTheme';

const root = document.documentElement;

afterEach(() => {
  localStorage.clear();
  delete root.dataset.theme;
  vi.restoreAllMocks();
});

describe('readStoredPreference', () => {
  it('defaults to following the OS', () => {
    expect(readStoredPreference()).toBe('system');
  });

  it.each(['light', 'dark', 'system'] as const)('returns a stored %s', (value) => {
    localStorage.setItem(THEME_STORAGE_KEY, value);

    expect(readStoredPreference()).toBe(value);
  });

  it('ignores an unknown stored value', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'sepia');

    expect(readStoredPreference()).toBe('system');
  });

  it('falls back to the OS when storage is unavailable', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('blocked', 'SecurityError');
    });

    expect(readStoredPreference()).toBe('system');
  });
});

describe('useTheme', () => {
  it('leaves the theme to the OS by default', () => {
    const { result } = renderHook(() => useTheme());

    expect(result.current.preference).toBe('system');
    expect(root.dataset.theme).toBeUndefined();
  });

  it('pins the chosen theme on the root element and remembers it', () => {
    const { result } = renderHook(() => useTheme());

    act(() => {
      result.current.setPreference('dark');
    });

    expect(root.dataset.theme).toBe('dark');
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');
  });

  it('returns to the OS theme when system is chosen again', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'light');
    const { result } = renderHook(() => useTheme());
    expect(root.dataset.theme).toBe('light');

    act(() => {
      result.current.setPreference('system');
    });

    expect(root.dataset.theme).toBeUndefined();
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('system');
  });

  it('still switches theme when storage refuses writes', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('full', 'QuotaExceededError');
    });
    const { result } = renderHook(() => useTheme());

    act(() => {
      result.current.setPreference('light');
    });

    expect(result.current.preference).toBe('light');
    expect(root.dataset.theme).toBe('light');
  });
});
