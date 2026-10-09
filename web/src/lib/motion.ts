/**
 * Shared motion values for motion/react. Components take durations, easings and springs
 * from here, never inline. Animate transform and opacity only; with reduced motion,
 * fall back to opacity fades of at most `duration.reduced`.
 */

type CubicBezier = readonly [number, number, number, number];

export const motionTokens = {
  duration: {
    instant: 0.08,
    fast: 0.18,
    normal: 0.35,
    slow: 0.6,
    crawl: 1.0,
    reduced: 0.2,
  },
  easing: {
    smooth: [0.22, 1, 0.36, 1] as CubicBezier,
    sharp: [0.4, 0, 0.2, 1] as CubicBezier,
    linear: [0, 0, 1, 1] as CubicBezier,
  },
  distance: { xs: 4, sm: 8, md: 16, lg: 24, xl: 48 },
  scale: { subtle: 0.98, press: 0.95, pop: 1.04 },
} as const;

export const springs = {
  snappy: { type: 'spring', stiffness: 300, damping: 30 },
  gentle: { type: 'spring', stiffness: 120, damping: 14 },
  instant: { type: 'spring', stiffness: 600, damping: 35 },
} as const;
