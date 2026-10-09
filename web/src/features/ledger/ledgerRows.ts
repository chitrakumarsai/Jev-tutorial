/** How each finding fared against the answer key, once the side's scorecard is in. Pure. */
import type { Finding, SideResult } from '../../api/types';
import { evidenceHighlightId } from '../documents/highlights';
import type { TraceTarget } from '../trace/traceContext';

export type Verdict =
  | { readonly kind: 'pending' }
  | { readonly kind: 'matched'; readonly keyId: string; readonly inReview: boolean }
  | { readonly kind: 'wrong_amount'; readonly keyId: string }
  | { readonly kind: 'false_positive'; readonly isTrap: boolean };

const PENDING: Verdict = { kind: 'pending' };

export function verdicts(result: SideResult | null): (findingId: string) => Verdict {
  if (!result) return () => PENDING;
  const { scorecard } = result;
  const byFinding = new Map<string, Verdict>();
  for (const item of scorecard.items) {
    if (item.finding_id === null) continue;
    if (item.status === 'wrong_amount') {
      byFinding.set(item.finding_id, { kind: 'wrong_amount', keyId: item.key_id });
    } else if (item.status !== 'missed') {
      byFinding.set(item.finding_id, {
        kind: 'matched',
        keyId: item.key_id,
        inReview: item.status === 'correct_in_review',
      });
    }
  }
  const traps = new Set(scorecard.trap_hits);
  for (const id of scorecard.false_positives) {
    byFinding.set(id, { kind: 'false_positive', isTrap: traps.has(id) });
  }
  return (findingId) => byFinding.get(findingId) ?? PENDING;
}

export function isDiscrepancy(verdict: Verdict): boolean {
  return verdict.kind === 'wrong_amount' || verdict.kind === 'false_positive';
}

/** Where each quoted span of a finding lives, primary (its own document) first. */
export function traceTargets(finding: Finding): readonly TraceTarget[] {
  const targets = finding.evidence.map((span, i): TraceTarget => ({
    highlightId: evidenceHighlightId(finding.id, i),
    docId: span.doc_id,
    quote: span.text,
  }));
  const own = targets.filter((t) => t.docId === finding.doc_id);
  return [...own, ...targets.filter((t) => t.docId !== finding.doc_id)];
}
