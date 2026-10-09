/**
 * Spend against the per-key cap, one row per provider. The figures are the backend's Decimal
 * strings, formatted; the bar is a native <meter>, so the browser (not this page) works out
 * how full it is.
 */
import { useId } from 'react';

import type { BudgetReport } from '../../api/types';
import { formatMoney } from '../../lib/format';
import './budget.css';

type Row = BudgetReport['providers'][number];

const PROVIDERS: Readonly<Record<string, string>> = {
  openai: 'OpenAI (plain LLM)',
  typesafe: 'TypeSafe (Jev)',
};

function providerName(provider: string): string {
  return PROVIDERS[provider] ?? provider;
}

function RowStatus({ row, hasLedger }: { row: Row; hasLedger: boolean }) {
  if (!row.key_configured) return <>No key set on the server</>;
  if (!hasLedger || row.spent === null) return <>No spend recorded</>;
  return (
    <>
      {formatMoney(row.spent)} of {formatMoney(row.cap)} spent
      {row.remaining !== null && <> · {formatMoney(row.remaining)} left</>}
    </>
  );
}

function BudgetRow({ row, hasLedger }: { row: Row; hasLedger: boolean }) {
  const id = useId();
  const isMetered = row.key_configured && hasLedger && row.spent !== null;
  return (
    <li className="budget__row">
      <span id={`${id}-name`} className="budget__name">
        {providerName(row.provider)}
      </span>
      <span id={`${id}-status`} className="budget__status">
        <RowStatus row={row} hasLedger={hasLedger} />
      </span>
      {isMetered && (
        <meter
          className="budget__meter"
          min={0}
          max={row.cap}
          value={row.spent ?? undefined}
          aria-labelledby={`${id}-name`}
          aria-describedby={`${id}-status`}
        />
      )}
    </li>
  );
}

export function BudgetMeter({ report }: { report: BudgetReport }) {
  const headingId = useId();
  return (
    <section className="budget" aria-labelledby={headingId}>
      <p id={headingId} className="eyebrow budget__heading">
        Live budget
      </p>
      {!report.ledger_initialised && (
        <p className="budget__note">The server has no spend ledger yet, so it refuses live runs.</p>
      )}
      <ul className="budget__rows">
        {report.providers.map((row) => (
          <BudgetRow key={row.provider} row={row} hasLedger={report.ledger_initialised} />
        ))}
      </ul>
    </section>
  );
}
