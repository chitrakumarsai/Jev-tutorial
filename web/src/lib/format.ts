/**
 * Display formatting only. Amounts arrive as Decimal strings (already validated by the
 * guards), and Intl formats a numeric string exactly, with no float round-trip, so the UI
 * shows the figure the backend computed. The UI never does arithmetic on money.
 */
type NumericString = `${number}`;

const LOCALE = 'en-US';
const MONEY = new Intl.NumberFormat(LOCALE, { style: 'currency', currency: 'USD' });
// Run costs are fractions of a cent: three significant digits keep them readable.
const COST = new Intl.NumberFormat(LOCALE, {
  style: 'currency',
  currency: 'USD',
  maximumSignificantDigits: 3,
});
const PERCENT = new Intl.NumberFormat(LOCALE, { style: 'percent', maximumFractionDigits: 0 });
const COUNT = new Intl.NumberFormat(LOCALE);
const SECONDS = new Intl.NumberFormat(LOCALE, {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});
const DATE = new Intl.DateTimeFormat(LOCALE, { dateStyle: 'medium', timeZone: 'UTC' });

const MS_PER_SECOND = 1000;

export function formatMoney(decimal: string): string {
  return MONEY.format(decimal as NumericString);
}

export function formatCost(decimal: string): string {
  return COST.format(decimal as NumericString);
}

/** A probability or confidence in [0, 1] as a whole percentage. */
export function formatPercent(fraction: number): string {
  return PERCENT.format(fraction);
}

export function formatCount(count: number): string {
  return COUNT.format(count);
}

export function formatDuration(ms: number): string {
  return ms < MS_PER_SECOND
    ? `${COUNT.format(Math.round(ms))} ms`
    : `${SECONDS.format(ms / MS_PER_SECOND)} s`;
}

/** An ISO timestamp as a calendar date, or the input unchanged if it can't be read. */
export function formatDate(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : DATE.format(date);
}
