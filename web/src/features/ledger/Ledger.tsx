import { motion } from 'motion/react';
import { useId } from 'react';

import type { Finding, SideName, SideResult } from '../../api/types';
import { CountUpMoney } from '../../components/count-up/CountUpMoney';
import { formatMoney } from '../../lib/format';
import { motionTokens } from '../../lib/motion';
import { LedgerRow } from './LedgerRow';
import { verdicts } from './ledgerRows';
import './ledger.css';

type Props = {
  side: SideName;
  findings: readonly Finding[];
  /** The side's result, once it has finished: its scorecard decides each row's verdict. */
  result: SideResult | null;
  /** Leave out review-lane findings (they are shown in the review lane instead). */
  isReviewSeparate?: boolean;
};

type VarianceTotal = NonNullable<SideResult['scorecard']['variance']>;

function Total({ variance }: { variance: VarianceTotal }) {
  const { reported, expected, exact: isExact } = variance;
  return (
    <motion.p
      className={`ledger-total ledger-total--${isExact ? 'exact' : 'off'}`}
      animate={{ x: isExact ? 0 : [...motionTokens.shake] }}
      transition={{ duration: motionTokens.duration.slow }}
    >
      <span className="ledger-total__label">Total variance</span>{' '}
      {reported === null ? (
        <span className="ledger-total__figure">not reported</span>
      ) : (
        <CountUpMoney className="ledger-total__figure" value={reported} />
      )}{' '}
      <span className="ledger-total__verdict">
        <span aria-hidden="true">{isExact ? '✓' : '✕'}</span>{' '}
        {isExact ? 'matches the answer key' : `the answer key totals ${formatMoney(expected)}`}
      </span>
    </motion.p>
  );
}

/** A side's findings as ledger lines, then the total once the answer key has scored them. */
export function Ledger({ side, findings, result, isReviewSeparate = false }: Props) {
  const headingId = useId();
  const verdictOf = verdicts(result);
  const rows = isReviewSeparate ? findings.filter((f) => f.lane !== 'review') : findings;
  return (
    <section className="ledger" aria-labelledby={headingId}>
      <h3 id={headingId} className="ledger__heading">
        Ledger
      </h3>
      {rows.length === 0 ? (
        <p className="ledger__empty">{result ? 'No findings.' : 'No findings yet.'}</p>
      ) : (
        <ol className="ledger__rows">
          {rows.map((finding) => (
            <LedgerRow
              key={finding.id}
              finding={finding}
              side={side}
              verdict={verdictOf(finding.id)}
            />
          ))}
        </ol>
      )}
      {result?.scorecard.variance && <Total variance={result.scorecard.variance} />}
    </section>
  );
}
