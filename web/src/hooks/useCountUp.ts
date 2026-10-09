/**
 * Counts a money figure up from zero for display. The in-between frames are approximate
 * (a float tween); the last frame is always the exact Decimal string, formatted, so the
 * figure that stays on screen is the backend's. With reduced motion it shows at once.
 */
import { animate } from 'motion/react';
import { useEffect, useState } from 'react';

import { formatMoney } from '../lib/format';
import { motionTokens } from '../lib/motion';
import { useReducedMotion } from './useReducedMotion';

const CENTS = 2;

interface Tween {
  readonly target: string;
  readonly frame: number | null; // null: finished, show the exact target
}

export function useCountUp(value: string): string {
  const isReduced = useReducedMotion();
  const [tween, setTween] = useState<Tween>({ target: value, frame: 0 });
  const target = Number(value);
  const canTween = !isReduced && Number.isFinite(target);

  useEffect(() => {
    if (!canTween) return;
    const controls = animate(0, target, {
      duration: motionTokens.duration.crawl,
      ease: motionTokens.easing.smooth,
      onUpdate: (frame) => {
        setTween({ target: value, frame });
      },
      onComplete: () => {
        setTween({ target: value, frame: null });
      },
    });
    return () => {
      controls.stop();
    };
  }, [value, target, canTween]);

  const isCurrent = tween.target === value;
  if (!canTween || (isCurrent && tween.frame === null)) return formatMoney(value);
  // A new value starts from zero until its first frame lands.
  return formatMoney((isCurrent ? (tween.frame ?? 0) : 0).toFixed(CENTS));
}
