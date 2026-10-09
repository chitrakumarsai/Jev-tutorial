import { motion } from 'motion/react';
import { useEffect, useEffectEvent, useState } from 'react';

import { useReducedMotion } from '../../hooks/useReducedMotion';
import { motionTokens } from '../../lib/motion';
import { findMark } from './findMark';
import { tracePath, type TracePath } from './traceGeometry';
import './trace.css';

type Props = {
  /** The figure that was pressed. */
  from: HTMLElement;
  highlightId: string;
  onDone: () => void;
};

/** Scrolling counts as settled once no scroll event has arrived for this long. */
const SCROLL_QUIET_MS = 120;
/** Draw anyway after this long, even if something keeps scrolling. */
const MAX_WAIT_MS = 1500;
/** How long the line stays once drawn. */
const LINGER_MS = 2200;
const END_RADIUS = 3.5;

/**
 * Draws a line from a figure to its passage once the viewer's scroll to it has settled,
 * then fades. A scroll or resize after drawing would leave the line pointing at the wrong
 * place, so it ends the line instead.
 */
export function TraceLine({ from, highlightId, onDone }: Props) {
  const isReduced = useReducedMotion();
  const [path, setPath] = useState<TracePath | null>(null);
  const finish = useEffectEvent(onDone);

  useEffect(() => {
    let isDrawn = false;
    let quiet = 0;
    let linger = 0;
    let cap = 0;
    const draw = () => {
      if (isDrawn) return;
      window.clearTimeout(quiet);
      window.clearTimeout(cap);
      const mark = findMark(document, highlightId);
      const next = mark
        ? tracePath(
            from.getBoundingClientRect(),
            mark.getBoundingClientRect(),
            window.innerWidth,
            window.innerHeight,
          )
        : null;
      if (!next) {
        finish();
        return;
      }
      isDrawn = true;
      setPath(next);
      linger = window.setTimeout(finish, LINGER_MS);
    };
    const waitForQuiet = () => {
      window.clearTimeout(quiet);
      quiet = window.setTimeout(draw, SCROLL_QUIET_MS);
    };
    const handleMove = () => {
      if (isDrawn) finish();
      else waitForQuiet(); // still the viewer's own scroll to the passage
    };
    cap = window.setTimeout(draw, MAX_WAIT_MS);
    waitForQuiet();
    window.addEventListener('scroll', handleMove, { capture: true, passive: true });
    window.addEventListener('resize', handleMove);
    return () => {
      window.clearTimeout(quiet);
      window.clearTimeout(cap);
      window.clearTimeout(linger);
      window.removeEventListener('scroll', handleMove, { capture: true });
      window.removeEventListener('resize', handleMove);
    };
  }, [from, highlightId]);

  if (!path) return null;
  return (
    <svg className="trace-line" aria-hidden="true">
      <motion.path
        className="trace-line__path"
        d={path.d}
        initial={{ pathLength: isReduced ? 1 : 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: motionTokens.duration.slow, ease: motionTokens.easing.smooth }}
      />
      <circle className="trace-line__end" cx={path.end.x} cy={path.end.y} r={END_RADIUS} />
    </svg>
  );
}
