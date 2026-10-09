import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiRequestError, startRun } from '../../api/client';
import { completedView } from '../../test/fixtures/replay';
import { RunControl } from './RunControl';
import { initialRunView, runReducer } from './runReducer';

vi.mock('../../api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../api/client')>()),
  startRun: vi.fn(),
}));
const startRunMock = vi.mocked(startRun);

afterEach(() => {
  startRunMock.mockReset();
});

describe('RunControl', () => {
  it('starts a paced replay and reports the new run', async () => {
    const user = userEvent.setup();
    startRunMock.mockResolvedValueOnce({ run_id: 'r9' });
    const onStarted = vi.fn();
    render(<RunControl scenarioId="s1_reconciliation" view={null} onStarted={onStarted} />);

    await user.click(screen.getByRole('button', { name: 'Replay recorded run' }));

    expect(startRunMock).toHaveBeenCalledWith({
      scenario_id: 's1_reconciliation',
      mode: 'replay',
      pace: true,
    });
    expect(onStarted).toHaveBeenCalledWith('r9');
  });

  it('cannot start without a scenario or while a run is going', () => {
    const { rerender } = render(<RunControl scenarioId={null} view={null} onStarted={vi.fn()} />);
    expect(screen.getByRole('button')).toBeDisabled();

    const running = runReducer(initialRunView('r1'), {
      type: 'event',
      event: {
        seq: 0,
        t_ms: 0,
        type: 'run_started',
        side: null,
        data: { run_id: 'r1', scenario_id: 's1', mode: 'replay' },
      },
    });
    rerender(<RunControl scenarioId="s1_reconciliation" view={running} onStarted={vi.fn()} />);

    // Still focusable (so a keyboard user keeps their place), but announced as unavailable.
    expect(screen.getByRole('button')).toBeEnabled();
    expect(screen.getByRole('button')).toHaveAttribute('aria-disabled', 'true');
    expect(screen.getByRole('status')).toHaveTextContent('Running');
  });

  it('keeps focus on the button while the run goes, and ignores presses', async () => {
    const user = userEvent.setup();
    let finish: (value: { run_id: string }) => void = () => undefined;
    startRunMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    render(<RunControl scenarioId="s1_reconciliation" view={null} onStarted={vi.fn()} />);
    const button = screen.getByRole('button');

    await user.click(button);
    await user.click(button);

    expect(button).toHaveFocus();
    expect(button).toHaveAttribute('aria-disabled', 'true');
    expect(startRunMock).toHaveBeenCalledTimes(1);
    await act(async () => {
      finish({ run_id: 'r1' });
      await Promise.resolve();
    });
  });

  it('drops a start that resolves after it was unmounted', async () => {
    const user = userEvent.setup();
    let finish: (value: { run_id: string }) => void = () => undefined;
    startRunMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    const onStarted = vi.fn();
    const { unmount } = render(
      <RunControl scenarioId="s1_reconciliation" view={null} onStarted={onStarted} />,
    );

    await user.click(screen.getByRole('button'));
    unmount();
    await act(async () => {
      finish({ run_id: 'late' });
      await Promise.resolve();
    });

    expect(onStarted).not.toHaveBeenCalled();
  });

  it('can replay again once a run is over', () => {
    render(
      <RunControl scenarioId="s1_reconciliation" view={completedView()} onStarted={vi.fn()} />,
    );

    expect(screen.getByRole('button')).toBeEnabled();
    expect(screen.getByRole('status')).toHaveTextContent('Replay complete');
  });

  it('shows why a run could not start', async () => {
    const user = userEvent.setup();
    startRunMock.mockRejectedValueOnce(
      new ApiRequestError(404, 'NO_RECORDING', 'No recordings yet; record a live run first.'),
    );
    render(<RunControl scenarioId="s1_reconciliation" view={null} onStarted={vi.fn()} />);

    await user.click(screen.getByRole('button'));

    expect(screen.getByRole('status')).toHaveTextContent(
      'No recordings yet; record a live run first.',
    );
    expect(screen.getByRole('button')).toBeEnabled();
  });

  it('shows why a run failed', () => {
    const failed = runReducer(initialRunView('r1'), {
      type: 'failed',
      error: { code: 'RUN_FAILED', message: 'The run failed (TimeoutError).' },
    });

    render(<RunControl scenarioId="s1_reconciliation" view={failed} onStarted={vi.fn()} />);

    expect(screen.getByRole('status')).toHaveTextContent('The run failed (TimeoutError).');
  });
});
