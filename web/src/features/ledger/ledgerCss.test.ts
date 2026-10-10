import { describe, expect, it } from 'vitest';

import ledgerCss from './ledger.css?raw';
import type { Verdict } from './ledgerRows';

// Classes are built from `verdict.kind`, so a renamed kind silently loses its styling.
const DISCREPANCIES = [
  'wrong_value',
  'false_positive',
] as const satisfies readonly Verdict['kind'][];
const WITH_VERDICT_TEXT = [
  'matched',
  ...DISCREPANCIES,
] as const satisfies readonly Verdict['kind'][];

describe('ledger.css', () => {
  it.each(DISCREPANCIES)('marks a %s row as a discrepancy', (kind) => {
    expect(ledgerCss).toContain(`.ledger-row--${kind}`);
  });

  it.each(WITH_VERDICT_TEXT)('styles the verdict text of a %s row', (kind) => {
    expect(ledgerCss).toContain(`.ledger-row__verdict--${kind}`);
  });
});
