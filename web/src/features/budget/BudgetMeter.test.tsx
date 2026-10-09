import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { BudgetReport } from '../../api/types';
import { BudgetMeter } from './BudgetMeter';

type Row = BudgetReport['providers'][number];

const OPENAI: Row = {
  provider: 'openai',
  cap: '5.00',
  key_configured: true,
  spent: '1.25',
  reserved: '0',
  remaining: '3.75',
};
const REPORT: BudgetReport = {
  ledger_initialised: true,
  providers: [
    OPENAI,
    {
      provider: 'typesafe',
      cap: '5.00',
      key_configured: false,
      spent: null,
      reserved: null,
      remaining: null,
    },
  ],
};

describe('BudgetMeter', () => {
  it("shows each key's spend against its cap, as the backend's exact figures", () => {
    render(<BudgetMeter report={REPORT} />);

    const region = screen.getByRole('region', { name: 'Live budget' });
    const meter = within(region).getByRole('meter', { name: 'OpenAI (plain LLM)' });
    expect(meter).toHaveAttribute('value', '1.25');
    expect(meter).toHaveAttribute('max', '5.00');
    expect(meter).toHaveAccessibleDescription('$1.25 of $5.00 spent · $3.75 left');
  });

  it('says when a key is not set, without a meter', () => {
    render(<BudgetMeter report={REPORT} />);

    expect(screen.getByText('No key set on the server')).toBeInTheDocument();
    expect(screen.getAllByRole('meter')).toHaveLength(1);
  });

  it('warns that live runs are refused without a ledger', () => {
    render(<BudgetMeter report={{ ...REPORT, ledger_initialised: false }} />);

    expect(screen.getByText(/no spend ledger yet/)).toBeInTheDocument();
    expect(screen.getByText('No spend recorded')).toBeInTheDocument();
    expect(screen.queryByRole('meter')).toBeNull();
  });

  it('names an unknown provider as given', () => {
    render(
      <BudgetMeter
        report={{
          ledger_initialised: true,
          providers: [{ ...OPENAI, provider: 'other' }],
        }}
      />,
    );

    expect(screen.getByText('other')).toBeInTheDocument();
  });
});
