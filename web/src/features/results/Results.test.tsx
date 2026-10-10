import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { RunResult, SideResult } from '../../api/types';
import { completedView } from '../../test/fixtures/replay';
import { Results } from './Results';

const result = completedView().result;
if (!result?.sides.jev || !result.sides.llm) throw new Error('fixture has no result');
const jev: SideResult = result.sides.jev;

function cells(table: HTMLElement, row: RegExp): (string | null)[] {
  return within(within(table).getByRole('row', { name: row }))
    .getAllByRole('cell')
    .map((cell) => cell.textContent);
}

describe('Results', () => {
  it('compares both sides against the answer key', () => {
    render(<Results result={result} />);

    const scorecard = screen.getByRole('table', { name: 'Scorecard against the answer key' });
    expect(
      within(scorecard)
        .getAllByRole('columnheader')
        .map((h) => h.textContent),
    ).toEqual(['Measure', 'Plain LLM', 'Jev + code']);
    expect(cells(scorecard, /Answer-key items found/)).toEqual(['✓14 of 14', '✓14 of 14']);
    expect(cells(scorecard, /Total variance/)).toEqual(['✕$99,190.71', '✓$98,510.71, exact']);
    expect(cells(scorecard, /traceable/)).toEqual(['✕17 of 18', '✓14 of 14']);
  });

  it('shows what each side cost and where its answers came from', () => {
    render(<Results result={result} />);

    const cost = screen.getByRole('table', { name: 'Cost and latency' });
    expect(cells(cost, /Cost/)).toEqual(['$0.00257', '$0.000755']);
    expect(cells(cost, /Requests/)).toEqual(['1', '13']);
    expect(cells(cost, /Answers from/)).toEqual([
      'gpt-6-luna, recorded Oct 9, 2026',
      'jev-1.13.0, recorded Oct 9, 2026',
    ]);
  });

  it('handles review, traps, an unpriced live side and a missing side', () => {
    const live: SideResult = {
      ...jev,
      metrics: { ...jev.metrics, cost_usd: null },
      provenance: { ...jev.provenance, kind: 'live' },
      scorecard: {
        ...jev.scorecard,
        correct: 12,
        correct_in_review: 2,
        false_positives: ['x'],
        trap_hits: ['x'],
        summary: [
          ...jev.scorecard.summary.slice(0, 1),
          { label: 'Total variance', kind: 'money', value: null, note: 'Not reported', ok: false },
        ],
      },
    };
    const onlyJev: RunResult = { ...result, sides: { jev: live } };

    render(<Results result={onlyJev} />);

    const scorecard = screen.getByRole('table', { name: 'Scorecard against the answer key' });
    expect(cells(scorecard, /items found/)).toEqual(['✓14 of 14 (2 after review)']);
    expect(cells(scorecard, /False positives/)).toEqual(['✕1 (1 planted traps)']);
    expect(cells(scorecard, /Total variance/)).toEqual(['✕Not reported']);
    const cost = screen.getByRole('table', { name: 'Cost and latency' });
    expect(cells(cost, /Cost/)).toEqual(['Not priced']);
    expect(cells(cost, /Answers from/)).toEqual(['jev-1.13.0, live']);
  });

  it('shows only the shared rows for a scenario without summary rows', () => {
    const plain: SideResult = {
      ...jev,
      scorecard: { ...jev.scorecard, summary: [], variance: null },
    };

    render(<Results result={{ ...result, sides: { jev: plain } }} />);

    const scorecard = screen.getByRole('table', { name: 'Scorecard against the answer key' });
    const labels = within(scorecard)
      .getAllByRole('rowheader')
      .map((th) => th.textContent);
    expect(labels).toEqual([
      'Answer-key items found',
      'False positives',
      'Findings traceable to a quote',
    ]);
  });

  it('renders nothing for a result without sides', () => {
    const { container } = render(<Results result={{ ...result, sides: {} }} />);

    expect(container).toBeEmptyDOMElement();
  });
});
