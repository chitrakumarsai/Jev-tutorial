import { useId } from 'react';

import { THEME_PREFERENCES, type ThemePreference, useTheme } from '../../hooks/useTheme';
import './theme-toggle.css';

const LABELS: Record<ThemePreference, string> = {
  system: 'System',
  light: 'Light',
  dark: 'Dark',
};

/** Native radios give arrow-key movement and form semantics for free. */
export function ThemeToggle() {
  const { preference, setPreference } = useTheme();
  const name = useId();
  const labelId = `${name}-label`;

  return (
    <div className="theme-toggle" role="radiogroup" aria-labelledby={labelId}>
      <span id={labelId} className="visually-hidden">
        Theme
      </span>
      {THEME_PREFERENCES.map((option) => (
        <label key={option} className="theme-toggle__option">
          <input
            type="radio"
            name={name}
            value={option}
            checked={preference === option}
            onChange={() => {
              setPreference(option);
            }}
          />
          <span>{LABELS[option]}</span>
        </label>
      ))}
    </div>
  );
}
