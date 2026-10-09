import { THEME_PREFERENCES, type ThemePreference, useTheme } from '../../hooks/useTheme';
import { Segmented } from '../segmented/Segmented';

const LABELS: Record<ThemePreference, string> = {
  system: 'System',
  light: 'Light',
  dark: 'Dark',
};

export function ThemeToggle() {
  const { preference, setPreference } = useTheme();
  return (
    <Segmented
      label="Theme"
      options={THEME_PREFERENCES}
      labels={LABELS}
      value={preference}
      onChange={setPreference}
    />
  );
}
