import { useId } from 'react';

import type { ScenarioSummary } from '../../api/types';

type Props = {
  scenarios: readonly ScenarioSummary[];
  value: string;
  onChange: (scenarioId: string) => void;
};

export function ScenarioPicker({ scenarios, value, onChange }: Props) {
  const id = useId();
  return (
    <div className="scenario-picker">
      <label htmlFor={id} className="eyebrow">
        Scenario
      </label>
      <select
        id={id}
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
        }}
      >
        {scenarios.map((scenario) => (
          <option key={scenario.id} value={scenario.id}>
            {scenario.title}
          </option>
        ))}
      </select>
    </div>
  );
}
