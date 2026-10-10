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

type SummaryRow = SideResult['scorecard']['summary'][number];

function summaryText(row: SummaryRow): string {
  if (row.value === null) return row.note ?? 'Not reported';
  const value =
    row.kind === 'count'
      ? formatCount(Number(row.value))
      : row.kind === 'money'
        ? formatMoney(row.value)
        : row.value;
  return row.note ? `${value}, ${row.note}` : value;
}

/** Scenario-specific rows, as the backend's scorer supplied them, in its order. */
function summaryRows(sides: readonly SideResult[]): Row[] {
  const labels = [...new Set(sides.flatMap((s) => s.scorecard.summary.map((r) => r.label)))];
  return labels.map((label) => ({
    label,
    cell: (side) => {
      const row = side.scorecard.summary.find((r) => r.label === label);
      if (!row) return { text: '—' };
      const text = summaryText(row);
      return row.ok === null || row.ok === undefined ? { text } : { text, ok: row.ok };
    },
  }));
}

const FOUND_ROW: Row = {
  label: 'Answer-key items found',
  cell: ({ scorecard: s }) => ({
    text: `${formatCount(s.correct + s.correct_in_review)} of ${formatCount(s.of)}${
      s.correct_in_review > 0 ? ` (${formatCount(s.correct_in_review)} after review)` : ''
    }`,
    ok: s.correct + s.correct_in_review === s.of,
  }),
};

const SHARED_ROWS: readonly Row[] = [
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
        <Table
          caption="Scorecard against the answer key"
          rows={[FOUND_ROW, ...summaryRows(sides), ...SHARED_ROWS]}
          sides={sides}
        />
        <Table caption="Cost and latency" rows={COST_ROWS} sides={sides} />
      </div>
    </section>
  );
}
