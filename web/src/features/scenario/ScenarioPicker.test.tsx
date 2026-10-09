import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ScenarioPicker } from './ScenarioPicker';

const scenarios = [
  { id: 's1_reconciliation', title: 'Contract-to-invoice reconciliation', description: '…' },
  { id: 's2_other', title: 'Another scenario', description: '…' },
];

describe('ScenarioPicker', () => {
  it('is a labelled select of the scenarios', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<ScenarioPicker scenarios={scenarios} value="s1_reconciliation" onChange={onChange} />);

    const select = screen.getByRole('combobox', { name: 'Scenario' });
    expect(select).toHaveValue('s1_reconciliation');

    await user.selectOptions(select, 's2_other');

    expect(onChange).toHaveBeenCalledWith('s2_other');
  });
});
