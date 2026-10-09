/**
 * Whether the OS asks for reduced motion, kept live. Motion components read this to
 * swap transforms for short opacity fades (see lib/motion.ts); CSS has its own fallback.
 */
import { useSyncExternalStore } from 'react';

export const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)';

function query(): MediaQueryList | null {
  // matchMedia is missing in some test and embedded environments.
  return typeof window.matchMedia === 'function' ? window.matchMedia(REDUCED_MOTION_QUERY) : null;
}

function subscribe(onChange: () => void): () => void {
  const media = query();
  media?.addEventListener('change', onChange);
  return () => media?.removeEventListener('change', onChange);
}

function prefersReducedMotion(): boolean {
  return query()?.matches ?? false;
}

export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, prefersReducedMotion, () => false);
}
