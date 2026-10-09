import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiRequestError, getBudget, getRecordings, startRun } from '../../api/client';
import type { BudgetReport, RecordingMeta } from '../../api/types';
import { completedView } from '../../test/fixtures/replay';
import { RunControl } from './RunControl';
import { initialRunView, runReducer, type RunView } from './runReducer';

vi.mock('../../api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../api/client')>()),
  startRun: vi.fn(),
  getRecordings: vi.fn(),
  getBudget: vi.fn(),
}));
const startRunMock = vi.mocked(startRun);
const getRecordingsMock = vi.mocked(getRecordings);
const getBudgetMock = vi.mocked(getBudget);

const SCENARIO = 's1_reconciliation';
const RECORDING: RecordingMeta = {
  id: 'rec-2026-10-09',
  scenario_id: SCENARIO,
  recorded_at: '2026-10-09T18:30:56.830087+00:00',
  jev_model: 'jev-1.13.0',
  llm_model: 'gpt-6-luna',
};
const BUDGET: BudgetReport = {
  ledger_initialised: true,
  providers: [
    {
      provider: 'openai',
      cap: '5.00',
      key_configured: true,
      spent: '0.0042',
      reserved: '0',
      remaining: '4.9958',
    },
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

function renderControl(props: Partial<Parameters<typeof RunControl>[0]> = {}) {
  const onStarted = vi.fn();
  const utils = render(
    <RunControl
      scenarioId={SCENARIO}
      isLiveEnabled={false}
      view={null}
      onStarted={onStarted}
      {...props}
    />,
  );
  return { ...utils, onStarted };
}

function deferredStart() {
  let finish: (value: { run_id: string }) => void = () => undefined;
  startRunMock.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  return (value: { run_id: string }) => {
    finish(value);
  };
}

const replayButton = () => screen.getByRole('button', { name: 'Replay recorded run' });
/** Replay is offered once the recording it will show is known. */
const readyToReplay = () => screen.findByText('Recorded');

beforeEach(() => {
  getRecordingsMock.mockResolvedValue([RECORDING]);
  getBudgetMock.mockResolvedValue(BUDGET);
});

afterEach(() => {
  // Unmount before resetting mocks: a load still in flight must not call a reset mock.
  cleanup();
  vi.resetAllMocks();
});

describe('RunControl: replay', () => {
  it('says which recording a replay shows, then replays exactly that one', async () => {
    const user = userEvent.setup();
    startRunMock.mockResolvedValueOnce({ run_id: 'r9' });
    const { onStarted } = renderControl();

    expect(await screen.findByText('Recorded')).toBeInTheDocument();
    expect(screen.getByText('Recorded').parentElement).toHaveTextContent(
      'Recorded Oct 9, 2026 · jev-1.13.0 vs gpt-6-luna',
    );
    await user.click(replayButton());

    expect(startRunMock).toHaveBeenCalledWith({
      scenario_id: SCENARIO,
      mode: 'replay',
      pace: true,
      recording_id: RECORDING.id,
    });
    expect(onStarted).toHaveBeenCalledWith('r9');
  });

  it('waits for the recording list, and can try it again after a failure', async () => {
    const user = userEvent.setup();
    getRecordingsMock.mockRejectedValueOnce(
      new ApiRequestError(500, 'RECORDING_INVALID', 'A recording could not be read.'),
    );
    renderControl();
    expect(replayButton()).toBeDisabled();

    expect(
      await screen.findByText(/Recordings unavailable: A recording could not be read\./),
    ).toBeInTheDocument();
    expect(replayButton()).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Try again' }));

    await readyToReplay();
    expect(replayButton()).toBeEnabled();
    expect(getRecordingsMock).toHaveBeenCalledTimes(2);
  });

  it('cannot replay when there are no recordings', async () => {
    getRecordingsMock.mockResolvedValueOnce([]);
    renderControl();

    expect(
      await screen.findByText('No recordings yet. Record a live run first.'),
    ).toBeInTheDocument();
    expect(replayButton()).toBeDisabled();
  });

  it('cannot start without a scenario or while a run is going', async () => {
    const { rerender } = renderControl({ scenarioId: null });
    expect(replayButton()).toBeDisabled();

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
    rerender(
      <RunControl scenarioId={SCENARIO} isLiveEnabled={false} view={running} onStarted={vi.fn()} />,
    );
    await readyToReplay();

    // Still focusable (so a keyboard user keeps their place), but announced as unavailable.
    expect(replayButton()).toBeEnabled();
    expect(replayButton()).toHaveAttribute('aria-disabled', 'true');
    expect(screen.getByRole('status')).toHaveTextContent('Running');
    // The mode can't change under a run that is going.
    expect(screen.getByRole('radio', { name: 'Live' })).toBeDisabled();
  });

  it('keeps focus on the button while the run starts, and ignores presses', async () => {
    const user = userEvent.setup();
    const finish = deferredStart();
    renderControl();
    await readyToReplay();
    const button = replayButton();

    await user.click(button);
    await user.click(button);

    expect(button).toHaveFocus();
    expect(button).toHaveAttribute('aria-disabled', 'true');
    expect(screen.getByRole('status')).toHaveTextContent('Starting the replay…');
    expect(startRunMock).toHaveBeenCalledTimes(1);
    await act(async () => {
      finish({ run_id: 'r1' });
      await Promise.resolve();
    });
  });

  it('drops a start that resolves after it was unmounted', async () => {
    const user = userEvent.setup();
    const finish = deferredStart();
    const { unmount, onStarted } = renderControl();
    await readyToReplay();

    await user.click(replayButton());
    unmount();
    await act(async () => {
      finish({ run_id: 'late' });
      await Promise.resolve();
    });

    expect(onStarted).not.toHaveBeenCalled();
  });

  it('can replay again once a run is over', async () => {
    renderControl({ view: completedView() });
    await readyToReplay();

    expect(replayButton()).toBeEnabled();
    expect(screen.getByRole('status')).toHaveTextContent('Replay complete');
  });

  it('shows why a run could not start, and what to do about it', async () => {
    const user = userEvent.setup();
    startRunMock.mockRejectedValueOnce(
      new ApiRequestError(404, 'NO_RECORDING', 'No recordings yet; record a live run first.'),
    );
    renderControl();
    await readyToReplay();

    await user.click(replayButton());

    expect(screen.getByRole('alert')).toHaveTextContent(
      'No recordings yet; record a live run first. Record a live run from the command line first.',
    );
    expect(replayButton()).toBeEnabled();
  });

  it('falls back to a plain message for an unexpected failure', async () => {
    const user = userEvent.setup();
    startRunMock.mockRejectedValueOnce(new Error('internals'));
    renderControl();
    await readyToReplay();

    await user.click(replayButton());

    expect(screen.getByRole('alert')).toHaveTextContent('The run could not be started.');
    expect(screen.getByRole('alert')).not.toHaveTextContent('internals');
  });

  it('says the run stopped (the workspace says why)', () => {
    const failed = runReducer(initialRunView('r1'), {
      type: 'failed',
      error: { code: 'RUN_FAILED', message: 'The run failed (TimeoutError).' },
    });

    renderControl({ view: failed });

    expect(screen.getByRole('status')).toHaveTextContent('Run stopped');
  });
});

describe('RunControl: live', () => {
  it('explains that live is off, and shows the budget anyway', async () => {
    const user = userEvent.setup();
    renderControl({ isLiveEnabled: false });

    await user.click(screen.getByRole('radio', { name: 'Live' }));

    expect(screen.getByRole('button', { name: 'Run live' })).toBeDisabled();
    expect(screen.getByText(/Live calls are turned off on this server/)).toBeInTheDocument();
    expect(await screen.findByRole('region', { name: 'Live budget' })).toBeInTheDocument();
    expect(startRunMock).not.toHaveBeenCalled();
  });

  it('asks for a second press before spending, and Escape or Cancel backs out', async () => {
    const user = userEvent.setup();
    renderControl({ isLiveEnabled: true });
    await user.click(screen.getByRole('radio', { name: 'Live' }));

    await user.click(screen.getByRole('button', { name: 'Run live' }));
    expect(screen.getByRole('status')).toHaveTextContent('spends from the budget');
    expect(screen.getByRole('button', { name: 'Confirm live run' })).toHaveFocus();
    await user.keyboard('{Escape}');
    expect(screen.getByRole('button', { name: 'Run live' })).toHaveFocus();

    await user.click(screen.getByRole('button', { name: 'Run live' }));
    await user.tab();
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus();
    await user.keyboard('{Enter}');
    // The Cancel button goes away; focus returns to the run button, not the page.
    expect(screen.getByRole('button', { name: 'Run live' })).toHaveFocus();
    expect(startRunMock).not.toHaveBeenCalled();
  });

  it('disarms the confirmation once focus leaves the control', async () => {
    const user = userEvent.setup();
    render(
      <>
        <RunControl scenarioId={SCENARIO} isLiveEnabled view={null} onStarted={vi.fn()} />
        <button type="button">Elsewhere</button>
      </>,
    );
    await user.click(screen.getByRole('radio', { name: 'Live' }));
    await user.click(screen.getByRole('button', { name: 'Run live' }));

    await user.click(screen.getByRole('button', { name: 'Elsewhere' }));
    await user.click(screen.getByRole('button', { name: 'Run live' }));

    expect(startRunMock).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Confirm live run' })).toBeInTheDocument();
  });

  it('starts a live run on the confirming press', async () => {
    const user = userEvent.setup();
    startRunMock.mockResolvedValueOnce({ run_id: 'live1' });
    const { onStarted } = renderControl({ isLiveEnabled: true });
    await user.click(screen.getByRole('radio', { name: 'Live' }));

    await user.click(screen.getByRole('button', { name: 'Run live' }));
    await user.click(screen.getByRole('button', { name: 'Confirm live run' }));

    expect(startRunMock).toHaveBeenCalledWith({
      scenario_id: SCENARIO,
      mode: 'live',
      pace: true,
      recording_id: null,
    });
    expect(onStarted).toHaveBeenCalledWith('live1');
  });

  it('shows a refusal with its next step, e.g. the cap is reached', async () => {
    const user = userEvent.setup();
    startRunMock.mockRejectedValueOnce(
      new ApiRequestError(409, 'BUDGET_EXCEEDED', 'The openai key has reached its $5.00 cap.'),
    );
    renderControl({ isLiveEnabled: true });
    await user.click(screen.getByRole('radio', { name: 'Live' }));

    await user.click(screen.getByRole('button', { name: 'Run live' }));
    await user.click(screen.getByRole('button', { name: 'Confirm live run' }));

    expect(screen.getByRole('alert')).toHaveTextContent(
      'The openai key has reached its $5.00 cap. The spending cap is reached. Replays still work.',
    );
  });

  it('re-reads the budget once a live run has finished', async () => {
    const user = userEvent.setup();
    const { rerender } = renderControl({ isLiveEnabled: true });
    await user.click(screen.getByRole('radio', { name: 'Live' }));
    await screen.findByRole('region', { name: 'Live budget' });
    expect(getBudgetMock).toHaveBeenCalledTimes(1);

    const finished: RunView = { ...completedView('live1'), mode: 'live' };
    rerender(
      <RunControl scenarioId={SCENARIO} isLiveEnabled view={finished} onStarted={vi.fn()} />,
    );

    // The last figures stay up while the new ones load.
    expect(screen.getByRole('region', { name: 'Live budget' })).toBeInTheDocument();
    await waitFor(() => {
      expect(getBudgetMock).toHaveBeenCalledTimes(2);
    });
    expect(screen.getByRole('status')).toHaveTextContent('Run complete');
  });

  it('says when the budget cannot be read', async () => {
    const user = userEvent.setup();
    getBudgetMock.mockRejectedValueOnce(
      new ApiRequestError(0, 'NETWORK', 'Could not reach the API. Is the server running?'),
    );
    renderControl({ isLiveEnabled: true });

    await user.click(screen.getByRole('radio', { name: 'Live' }));

    expect(
      await screen.findByText(
        'Budget unavailable: Could not reach the API. Is the server running?',
      ),
    ).toBeInTheDocument();
  });

  it('switching back to replay drops a pending confirmation', async () => {
    const user = userEvent.setup();
    renderControl({ isLiveEnabled: true });
    await user.click(screen.getByRole('radio', { name: 'Live' }));
    await user.click(screen.getByRole('button', { name: 'Run live' }));

    await user.click(screen.getByRole('radio', { name: 'Replay' }));

    expect(replayButton()).toBeInTheDocument();
    expect(within(screen.getByRole('status')).queryByText(/spends/)).toBeNull();
  });
});
