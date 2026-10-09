/**
 * Reveals text a few characters per frame. Purely presentational: the full text is already
 * known, so callers must say so on screen (the LLM response is not streamed). With reduced
 * motion the whole text shows at once. Text that grows keeps what is already typed; text
 * that changes otherwise starts again.
 */
import { useEffect, useState } from 'react';

import { useReducedMotion } from './useReducedMotion';

export const CHARS_PER_SECOND = 900;
const MS_PER_SECOND = 1000;

interface Typed {
  readonly basis: string;
  readonly count: number;
}

/** How much of `text` is already typed, given what was typed of the previous text. */
function kept(previous: Typed, text: string): number {
  return text.startsWith(previous.basis.slice(0, previous.count)) ? previous.count : 0;
}

export function useTypewriter(
  text: string,
  charsPerSecond = CHARS_PER_SECOND,
): { text: string; done: boolean } {
  const isReduced = useReducedMotion();
  const [typed, setTyped] = useState<Typed>({ basis: text, count: 0 });
  const count = kept(typed, text);
  const done = isReduced || count >= text.length;

  useEffect(() => {
    if (done) return;
    let frame = 0;
    let last: number | null = null;
    const tick = (now: number) => {
      const step =
        last === null
          ? 1
          : Math.max(1, Math.round(((now - last) * charsPerSecond) / MS_PER_SECOND));
      last = now;
      setTyped((previous) => ({
        basis: text,
        count: Math.min(text.length, kept(previous, text) + step),
      }));
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(frame);
    };
  }, [text, charsPerSecond, done]);

  return { text: isReduced ? text : text.slice(0, count), done };
}
