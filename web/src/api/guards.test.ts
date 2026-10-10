import { describe, expect, it } from 'vitest';

import { lastReplayEvent } from '../test/fixtures/replay';
import {
  ScorecardSchema,
  BudgetReportSchema,
  FindingSchema,
  HealthSchema,
  MoneySchema,
  RunResultSchema,
  envelopeOf,
} from './guards';

const result = (lastReplayEvent().data as { result: Record<string, unknown> }).result;
const sides = result.sides as Record<string, { findings: Record<string, unknown>[] }>;
const finding = sides.jev?.findings[0] ?? {};

describe('response guards', () => {
  it('accept a real replay result unchanged', () => {
    expect(RunResultSchema.parse(result)).toEqual(result);
  });

  it('drop keys the client does not know', () => {
    const parsed = FindingSchema.parse({ ...finding, injected: '<img src=x>' });

    expect(parsed).not.toHaveProperty('injected');
  });

  it.each([
    ['a confidence above 1', { confidence: 1.2 }],
    [
      'an evidence span that ends before it starts',
      { evidence: [{ doc_id: 'msa', start: 9, end: 3, text: 'x' }] },
    ],
    ['a negative span offset', { evidence: [{ doc_id: 'msa', start: -1, end: 3, text: 'x' }] }],
    ['an unknown lane', { lane: 'skip' }],
    ['a formatted amount', { variance: '$1,250.00' }],
  ])('reject a finding with %s', (_label, patch) => {
    expect(FindingSchema.safeParse({ ...finding, ...patch }).success).toBe(false);
  });

  it.each(['0', '12.50', '-3.1', '0.000754572', '0E-8', '1.5e+3'])(
    'accept the Decimal string %s',
    (amount) => {
      expect(MoneySchema.parse(amount)).toBe(amount);
    },
  );

  it.each(['', 'NaN', 'Infinity', '1,250.00', '$5', ' 1', '1.', 12])(
    'reject %j as money',
    (amount) => {
      expect(MoneySchema.safeParse(amount).success).toBe(false);
    },
  );

  it('read nullable budget amounts', () => {
    const report = {
      ledger_initialised: false,
      providers: [
        {
          provider: 'openai',
          cap: '5.00',
          key_configured: false,
          spent: null,
          reserved: null,
          remaining: null,
        },
      ],
    };

    expect(BudgetReportSchema.parse(report)).toEqual(report);
  });
});

describe('envelopeOf', () => {
  const HealthEnvelope = envelopeOf(HealthSchema);

  it('reads a success envelope', () => {
    expect(HealthEnvelope.parse({ success: true, data: { status: 'ok' }, error: null })).toEqual({
      success: true,
      data: { status: 'ok' },
      error: null,
    });
  });

  it('reads a failure envelope', () => {
    const failure = {
      success: false,
      data: null,
      error: { code: 'UNKNOWN_RUN', message: 'Unknown run' },
    };

    expect(HealthEnvelope.parse(failure)).toEqual(failure);
  });

  it.each([
    ['success without data', { success: true, data: null, error: null }],
    ['failure without an error', { success: false, data: null, error: null }],
    [
      'success carrying an error',
      { success: true, data: { status: 'ok' }, error: { code: 'X', message: 'y' } },
    ],
    ['data of the wrong shape', { success: true, data: { status: 'down' }, error: null }],
  ])('rejects %s', (_label, body) => {
    expect(HealthEnvelope.safeParse(body).success).toBe(false);
  });
});

describe('ScorecardSchema summary rows', () => {
  const card = {
    items: [],
    false_positives: [],
    trap_hits: [],
    of: 0,
    correct: 0,
    correct_in_review: 0,
  };
  const row = (kind: string, value: string | null) => ({
    ...card,
    summary: [{ label: 'x', kind, value }],
  });

  it.each([
    ['count', '12'],
    ['money', '-98510.71'],
    ['text', 'anything'],
    ['money', null],
  ])('accepts a %s value %s', (kind, value) => {
    expect(ScorecardSchema.safeParse(row(kind, value)).success).toBe(true);
  });

  it.each([
    ['count', '1.5'],
    ['count', 'NaN'],
    ['money', '$1,250.00'],
  ])('rejects a %s value %s the UI could not format', (kind, value) => {
    expect(ScorecardSchema.safeParse(row(kind, value)).success).toBe(false);
  });
});

describe('FindingSchema for S2 and S3', () => {
  const base = { id: 'F1', kind: 'x', doc_id: 'd', lane: 'auto', evidence: [], traceable: true };

  it('accepts a clause verdict with a risk level, and a citation with its claim', () => {
    expect(FindingSchema.safeParse({ ...base, verdict: 'present', risk: 'high' }).success).toBe(
      true,
    );
    expect(
      FindingSchema.safeParse({ ...base, verdict: 'fabricated', claim: 'After 800 loads.' })
        .success,
    ).toBe(true);
  });

  it.each([
    ['verdict', 'maybe'],
    ['risk', 'severe'],
  ])('rejects an unknown %s %s', (field, value) => {
    expect(FindingSchema.safeParse({ ...base, [field]: value }).success).toBe(false);
  });

  it('accepts a labelled score item', () => {
    const item = { key_id: 'K3', status: 'missed', finding_id: null, label: 'Breach notice' };
    const card = { items: [item], false_positives: [], trap_hits: [], summary: [] };

    expect(
      ScorecardSchema.safeParse({ ...card, of: 1, correct: 0, correct_in_review: 0 }).success,
    ).toBe(true);
  });
});
