/** WCAG 2.2 contrast maths, used to keep the design tokens legible in both themes. */

export type Rgb = readonly [number, number, number];

const HEX_PATTERN = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i;

export function parseHex(hex: string): Rgb {
  const match = HEX_PATTERN.exec(hex);
  if (!match) {
    throw new Error(`Expected a six-digit hex colour like #1b2333, got ${JSON.stringify(hex)}`);
  }
  const [, r = '', g = '', b = ''] = match;
  return [parseInt(r, 16), parseInt(g, 16), parseInt(b, 16)];
}

function linearChannel(channel: number): number {
  const srgb = channel / 255;
  return srgb <= 0.04045 ? srgb / 12.92 : ((srgb + 0.055) / 1.055) ** 2.4;
}

function relativeLuminance(hex: string): number {
  const [r, g, b] = parseHex(hex);
  return 0.2126 * linearChannel(r) + 0.7152 * linearChannel(g) + 0.0722 * linearChannel(b);
}

export function contrastRatio(a: string, b: string): number {
  const [lighter, darker] = [relativeLuminance(a), relativeLuminance(b)].sort((x, y) => y - x);
  return ((lighter ?? 0) + 0.05) / ((darker ?? 0) + 0.05);
}
