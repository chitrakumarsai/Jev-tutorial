import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { getConsistency } from '../../api/client';
import type { ConsistencyReport } from '../../api/types';
import { ConsistencyPanel } from './ConsistencyPanel';

vi.mock('../../api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../api/client')>()),
  getConsistency: vi.fn(),
}));
const getConsistencyMock = vi.mocked(getConsistency);

const run = (id: string, at: string) => ({
  id,
  scenario_id: 's3_citation_check',
  recorded_at: at,
  jev_model: 'jev-1.13.0',
  llm_model: 'gpt-6-luna',
});
const item = (label: string, answers: string[], changed: boolean) => ({
  key_id: `K-${label}`,
  label,
  answers,
  statuses: answers.map(() => 'correct' as const),
  changed,
});
const REPORT: ConsistencyReport = {
  scenario_id: 's3_citation_check',
  recordings: [
    run('a', '2026-10-12T03:21:21Z'),
    run('b', '2026-10-12T03:21:27Z'),
    run('c', '2026-10-12T03:21:36Z'),
  ],
  sides: {
    jev: {
      changed: 0,
      items: [item('C5', ['verified', 'verified', 'verified'], false)],
    },
    llm: {
      changed: 1,
      items: [item('C5', ['unsupported', 'verified', 'unsupported'], true)],
    },
  },
};

describe('ConsistencyPanel', () => {
  beforeEach(() => {
    getConsistencyMock.mockReset();
  });

  it('loads nothing until asked, then shows each side across the recorded runs', async () => {
    const user = userEvent.setup();
    getConsistencyMock.mockResolvedValue(REPORT);
    render(<ConsistencyPanel scenarioId="s3_citation_check" />);

    expect(getConsistencyMock).not.toHaveBeenCalled();
    await user.click(screen.getByRole('button', { name: 'Consistency ×3' }));

    const jev = await screen.findByRole('table', { name: /Jev \+ code/ });
    expect(jev).toHaveAccessibleName(/same answer on all 1 items in 3 runs/);
    const llm = screen.getByRole('table', { name: /Plain LLM/ });
    expect(llm).toHaveAccessibleName(/1 item changed/);
    const c5 = within(llm).getByRole('row', { name: /C5/ });
    expect(c5).toHaveTextContent('changed');
    expect(
      within(c5)
        .getAllByRole('cell')
        .map((c) => c.textContent),
    ).toContain('unsupported');
    expect(screen.getByRole('button', { name: 'Consistency ×3' })).toHaveAttribute(
      'aria-expanded',
      'true',
    );
  });

  it('says why when the runs cannot be loaded', async () => {
    const user = userEvent.setup();
    getConsistencyMock.mockRejectedValue(new Error('down'));
    render(<ConsistencyPanel scenarioId="s3_citation_check" />);

    await user.click(screen.getByRole('button', { name: 'Consistency ×3' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not be loaded/);
  });
});
