import { useCallback, useLayoutEffect, useState } from 'react';

/** "system" follows prefers-color-scheme; light/dark pin it via :root[data-theme]. */
export type ThemePreference = 'system' | 'light' | 'dark';

export const THEME_PREFERENCES: readonly ThemePreference[] = ['system', 'light', 'dark'];
export const THEME_STORAGE_KEY = 'jev-audit-lens:theme';

function isThemePreference(value: unknown): value is ThemePreference {
  return THEME_PREFERENCES.includes(value as ThemePreference);
}

/** Storage can be blocked (private mode, policies); the OS theme is always a safe answer. */
export function readStoredPreference(): ThemePreference {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    return isThemePreference(stored) ? stored : 'system';
  } catch {
    return 'system';
  }
}

function storePreference(preference: ThemePreference): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, preference);
  } catch {
    // Only a convenience: the theme still applies for this visit.
  }
}

export interface ThemeControl {
  preference: ThemePreference;
  setPreference: (preference: ThemePreference) => void;
}

export function useTheme(): ThemeControl {
  const [preference, setPreferenceState] = useState(readStoredPreference);

  // index.html pins a saved theme before first paint; this keeps it in sync afterwards.
  useLayoutEffect(() => {
    const root = document.documentElement;
    if (preference === 'system') {
      delete root.dataset.theme;
    } else {
      root.dataset.theme = preference;
    }
  }, [preference]);

  const setPreference = useCallback((next: ThemePreference) => {
    setPreferenceState(next);
    storePreference(next);
  }, []);

  return { preference, setPreference };
}
