import { motion } from 'motion/react';
import { use } from 'react';

import type { Finding, SideName } from '../../api/types';
import { ConfidenceRing } from '../../components/confidence-ring/ConfidenceRing';
import { CountUpMoney } from '../../components/count-up/CountUpMoney';
import { formatMoney } from '../../lib/format';
import { motionTokens, springs } from '../../lib/motion';
import { documentLabel } from '../documents/documentLabel';
import {
  VERDICT_LABELS,
  citationId,
  isMoneyFinding,
  kindLabel,
  riskLabel,
} from '../findings/findingText';
import { TraceButton } from '../trace/TraceButton';
import { CitationFocusContext } from './citationFocus';
import { isDiscrepancy, traceTargets, type Verdict } from './ledgerRows';

type Props = {
  finding: Finding;
  side: SideName;
  verdict: Verdict;
};

function verdictText(verdict: Verdict, isMoney: boolean): string {
  switch (verdict.kind) {
    case 'pending':
      return 'Recorded';
    case 'matched':
      return verdict.inReview
        ? `Matches ${verdict.keyId}, after review`
        : `Matches ${verdict.keyId}`;
    case 'wrong_value':
      return isMoney ? `Wrong amount for ${verdict.keyId}` : `Does not match ${verdict.keyId}`;
    case 'false_positive':
      return verdict.isTrap ? 'Fell for a planted trap' : 'Not in the answer key';
  }
}

function Mark({ verdict }: { verdict: Verdict }) {
  if (isDiscrepancy(verdict)) {
    return (
      <span className="ledger-row__mark ledger-row__mark--wrong" aria-hidden="true">
        ✕
      </span>
    );
  }
  return (
    <svg
      className={`ledger-row__mark ledger-row__mark--${verdict.kind}`}
      viewBox="0 0 16 16"
      aria-hidden="true"
    >
      <motion.path
        d="M3 8.5 6.5 12 13 4"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: motionTokens.duration.normal, ease: motionTokens.easing.smooth }}
      />
    </svg>
  );
}

/** One finding as a ledger line: it ticks in, and shakes if the answer key disagrees. */
export function LedgerRow({ finding, side, verdict }: Props) {
  const [primary, ...others] = traceTargets(finding);
  const isWrong = isDiscrepancy(verdict);
  const focusedCitation = use(CitationFocusContext);
  const citation = finding.kind === 'citation' ? citationId(finding) : undefined;
  const isCurrent = citation !== undefined && citation === focusedCitation;
  const billed = finding.billed ? formatMoney(finding.billed) : null;
  const where = `${documentLabel(finding.doc_id).short}${finding.line_ref ? ` · ${finding.line_ref}` : ''}`;
  return (
    <motion.li
      layoutId={finding.id}
      className={`ledger-row ledger-row--${verdict.kind}${isCurrent ? ' ledger-row--current' : ''}`}
      data-citation={citation}
      aria-current={isCurrent ? 'true' : undefined}
      initial={{ opacity: 0, y: -motionTokens.distance.sm }}
      animate={{ opacity: 1, y: 0, x: isWrong ? [...motionTokens.shake] : 0 }}
      transition={{ ...springs.snappy, x: { duration: motionTokens.duration.slow } }}
    >
      <Mark verdict={verdict} />
      <p className="ledger-row__what">
        <span className="ledger-row__where">
          {/* With no figure to press, the place itself leads to the passage. */}
          {!billed && !finding.variance && primary ? (
            <TraceButton target={primary}>{where}</TraceButton>
          ) : (
            where
          )}
        </span>{' '}
        <span className="ledger-row__kind">
          {finding.kind === 'citation'
            ? `Citation ${citationId(finding)}`
            : kindLabel(finding.kind)}
        </span>
      </p>
      {finding.claim && <p className="ledger-row__claim">“{finding.claim}”</p>}
      {side === 'jev' && finding.confidence != null && (
        <ConfidenceRing
          value={finding.confidence}
          tone={finding.lane === 'review' ? 'review' : 'jev'}
        />
      )}
      <p className="ledger-row__figures">
        {finding.verdict != null && (
          <span className={`ledger-row__chip ledger-row__chip--${finding.verdict}`}>
            <span aria-hidden="true">{VERDICT_LABELS[finding.verdict].symbol}</span>
            {VERDICT_LABELS[finding.verdict].text}
          </span>
        )}
        {finding.risk != null && (
          <span className={`ledger-row__risk ledger-row__risk--${finding.risk}`}>
            {riskLabel(finding.risk)}
          </span>
        )}
        {billed && (
          <span>
            Billed {primary ? <TraceButton target={primary}>{billed}</TraceButton> : billed}
          </span>
        )}
        {finding.expected && <span>Expected {formatMoney(finding.expected)}</span>}
        {finding.variance && (
          <span className="ledger-row__variance">
            Variance{' '}
            {!billed && primary ? (
              <TraceButton target={primary}>
                <CountUpMoney value={finding.variance} />
              </TraceButton>
            ) : (
              <CountUpMoney value={finding.variance} />
            )}
          </span>
        )}
      </p>
      <p className="ledger-row__notes">
        <span className={`ledger-row__verdict ledger-row__verdict--${verdict.kind}`}>
          {verdictText(verdict, isMoneyFinding(finding))}
        </span>
        {!finding.traceable && (
          <span className="ledger-row__flag">No quote found in the documents</span>
        )}
        {others.map((target) => (
          <span key={target.highlightId}>
            Cites <TraceButton target={target}>“{target.quote}”</TraceButton>
          </span>
        ))}
        {finding.review_reason && (
          <span className="ledger-row__reason">{finding.review_reason}</span>
        )}
      </p>
    </motion.li>
  );
}
