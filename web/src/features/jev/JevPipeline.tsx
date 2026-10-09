import { motion } from 'motion/react';
import { useState } from 'react';

import { formatCount } from '../../lib/format';
import { motionTokens, springs } from '../../lib/motion';
import type { SideProgress } from '../run/runReducer';
import { AnswerCard } from './AnswerCard';
import {
  isAnswered,
  jevPipeline,
  type JevPipeline as Pipeline,
  type StageState,
} from './jevProgress';
import './jev.css';

type Props = {
  progress: SideProgress | null;
};

const STATE_WORDS: Record<StageState, string> = {
  pending: 'Not started',
  active: 'In progress',
  done: 'Done',
};
const FAN_STAGGER_S = 0.035;

function stageDetail(pipeline: Pipeline): Record<keyof Pipeline['stages'], string> {
  const answered = pipeline.requests.filter(isAnswered).length;
  const planned = pipeline.planned;
  return {
    candidates: planned
      ? `${formatCount(planned.questions)} typed questions in ${formatCount(planned.requests)} requests`
      : 'Regexes over-find amounts, rates and dates',
    questions: planned
      ? `${formatCount(answered)} of ${formatCount(planned.requests)} requests answered`
      : 'Each answer is a typed choice with a probability',
    calculate:
      pipeline.computed === null
        ? 'Exact decimal maths, never the model'
        : `${formatCount(pipeline.computed)} findings`,
    gate:
      pipeline.gated === null
        ? 'Low confidence goes to an auditor'
        : `${formatCount(pipeline.gated.review)} sent to review`,
  };
}

const STAGES = [
  { id: 'candidates', who: 'Code', title: 'Find candidates' },
  { id: 'questions', who: 'Jev', title: 'Answer typed questions' },
  { id: 'calculate', who: 'Code', title: 'Calculate' },
  { id: 'gate', who: 'Code', title: 'Gate on confidence' },
] as const;

/** Jev + code at work: the four stages, a chip per request, and the chosen request's answers. */
export function JevPipeline({ progress }: Props) {
  const pipeline = jevPipeline(progress);
  const [chosen, setChosen] = useState<string | null>(null);
  const answered = pipeline.requests.filter(isAnswered);
  // The user's pick, else the first request to come back: later answers never move it.
  const firstBack = answered.reduce<(typeof answered)[number] | undefined>(
    (first, r) =>
      first === undefined || (r.answeredOrder ?? Infinity) < (first.answeredOrder ?? Infinity)
        ? r
        : first,
    undefined,
  );
  const shown = answered.find((r) => r.purpose === chosen) ?? firstBack;
  const details = stageDetail(pipeline);

  if (!progress) return null;
  return (
    <div className="jev-pipeline">
      <ol className="stages" aria-label="Pipeline stages">
        {STAGES.map((stage) => (
          <li key={stage.id} className={`stage stage--${pipeline.stages[stage.id]}`}>
            <span className="stage__marker" aria-hidden="true" />
            <span className="stage__who">{stage.who}</span>
            <span className="stage__title">{stage.title}</span>
            <span className="visually-hidden">: {STATE_WORDS[pipeline.stages[stage.id]]}.</span>
            <span className="stage__detail">{details[stage.id]}</span>
          </li>
        ))}
      </ol>
      {pipeline.requests.length > 0 && (
        <ul className="request-chips" aria-label="Jev requests">
          {pipeline.requests.map((request, i) => {
            const isDone = isAnswered(request);
            const isShown = request === shown;
            return (
              <motion.li
                key={request.purpose}
                initial={{
                  opacity: 0,
                  x: -motionTokens.distance.lg,
                  scale: motionTokens.scale.press,
                }}
                animate={{ opacity: 1, x: 0, scale: isDone ? 1 : motionTokens.scale.subtle }}
                transition={{ ...springs.snappy, delay: i * FAN_STAGGER_S }}
              >
                <button
                  type="button"
                  className={`request-chip${isDone ? ' request-chip--answered' : ''}`}
                  aria-pressed={isShown}
                  aria-disabled={!isDone}
                  onClick={() => {
                    if (isDone) setChosen(request.purpose);
                  }}
                >
                  <span aria-hidden="true">{request.label.short}</span>
                  <span className="visually-hidden">{request.label.full}</span>{' '}
                  {request.questions !== null && (
                    <span className="request-chip__count">
                      {request.questions} <span className="visually-hidden">questions</span>
                    </span>
                  )}
                  {!isDone && <span className="visually-hidden">, waiting</span>}
                </button>
              </motion.li>
            );
          })}
        </ul>
      )}
      {shown && <AnswerCard key={shown.purpose} request={shown} />}
    </div>
  );
}
