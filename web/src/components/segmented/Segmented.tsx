import { useId } from 'react';

import './segmented.css';

type Props<T extends string> = {
  /** Read by assistive tech as the group's name; hidden on screen. */
  label: string;
  options: readonly T[];
  labels: Readonly<Record<T, string>>;
  value: T;
  /** While true the choice can't change (e.g. mid-run); the current one stays visible. */
  isDisabled?: boolean;
  onChange: (value: T) => void;
};

/** A single choice as pills. Native radios give arrow-key movement and form semantics for free. */
export function Segmented<T extends string>({
  label,
  options,
  labels,
  value,
  isDisabled = false,
  onChange,
}: Props<T>) {
  const name = useId();
  const labelId = `${name}-label`;

  return (
    <div className="segmented" role="radiogroup" aria-labelledby={labelId}>
      <span id={labelId} className="visually-hidden">
        {label}
      </span>
      {options.map((option) => (
        <label key={option} className="segmented__option">
          <input
            type="radio"
            name={name}
            value={option}
            checked={value === option}
            disabled={isDisabled}
            onChange={() => {
              onChange(option);
            }}
          />
          <span>{labels[option]}</span>
        </label>
      ))}
    </div>
  );
}
