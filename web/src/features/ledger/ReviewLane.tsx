import { useId } from 'react';

import type { Finding, SideResult } from '../../api/types';
import { LedgerRow } from './LedgerRow';
import { verdicts } from './ledgerRows';
import './ledger.css';

type Props = {
  findings: readonly Finding[];
  result: SideResult | null;
  /** Why the gate could not decide some items (e.g. a contract term it could not read). */
  notes: readonly string[];
};

/**
 * Findings Jev was not confident enough about go to an auditor instead of the ledger. The
 * rows share their layout id with the ledger, so a gated finding glides across.
 */
export function ReviewLane({ findings, result, notes }: Props) {
  const headingId = useId();
  const verdictOf = verdicts(result);
  const inReview = findings.filter((f) => f.lane === 'review');
  return (
    <section className="review-lane" aria-labelledby={headingId}>
      <h3 id={headingId} className="ledger__heading">
        Review lane
      </h3>
      {inReview.length === 0 ? (
        <p className="ledger__empty">
          Nothing needed review: every finding cleared the confidence gate.
        </p>
      ) : (
        <ol className="ledger__rows">
          {inReview.map((finding) => (
            <LedgerRow
              key={finding.id}
              finding={finding}
              side="jev"
              verdict={verdictOf(finding.id)}
            />
          ))}
        </ol>
      )}
      {notes.length > 0 && (
        <ul className="review-lane__notes">
          {notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
