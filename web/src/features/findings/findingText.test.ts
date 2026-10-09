import { describe, expect, it } from 'vitest';

import { completedView } from '../../test/fixtures/replay';
import { kindLabel, parsedLine } from './findingText';

describe('kindLabel', () => {
  it('names the known kinds', () => {
    expect(kindLabel('surcharge_over_cap')).toBe('Fuel surcharge over the cap');
  });

  it('falls back to readable words for a kind it does not know', () => {
    expect(kindLabel('rate_typo_x')).toBe('Rate typo x');
    expect(kindLabel('')).toBe('Finding');
  });
});

describe('parsedLine', () => {
  it('prints the raw fields of an untraceable LLM finding', () => {
    const first = completedView().sides.llm.findings[0];
    if (!first) throw new Error('fixture has no LLM findings');

    expect(parsedLine(first)).toBe(
      'inv-2026-02  L4  other  billed 340.00  expected 170.00  variance 170.00  quote not found',
    );
  });

  it('marks missing fields with a dash', () => {
    expect(
      parsedLine({
        id: 'x',
        kind: 'other',
        doc_id: 'msa',
        lane: 'auto',
        evidence: [],
        traceable: true,
      }),
    ).toBe('msa  —  other  billed —  expected —  variance —  quote found');
  });
});
