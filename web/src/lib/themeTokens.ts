/** Reads `--token: light-dark(#light, #dark)` declarations so tests can check both themes. */

export interface ThemePair {
  readonly light: string;
  readonly dark: string;
}

const LIGHT_DARK_DECLARATION =
  /(--[\w-]+)\s*:\s*light-dark\(\s*(#[0-9a-f]{6})\s*,\s*(#[0-9a-f]{6})\s*\)/gi;

const COLOUR_DECLARATION = /(--color-[\w-]+)\s*:\s*([^;]*);/g;

/** A colour token the contrast tests can't read would silently escape them, so refuse it. */
function assertColoursCheckable(css: string): void {
  for (const [declaration, name = ''] of css.matchAll(COLOUR_DECLARATION)) {
    if (!new RegExp(LIGHT_DARK_DECLARATION.source, 'i').test(declaration)) {
      throw new Error(`${name} must be light-dark(#rrggbb, #rrggbb) so both themes are checked`);
    }
  }
}

export function readThemePairs(css: string): ReadonlyMap<string, ThemePair> {
  assertColoursCheckable(css);
  const entries = [...css.matchAll(LIGHT_DARK_DECLARATION)].map(
    ([, name = '', light = '', dark = '']) =>
      [name, { light: light.toLowerCase(), dark: dark.toLowerCase() }] as const,
  );
  const pairs = new Map(entries);
  if (pairs.size !== entries.length) {
    const seen = new Set<string>();
    const duplicate = entries.find(([name]) => seen.has(name) || !seen.add(name));
    throw new Error(`${duplicate?.[0] ?? 'A token'} is defined more than once`);
  }
  return pairs;
}
