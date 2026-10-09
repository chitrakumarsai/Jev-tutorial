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

export function kindLabel(kind: string): string {
  const known = KIND_LABELS[kind];
  if (known) return known;
  const words = kind.replaceAll('_', ' ').trim();
  return words ? words.charAt(0).toUpperCase() + words.slice(1) : 'Finding';
}

/** One finding as the parsed response carried it: raw fields, exact strings. */
export function parsedLine(finding: Finding): string {
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
