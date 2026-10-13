import { motion } from 'motion/react';
import { useEffect, useId, useState } from 'react';

import { getConsistency } from '../../api/client';
import type { ConsistencyReport, SideName } from '../../api/types';
import { formatDate } from '../../lib/format';
import { motionTokens } from '../../lib/motion';
import './consistency.css';

type Props = {
  scenarioId: string;
};

type State =
  | { readonly kind: 'closed' }
  | { readonly kind: 'loading' }
  | { readonly kind: 'ready'; readonly report: ConsistencyReport }
  | { readonly kind: 'error' };

const SIDES: readonly { id: SideName; title: string }[] = [
  { id: 'llm', title: 'Plain LLM' },
  { id: 'jev', title: 'Jev + code' },
];
const ROW_STAGGER_S = 0.04;

function summary(changed: number, items: number, runs: number): string {
  return changed === 0
    ? `same answer on all ${String(items)} items in ${String(runs)} runs`
    : `${String(changed)} ${changed === 1 ? 'item' : 'items'} changed across ${String(runs)} runs`;
}

function SideTable({
  title,
  side,
  report,
}: {
  title: string;
  side: ConsistencyReport['sides'][string];
  report: ConsistencyReport;
}) {
  const runs = report.recordings;
  return (
    <table className="consistency-table">
      <caption>
        {title}: {summary(side.changed, side.items.length, runs.length)}
      </caption>
      <thead>
        <tr>
          <th scope="col">Item</th>
          {runs.map((r, i) => (
            <th key={r.id} scope="col">
              Run {i + 1}
              <span className="consistency-table__date">{formatDate(r.recorded_at)}</span>
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
            transition={{ duration: motionTokens.duration.fast, delay: i * ROW_STAGGER_S }}
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
              <td key={report.recordings[run]?.id ?? run}>{answer}</td>
            ))}
          </motion.tr>
        ))}
      </tbody>
    </table>
  );
}

/** Consistency ×3 (PLAN-P7): each side's answers across the scenario's recorded live runs. */
export function ConsistencyPanel({ scenarioId }: Props) {
  const [state, setState] = useState<State>({ kind: 'closed' });
  const panelId = useId();
  const isOpen = state.kind !== 'closed';

  useEffect(() => {
    if (state.kind !== 'loading') return;
    const controller = new AbortController();
    getConsistency(scenarioId, { signal: controller.signal }).then(
      (report) => {
        setState({ kind: 'ready', report });
      },
      () => {
        if (!controller.signal.aborted) setState({ kind: 'error' });
      },
    );
    return () => {
      controller.abort();
    };
  }, [state.kind, scenarioId]);

  return (
    <section className="consistency" aria-label="Consistency across recorded runs">
      <button
        type="button"
        className="consistency__toggle"
        aria-expanded={isOpen}
        aria-controls={panelId}
        onClick={() => {
          setState(isOpen ? { kind: 'closed' } : { kind: 'loading' });
        }}
      >
        Consistency ×3
      </button>
      <div id={panelId} hidden={!isOpen}>
        {state.kind === 'loading' && <p role="status">Replaying the recorded runs…</p>}
        {state.kind === 'error' && <p role="alert">The recorded runs could not be loaded.</p>}
        {state.kind === 'ready' && (
          <>
            <p className="consistency__note">
              {state.report.recordings.length} separate recorded live runs, replayed: no new calls,
              no spend.
            </p>
            <div className="consistency__tables">
              {SIDES.map(({ id, title }) => {
                const side = state.report.sides[id];
                return side ? (
                  <SideTable key={id} title={title} side={side} report={state.report} />
                ) : null;
              })}
            </div>
          </>
        )}
      </div>
    </section>
  );
}
