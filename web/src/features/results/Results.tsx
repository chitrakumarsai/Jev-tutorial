import { motion } from 'motion/react';
import { useId, type ReactNode } from 'react';

import type { RunResult, SideName, SideResult } from '../../api/types';
import { formatCost, formatCount, formatDate, formatDuration, formatMoney } from '../../lib/format';
import { motionTokens, springs } from '../../lib/motion';
import './results.css';

type Props = {
  result: RunResult;
};

type Cell = { readonly text: string; readonly ok?: boolean };
type Row = {
  readonly label: string;
  readonly cell: (side: SideResult) => Cell;
  readonly extra?: (side: SideResult, all: readonly SideResult[]) => ReactNode;
};

const SIDES: readonly { id: SideName; title: string }[] = [
  { id: 'llm', title: 'Plain LLM' },
  { id: 'jev', title: 'Jev + code' },
];
const ROW_STAGGER_S = 0.06;

const count = (side: SideResult, status: string) =>
  side.scorecard.items.filter((item) => item.status === status).length;

const SCORE_ROWS: readonly Row[] = [
  {
    label: 'Answer-key items found',
    cell: ({ scorecard: s }) => ({
      text: `${formatCount(s.correct + s.correct_in_review)} of ${formatCount(s.of)}${
        s.correct_in_review > 0 ? ` (${formatCount(s.correct_in_review)} after review)` : ''
      }`,
      ok: s.correct + s.correct_in_review === s.of,
    }),
  },
  {
    label: 'Wrong amounts',
    cell: (side) => ({
      text: formatCount(count(side, 'wrong_amount')),
      ok: count(side, 'wrong_amount') === 0,
    }),
  },
  {
    label: 'False positives',
    cell: ({ scorecard: s }) => ({
      text: `${formatCount(s.false_positives.length)}${
        s.trap_hits.length > 0 ? ` (${formatCount(s.trap_hits.length)} planted traps)` : ''
      }`,
      ok: s.false_positives.length === 0,
    }),
  },
  {
    label: 'Total variance',
    cell: ({ scorecard: s }) => ({
      text:
        s.total_variance_reported === null
          ? 'Not reported'
          : `${formatMoney(s.total_variance_reported)}${s.total_variance_exact ? ', exact' : ''}`,
      ok: s.total_variance_exact,
    }),
  },
  {
    label: 'Findings traceable to a quote',
    cell: ({ findings }) => {
      const traceable = findings.filter((f) => f.traceable).length;
      return {
        text: `${formatCount(traceable)} of ${formatCount(findings.length)}`,
        ok: traceable === findings.length,
      };
    },
  },
];

function TimeBar({ side, all }: { side: SideResult; all: readonly SideResult[] }) {
  const longest = Math.max(...all.map((s) => s.metrics.latency_ms));
  const share = longest > 0 ? side.metrics.latency_ms / longest : 0;
  return (
    <span className="meter-bar" aria-hidden="true">
      <motion.span
        className={`meter-bar__fill meter-bar__fill--${side.side}`}
        initial={{ scaleX: 0 }}
        animate={{ scaleX: share }}
        transition={{ duration: motionTokens.duration.slow, ease: motionTokens.easing.smooth }}
      />
    </span>
  );
}

function source(side: SideResult): string {
  const { provenance } = side;
  const models = provenance.models.join(', ');
  return provenance.kind === 'recorded'
    ? `${models}, recorded ${provenance.recorded_at ? formatDate(provenance.recorded_at) : ''}`.trim()
    : `${models}, live`;
}

const COST_ROWS: readonly Row[] = [
  { label: 'Requests', cell: ({ metrics }) => ({ text: formatCount(metrics.requests) }) },
  { label: 'Input tokens', cell: ({ metrics }) => ({ text: formatCount(metrics.input_tokens) }) },
  { label: 'Output tokens', cell: ({ metrics }) => ({ text: formatCount(metrics.output_tokens) }) },
  {
    label: 'Cost',
    cell: ({ metrics }) => ({
      text: metrics.cost_usd === null ? 'Not priced' : formatCost(metrics.cost_usd),
    }),
  },
  {
    label: 'Time in this run',
    cell: ({ metrics }) => ({ text: formatDuration(metrics.latency_ms) }),
    extra: (side, all) => <TimeBar side={side} all={all} />,
  },
  { label: 'Answers from', cell: (side) => ({ text: source(side) }) },
];

function Table({
  caption,
  rows,
  sides,
}: {
  caption: string;
  rows: readonly Row[];
  sides: readonly SideResult[];
}) {
  return (
    <table className="results-table">
      <caption>{caption}</caption>
      <thead>
        <tr>
          <th scope="col">
            <span className="visually-hidden">Measure</span>
          </th>
          {SIDES.filter((s) => sides.some((r) => r.side === s.id)).map((s) => (
            <th key={s.id} scope="col" className={`results-table__side--${s.id}`}>
              {s.title}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <motion.tr
            key={row.label}
            initial={{ opacity: 0, y: motionTokens.distance.sm }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...springs.gentle, delay: i * ROW_STAGGER_S }}
          >
            <th scope="row">{row.label}</th>
            {sides.map((side) => {
              const cell = row.cell(side);
              return (
                <td
                  key={side.side}
                  className={cell.ok === false ? 'results-table__off' : undefined}
                >
                  {cell.ok !== undefined && (
                    <span className="results-table__glyph" aria-hidden="true">
                      {cell.ok ? '✓' : '✕'}
                    </span>
                  )}
                  {cell.text}
                  {row.extra?.(side, sides)}
                </td>
              );
            })}
          </motion.tr>
        ))}
      </tbody>
    </table>
  );
}

/** The verdict once both sides finish: how each did against the answer key, and its cost. */
export function Results({ result }: Props) {
  const headingId = useId();
  const sides = SIDES.map((s) => result.sides[s.id]).filter((s): s is SideResult => s != null);
  if (sides.length === 0) return null;
  return (
    <section className="results" aria-labelledby={headingId}>
      <h2 id={headingId} className="pane-heading">
        Results
      </h2>
      <div className="results__tables">
        <Table caption="Scorecard against the answer key" rows={SCORE_ROWS} sides={sides} />
        <Table caption="Cost and latency" rows={COST_ROWS} sides={sides} />
      </div>
    </section>
  );
}
