/** Words for findings: kind labels for people, and the parsed line the LLM pane types out. */
import type { Finding } from '../../api/types';

const KIND_LABELS: Readonly<Record<string, string>> = {
  discount_not_applied: 'Volume discount not applied',
  surcharge_on_undiscounted_base: 'Surcharge on the undiscounted base',
  surcharge_over_cap: 'Fuel surcharge over the cap',
  duplicate_line: 'Duplicate line',
  late_fee_incorrect: 'Late fee incorrect',
  rate_mismatch: 'Rate differs from the contract',
  other: 'Other',
};

const MISSING = '—';

type Verdict = NonNullable<Finding['verdict']>;
type Risk = NonNullable<Finding['risk']>;

/** Clause (S2) and citation (S3) verdicts in plain words, with a symbol so colour is not the only signal. */
export const VERDICT_LABELS: Readonly<
  Record<Verdict, { readonly text: string; readonly symbol: string }>
> = {
  present: { text: 'Present', symbol: '✓' },
  partial: { text: 'Partly there', symbol: '◐' },
  absent: { text: 'Not in the agreement', symbol: '∅' },
  verified: { text: 'Supported', symbol: '✓' },
  unsupported: { text: 'Not supported', symbol: '?' },
  contradicted: { text: 'Contradicted', symbol: '✕' },
  fabricated: { text: 'Quote not in the source', symbol: '✕' },
};

export function riskLabel(risk: Risk): string {
  return `${risk.charAt(0).toUpperCase()}${risk.slice(1)} risk`;
}

/** Whether a finding is about money (S1) rather than a clause or citation verdict. */
export function isMoneyFinding(finding: Finding): boolean {
  return finding.verdict == null;
}

export function kindLabel(kind: string): string {
  const known = KIND_LABELS[kind];
  if (known) return known;
  const words = kind.replaceAll('_', ' ').trim();
  return words ? words.charAt(0).toUpperCase() + words.slice(1) : 'Finding';
}

/** One finding as the parsed response carried it: raw fields, exact strings. */
export function parsedLine(finding: Finding): string {
  if (finding.verdict != null) {
    return [
      finding.doc_id,
      finding.line_ref ?? MISSING,
      finding.kind,
      finding.verdict,
      ...(finding.risk ? [`risk ${finding.risk}`] : []),
      `quote ${finding.traceable ? 'found' : 'not found'}`,
    ].join('  ');
  }
  return [
    finding.doc_id,
    finding.line_ref ?? MISSING,
    finding.kind,
    `billed ${finding.billed ?? MISSING}`,
    `expected ${finding.expected ?? MISSING}`,
    `variance ${finding.variance ?? MISSING}`,
    `quote ${finding.traceable ? 'found' : 'not found'}`,
  ].join('  ');
}
