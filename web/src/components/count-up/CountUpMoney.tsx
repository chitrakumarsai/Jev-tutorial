import { useCountUp } from '../../hooks/useCountUp';
import { formatMoney } from '../../lib/format';

type Props = {
  /** A Decimal string from the API. */
  value: string;
  className?: string;
};

/**
 * A money figure that counts up on screen. The moving figure is hidden from assistive tech
 * (and is approximate mid-flight); the exact figure sits beside it for screen readers.
 */
export function CountUpMoney({ value, className }: Props) {
  const shown = useCountUp(value);
  return (
    <data className={className} value={value}>
      <span aria-hidden="true">{shown}</span>
      <span className="visually-hidden">{formatMoney(value)}</span>
    </data>
  );
}
