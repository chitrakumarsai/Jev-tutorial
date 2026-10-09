import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import type { StepEvent } from '../../api/events';
import { completedView } from '../../test/fixtures/replay';
import { JevPipeline } from './JevPipeline';

const step = (data: StepEvent['data']): StepEvent => ({
  seq: 1,
  t_ms: 1,
  type: 'step',
  side: 'jev',
  data,
});

describe('JevPipeline', () => {
  it('renders nothing before a run', () => {
    const { container } = render(<JevPipeline progress={null} />);

    expect(container).toBeEmptyDOMElement();
  });

  it('shows a waiting chip for a request that has not come back', () => {
    render(
      <JevPipeline
        progress={{
          steps: [
            step({ step: 'candidates', requests: 2, questions: 7 }),
            step({ step: 'request_sent', purpose: 's1.contract', questions: 4 }),
          ],
          findings: [],
          result: null,
        }}
      />,
    );

    const items = within(screen.getByRole('list', { name: 'Pipeline stages' })).getAllByRole(
      'listitem',
    );
    expect(items[0]).toHaveTextContent('Find candidates: Done.7 typed questions in 2 requests');
    expect(items[1]).toHaveTextContent('In progress');
    const chip = screen.getByRole('button', { name: /Master services agreement/ });
    expect(chip).toHaveAccessibleName('Master services agreement 4 questions, waiting');
    expect(chip).toHaveAttribute('aria-disabled', 'true');
    expect(screen.queryByRole('region')).not.toBeInTheDocument();
  });

  it('keeps showing the first request to come back when an earlier one answers later', () => {
    const answers = (purpose: string) =>
      step({
        step: 'answers',
        purpose,
        latency_ms: 100,
        choices: { invoice_date: ['31 May 2026', 0.99] },
        nouls: { dup_L4_L5: 0.02 },
      });
    render(
      <JevPipeline
        progress={{
          steps: [
            step({ step: 'candidates', requests: 2, questions: 2 }),
            step({ step: 'request_sent', purpose: 's1.contract', questions: 1 }),
            step({ step: 'request_sent', purpose: 's1.invoice.inv-2026-05', questions: 1 }),
            answers('s1.invoice.inv-2026-05'),
            answers('s1.contract'),
          ],
          findings: [],
          result: null,
        }}
      />,
    );

    const card = screen.getByRole('region', { name: /Invoice INV-2026-05/ });
    // A confident "no" (P(yes) 2%) is 98% confidence, not 2%.
    expect(within(card).getByText('98%')).toHaveTextContent('Lowest confidence 98%');
  });

  it('shows the agreement answers first, with probabilities, then any request picked', async () => {
    const user = userEvent.setup();
    render(<JevPipeline progress={completedView().sides.jev} />);

    const contract = screen.getByRole('region', { name: /Master services agreement/ });
    expect(contract).toHaveTextContent('13 typed answers');
    expect(within(contract).getAllByText('70%')[0]).toHaveTextContent('Lowest confidence 70%');
    expect(within(contract).getByText('Late-fee grace days')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Master services agreement/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    );

    await user.click(screen.getByRole('button', { name: /Invoice INV-2026-10/ }));

    const october = screen.getByRole('region', { name: /Invoice INV-2026-10/ });
    expect(within(october).getByText('L5 duplicates L4?')).toBeInTheDocument();
    expect(within(october).getByText('yes')).toBeInTheDocument();
    expect(october).toHaveTextContent('Probability of yes 90%');
  });
});
