import { motion } from 'motion/react';

import { formatPercent } from '../../lib/format';
import { motionTokens } from '../../lib/motion';
import './confidence-ring.css';

type Props = {
  /** A calibrated confidence in [0, 1]. */
  value: number;
  /** What the confidence is of, for the accessible name ("Lowest confidence"). */
  label?: string;
  tone?: 'jev' | 'review';
};

const RADIUS = 15.9155; // circumference 100, so a stroke length reads as a percentage

/** A ring that fills to the confidence, with the figure beside it. */
export function ConfidenceRing({ value, label = 'Confidence', tone = 'jev' }: Props) {
  const clamped = Math.min(1, Math.max(0, value));
  return (
    <span className={`confidence-ring confidence-ring--${tone}`}>
      <svg viewBox="0 0 36 36" aria-hidden="true" className="confidence-ring__svg">
        <circle className="confidence-ring__track" cx="18" cy="18" r={RADIUS} />
        <motion.circle
          className="confidence-ring__fill"
          cx="18"
          cy="18"
          r={RADIUS}
          initial={{ pathLength: 0 }}
          animate={{ pathLength: clamped }}
          transition={{ duration: motionTokens.duration.slow, ease: motionTokens.easing.smooth }}
        />
      </svg>
      <span className="confidence-ring__figure">
        <span className="visually-hidden">{label} </span>
        {formatPercent(clamped)}
      </span>
    </span>
  );
}
