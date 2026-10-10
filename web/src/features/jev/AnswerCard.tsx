import { motion } from 'motion/react';
import { useId } from 'react';

import { ConfidenceRing } from '../../components/confidence-ring/ConfidenceRing';
import { formatCount, formatDuration, formatPercent } from '../../lib/format';
import { motionTokens, springs } from '../../lib/motion';
import type { JevRequest } from './jevProgress';

type Props = {
  request: JevRequest;
};

/** One Jev request's typed answers, each with the probability Jev gave it. */
export function AnswerCard({ request }: Props) {
  const headingId = useId();
  const lowest = Math.min(...request.answers.map((a) => a.confidence));
  return (
    <motion.section
      className="answer-card"
      aria-labelledby={headingId}
      initial={{ opacity: 0, y: -motionTokens.distance.md, scale: motionTokens.scale.subtle }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={springs.snappy}
    >
      <div className="answer-card__header">
        <h3 id={headingId} className="answer-card__title">
          {request.label.full}
          <span className="answer-card__meta">
            {formatCount(request.answers.length)} typed answers
            {request.latencyMs !== null && ` in ${formatDuration(request.latencyMs)}`}
          </span>
        </h3>
        {request.answers.length > 0 && <ConfidenceRing value={lowest} label="Lowest confidence" />}
      </div>
      {/* It scrolls when there are many answers, so the keyboard must be able to reach it. */}
      <div
        className="answer-card__scroll"
        role="group"
        aria-label={`Typed answers, ${request.label.full}`}
        tabIndex={0}
      >
        <dl className="answer-card__answers">
          {request.answers.map((answer) => (
            <div key={answer.key} className="answer">
              <dt className="answer__question">{answer.question}</dt>
              <dd className="answer__value">
                <code>{answer.answer}</code>
              </dd>
              <dd className="answer__probability">
                <span className="answer__bar" aria-hidden="true">
                  <motion.span
                    className="answer__fill"
                    initial={{ scaleX: 0 }}
                    animate={{ scaleX: answer.probability }}
                    transition={{
                      duration: motionTokens.duration.normal,
                      ease: motionTokens.easing.smooth,
                    }}
                  />
                </span>
                <span className="answer__figure">
                  <span className="visually-hidden">
                    {answer.kind === 'yes_no' ? 'Probability of yes' : 'Probability'}{' '}
                  </span>
                  {formatPercent(answer.probability)}
                </span>
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </motion.section>
  );
}
