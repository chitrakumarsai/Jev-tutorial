import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { Finding, SideResult } from '../../api/types';
import { completedView } from '../../test/fixtures/replay';
import { TraceContext } from '../trace/traceContext';
import { Ledger } from './Ledger';
import { ReviewLane } from './ReviewLane';
import { traceTargets, verdicts } from './ledgerRows';

const view = completedView();
const jevResult = view.sides.jev.result;
const llmResult = view.sides.llm.result;
if (!jevResult || !llmResult) throw new Error('fixture has no side results');

const finding = (overrides: Partial<Finding>): Finding => ({
  id: 'f1',
  kind: 'duplicate_line',
  doc_id: 'inv-2026-10',
  line_ref: 'L5',
  billed: null,
  expected: null,
  variance: '850.00',
  lane: 'auto',
  confidence: 0.6,
  review_reason: null,
  evidence: [{ doc_id: 'inv-2026-10', start: 0, end: 4, text: 'Line' }],
  traceable: true,
  ...overrides,
});

function withScorecard(
  result: SideResult,
  scorecard: Partial<SideResult['scorecard']>,
): SideResult {
  return { ...result, scorecard: { ...result.scorecard, ...scorecard } };
}

describe('verdicts', () => {
  it('reads every outcome the scorecard can give', () => {
    const verdictOf = verdicts(
      withScorecard(jevResult, {
        items: [
          { key_id: 'K1', status: 'correct', finding_id: 'a' },
          { key_id: 'K2', status: 'correct_in_review', finding_id: 'b' },
          { key_id: 'K3', status: 'wrong_value', finding_id: 'c' },
          { key_id: 'K4', status: 'missed', finding_id: null },
        ],
        false_positives: ['d', 'e'],
        trap_hits: ['e'],
      }),
    );

    expect(verdictOf('a')).toEqual({ kind: 'matched', keyId: 'K1', inReview: false });
    expect(verdictOf('b')).toEqual({ kind: 'matched', keyId: 'K2', inReview: true });
    expect(verdictOf('c')).toEqual({ kind: 'wrong_value', keyId: 'K3' });
    expect(verdictOf('d')).toEqual({ kind: 'false_positive', isTrap: false });
    expect(verdictOf('e')).toEqual({ kind: 'false_positive', isTrap: true });
    expect(verdictOf('unknown')).toEqual({ kind: 'pending' });
    expect(verdicts(null)('a')).toEqual({ kind: 'pending' });
  });
});

describe('traceTargets', () => {
  it('puts the passage in the finding’s own document first', () => {
    const targets = traceTargets(
      finding({
        id: 'x',
        evidence: [
          { doc_id: 'msa', start: 1, end: 4, text: '18%' },
          { doc_id: 'inv-2026-10', start: 9, end: 12, text: '$85' },
        ],
      }),
    );

    expect(targets.map((t) => t.highlightId)).toEqual(['x#1', 'x#0']);
  });
});

describe('Ledger', () => {
  it('says so while there is nothing to show yet', () => {
    render(<Ledger side="jev" findings={[]} result={null} />);

    expect(screen.getByRole('region', { name: 'Ledger' })).toHaveTextContent('No findings yet.');
  });

  it('marks the LLM’s false positives and its off total', () => {
    render(<Ledger side="llm" findings={view.sides.llm.findings} result={llmResult} />);

    const ledger = screen.getByRole('region', { name: 'Ledger' });
    expect(within(ledger).getAllByRole('listitem')).toHaveLength(18);
    expect(within(ledger).getAllByText('No quote found in the documents').length).toBeGreaterThan(
      0,
    );
    expect(ledger).toHaveTextContent('the answer key totals $98,510.71');
    // Mid count-up, assistive tech already has the exact figures.
    expect(within(ledger).getByText('$99,190.71')).toHaveClass('visually-hidden');
  });

  it('cites a second document with its own trace button', () => {
    render(<Ledger side="jev" findings={view.sides.jev.findings} result={jevResult} />);

    expect(screen.getAllByText(/“18%”/).length).toBeGreaterThan(0);
    expect(screen.getByText(/matches the answer key/)).toBeInTheDocument();
  });

  it('shows a wrong amount, a trap and a missing total', () => {
    const result = withScorecard(jevResult, {
      items: [{ key_id: 'K9', status: 'wrong_value', finding_id: 'f1' }],
      false_positives: ['f2'],
      trap_hits: ['f2'],
      variance: { expected: '98510.71', reported: null, exact: false },
    });

    render(
      <Ledger
        side="jev"
        findings={[finding({}), finding({ id: 'f2', evidence: [], traceable: false })]}
        result={result}
      />,
    );

    expect(screen.getByText('Wrong amount for K9')).toBeInTheDocument();
    expect(screen.getByText('Fell for a planted trap')).toBeInTheDocument();
    expect(screen.getByText('not reported')).toBeInTheDocument();
  });

  it('leaves review findings to the review lane when asked', () => {
    const review = finding({ id: 'r1', lane: 'review', review_reason: 'Order twins disagree' });

    render(
      <>
        <Ledger side="jev" findings={[review]} result={null} isReviewSeparate />
        <ReviewLane findings={[review]} result={null} notes={['Late fee term unreadable']} />
      </>,
    );

    expect(screen.getByRole('region', { name: 'Ledger' })).toHaveTextContent('No findings yet.');
    const lane = screen.getByRole('region', { name: 'Review lane' });
    expect(lane).toHaveTextContent('Order twins disagree');
    expect(lane).toHaveTextContent('Late fee term unreadable');
    expect(within(lane).getByText(/60%/)).toBeInTheDocument();
  });

  it('shows no total for a scenario without a variance', () => {
    const result = withScorecard(jevResult, { variance: null });

    render(<Ledger side="jev" findings={[finding({})]} result={result} />);

    expect(screen.queryByText('Total variance')).not.toBeInTheDocument();
  });

  describe('clause findings (S2)', () => {
    const clause = (overrides: Partial<Finding>): Finding =>
      finding({
        id: 'c1',
        kind: 'limitation_of_liability',
        doc_id: 'addendum',
        line_ref: 'L068',
        variance: null,
        verdict: 'present',
        risk: 'high',
        evidence: [{ doc_id: 'addendum', start: 0, end: 9, text: 'Liability' }],
        ...overrides,
      });
    const card = (status: 'correct' | 'wrong_value', id = 'c1') =>
      withScorecard(jevResult, {
        items: [{ key_id: 'K01', status, finding_id: id }],
        false_positives: [],
        trap_hits: [],
        variance: null,
      });

    it('shows a present clause with its risk and its line, and no money', () => {
      render(
        <TraceContext value={() => undefined}>
          <Ledger side="jev" findings={[clause({})]} result={card('correct')} />
        </TraceContext>,
      );

      expect(screen.getByText('Limitation of liability')).toBeInTheDocument();
      expect(screen.getByText('Present')).toBeInTheDocument();
      expect(screen.getByText('High risk')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Addendum · L068/ })).toBeInTheDocument();
      expect(screen.queryByText(/Billed|Variance/)).not.toBeInTheDocument();
    });

    it('says plainly when a clause is not in the agreement', () => {
      const absent = clause({
        verdict: 'absent',
        risk: 'critical',
        line_ref: null,
        evidence: [],
        traceable: true, // an absent clause claims nothing to trace
      });

      render(
        <TraceContext value={() => undefined}>
          <Ledger side="jev" findings={[absent]} result={card('correct')} />
        </TraceContext>,
      );

      expect(screen.getByText('Not in the agreement')).toBeInTheDocument();
      expect(screen.getByText('Critical risk')).toBeInTheDocument();
      expect(screen.queryByText('No quote found in the documents')).not.toBeInTheDocument();
      expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });

    it('flags a present clause whose quote was not found', () => {
      const invented = clause({ verdict: 'present', evidence: [], traceable: false });

      render(<Ledger side="llm" findings={[invented]} result={card('correct')} />);

      expect(screen.getByText('No quote found in the documents')).toBeInTheDocument();
    });

    it('marks a partial clause and a clause the key disagrees with', () => {
      render(
        <Ledger
          side="llm"
          findings={[clause({ verdict: 'partial', risk: 'high' })]}
          result={card('wrong_value')}
        />,
      );

      expect(screen.getByText('Partly there')).toBeInTheDocument();
      expect(screen.getByText('Does not match K01')).toBeInTheDocument();
    });
  });

  it('names a citation finding by its id and shows the claim it checks', () => {
    const citation = finding({
      id: 'jev-C7',
      kind: 'citation',
      doc_id: 'msa',
      line_ref: '§5.2',
      variance: null,
      verdict: 'contradicted',
      claim: 'The agreement caps the fuel surcharge at 25%.',
    });
    const card = withScorecard(jevResult, {
      items: [{ key_id: 'K7', status: 'correct', finding_id: 'jev-C7' }],
      false_positives: [],
      trap_hits: [],
      variance: null,
    });

    render(<Ledger side="jev" findings={[citation]} result={card} />);

    expect(screen.getByText('Citation C7')).toBeInTheDocument();
    expect(screen.getByText('“The agreement caps the fuel surcharge at 25%.”')).toBeInTheDocument();
    expect(screen.getByText('Contradicted')).toBeInTheDocument();
  });
});
