import { motion } from 'motion/react';
import { useId, useState } from 'react';

import { getConsistency } from '../../api/client';
import type { ConsistencyReport, SideName } from '../../api/types';
import { useResource } from '../../hooks/useResource';
import { formatDate, formatTime } from '../../lib/format';
import { motionTokens } from '../../lib/motion';
import './consistency.css';

type Props = {
  scenarioId: string;
};

type Side = ConsistencyReport['sides'][string];

const SIDES: readonly { id: SideName; title: string }[] = [
  { id: 'llm', title: 'Plain LLM' },
  { id: 'jev', title: 'Jev + code' },
];
const ROW_STAGGER_S = 0.04;
const MAX_STAGGERED_ROWS = 10; // longer tables still finish fading in quickly

const loadConsistency = (scenarioId: string, signal: AbortSignal) =>
  getConsistency(scenarioId, { signal });

function plural(count: number, word: string): string {
  return `${String(count)} ${word}${count === 1 ? '' : 's'}`;
}

function summary(side: Side, runs: number): string {
  const items = side.items.length;
  const across = plural(runs, 'run');
  if (side.changed > 0) return `${plural(side.changed, 'item')} changed across ${across}`;
  return items === 1
    ? `same answer on the 1 item in ${across}`
    : `same answer on all ${String(items)} items in ${across}`;
}

function SideTable({
  title,
  side,
  report,
}: {
  title: string;
  side: Side;
  report: ConsistencyReport;
}) {
  const runs = report.recordings;
  const captionId = useId();
  return (
    // Scrolls sideways inside itself on a narrow screen; the page never does.
    <div className="consistency__scroll" role="region" aria-labelledby={captionId} tabIndex={0}>
      <table className="consistency-table">
        <caption id={captionId}>
          {title}: {summary(side, runs.length)}
        </caption>
        <thead>
          <tr>
            <th scope="col">Item</th>
            {runs.map((r, i) => (
              <th key={r.id} scope="col">
                Run {i + 1}
                <span className="consistency-table__date">
                  {formatDate(r.recorded_at)}, {formatTime(r.recorded_at)}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {side.items.map((item, i) => (
            <motion.tr
              key={item.key_id}
              className={item.changed ? 'consistency-table__changed' : undefined}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{
                duration: motionTokens.duration.fast,
                delay: Math.min(i, MAX_STAGGERED_ROWS) * ROW_STAGGER_S,
              }}
            >
              <th scope="row">
                {item.label}
                {item.changed && (
                  <span className="consistency-table__flag">
                    <span aria-hidden="true"> ⟳</span> changed
                  </span>
                )}
              </th>
              {item.answers.map((answer, run) => (
                <td key={runs[run]?.id ?? run}>{answer}</td>
              ))}
            </motion.tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Consistency ×3 (PLAN-P7): each side's answers across the scenario's recorded live runs. */
export function ConsistencyPanel({ scenarioId }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const panelId = useId();
  // Loads only while open; useResource aborts on close and ignores stale answers.
  const consistency = useResource(isOpen ? scenarioId : null, loadConsistency, attempt);

  return (
    <section className="consistency" aria-label="Consistency across recorded runs">
      <button
        type="button"
        className="consistency__toggle"
        aria-expanded={isOpen}
        aria-controls={panelId}
        onClick={() => {
          setIsOpen((open) => !open);
        }}
      >
        Consistency ×3
      </button>
      {/* Mounted before it speaks, so screen readers announce the change. */}
      <p role="status" className="visually-hidden">
        {isOpen && consistency.status === 'loading' ? 'Replaying the recorded runs…' : ''}
      </p>
      <div id={panelId} hidden={!isOpen}>
        {isOpen && consistency.status === 'error' && (
          <p role="alert" className="consistency__problem">
            The recorded runs could not be loaded.{' '}
            <button
              type="button"
              className="consistency__retry"
              onClick={() => {
                setAttempt((n) => n + 1);
              }}
            >
              Try again
            </button>
          </p>
        )}
        {isOpen && consistency.status === 'ready' && (
          <>
            <p className="consistency__note">
              {plural(consistency.data.recordings.length, 'separate recorded live run')}, replayed:
              no new calls, no spend.
            </p>
            <div className="consistency__tables">
              {SIDES.map(({ id, title }) => {
                const side = consistency.data.sides[id];
                return side ? (
                  <SideTable key={id} title={title} side={side} report={consistency.data} />
                ) : null;
              })}
            </div>
          </>
        )}
      </div>
    </section>
  );
}
