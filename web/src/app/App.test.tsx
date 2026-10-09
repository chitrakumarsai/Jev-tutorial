import { act, cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  ApiRequestError,
  getBudget,
  getDocuments,
  getRecordings,
  getScenario,
  getScenarios,
  startRun,
} from '../api/client';
import { FakeEventSource } from '../test/fakeEventSource';
import { replayDocuments, replayFrames } from '../test/fixtures/replay';
import { App } from './App';

vi.mock('../api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api/client')>()),
  getScenarios: vi.fn(),
  getScenario: vi.fn(),
  getDocuments: vi.fn(),
  getRecordings: vi.fn(),
  getBudget: vi.fn(),
  startRun: vi.fn(),
}));

const SCENARIO = {
  id: 's1_reconciliation',
  title: 'Contract-to-invoice reconciliation',
  description: 'Check 12 monthly freight invoices against the Northwind Logistics agreement.',
};

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal('EventSource', FakeEventSource);
  vi.mocked(getScenarios).mockResolvedValue([SCENARIO]);
  vi.mocked(getScenario).mockResolvedValue({
    ...SCENARIO,
    llm_prompt: 'You are auditing freight invoices…',
    models: { jev: 'jev-latest', llm: 'gpt-6-luna' },
    live_enabled: false,
  });
  vi.mocked(getDocuments).mockResolvedValue(replayDocuments);
  vi.mocked(getRecordings).mockResolvedValue([
    {
      id: 'rec1',
      scenario_id: SCENARIO.id,
      recorded_at: '2026-10-09T18:30:56.830087+00:00',
      jev_model: 'jev-1.13.0',
      llm_model: 'gpt-6-luna',
    },
  ]);
  vi.mocked(getBudget).mockResolvedValue({ ledger_initialised: false, providers: [] });
  vi.mocked(startRun).mockResolvedValue({ run_id: 'r1' });
});

afterEach(() => {
  // Unmount before resetting mocks: a load still in flight must not call a reset mock.
  cleanup();
  vi.unstubAllGlobals();
  vi.resetAllMocks();
});

describe('App', () => {
  it('renders the product name as the main heading inside a banner', () => {
    render(<App />);

    expect(screen.getByRole('banner')).toContainElement(
      screen.getByRole('heading', { level: 1, name: 'Jev Audit Lens' }),
    );
  });

  it('offers the theme choice in the masthead', () => {
    render(<App />);

    expect(screen.getByRole('banner')).toContainElement(
      screen.getByRole('radiogroup', { name: 'Theme' }),
    );
  });

  it('loads the scenario: picker, documents and both panes', async () => {
    render(<App />);

    // Wait for the scenario itself (the picker appears as soon as the catalog loads).
    expect(
      await screen.findByRole('heading', { level: 2, name: SCENARIO.title }),
    ).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Scenario' })).toHaveValue(SCENARIO.id);
    const main = screen.getByRole('main');
    expect(within(main).getByRole('region', { name: 'Source documents' })).toBeInTheDocument();
    expect(within(main).getByRole('region', { name: 'Plain LLM' })).toHaveTextContent('gpt-6-luna');
    expect(within(main).getByRole('region', { name: 'Jev + code' })).toHaveTextContent(
      'jev-latest',
    );
    expect(getScenario).toHaveBeenCalledWith(SCENARIO.id, {
      signal: expect.any(AbortSignal) as AbortSignal,
    });
  });

  it('shows the exact LLM prompt, for fairness', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByText('Exact prompt sent to the LLM'));

    expect(screen.getByText('You are auditing freight invoices…')).toBeVisible();
  });

  it('plays a replay into the panes and marks the quoted evidence', async () => {
    const user = userEvent.setup();
    render(<App />);

    await screen.findByRole('heading', { level: 2, name: SCENARIO.title });
    await within(screen.getByRole('banner')).findByText('Recorded');
    await user.click(screen.getByRole('button', { name: 'Replay recorded run' }));
    expect(FakeEventSource.instances[0]?.url).toBe('/api/runs/r1/events');
    act(() => {
      for (const frame of replayFrames) FakeEventSource.instances[0]?.send(frame.type, frame.data);
    });

    expect(within(screen.getByRole('banner')).getByRole('status')).toHaveTextContent(
      'Replay complete',
    );
    expect(screen.getByRole('region', { name: 'Jev + code' })).toHaveTextContent('14 findings');
    expect(screen.getByRole('region', { name: 'Plain LLM' })).toHaveTextContent('18 findings');
    expect(screen.getByRole('tabpanel').querySelectorAll('mark').length).toBeGreaterThan(0);
  });

  it('ends a replay with both ledgers, the review lane and the results', async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole('heading', { level: 2, name: SCENARIO.title });
    await within(screen.getByRole('banner')).findByText('Recorded');
    await user.click(screen.getByRole('button', { name: 'Replay recorded run' }));
    act(() => {
      for (const frame of replayFrames) FakeEventSource.instances[0]?.send(frame.type, frame.data);
    });

    const llm = screen.getByRole('region', { name: 'Plain LLM' });
    const jev = screen.getByRole('region', { name: 'Jev + code' });
    expect(within(llm).getAllByText('Not in the answer key')).toHaveLength(4);
    expect(within(jev).getAllByText(/^Matches K\d\d$/)).toHaveLength(14);
    expect(within(jev).getByRole('region', { name: 'Review lane' })).toHaveTextContent(
      'Nothing needed review',
    );
    const results = screen.getByRole('region', { name: 'Results' });
    const scorecard = within(results).getByRole('table', {
      name: 'Scorecard against the answer key',
    });
    const falsePositives = within(scorecard).getByRole('row', { name: /False positives/ });
    expect(
      within(falsePositives)
        .getAllByRole('cell')
        .map((c) => c.textContent),
    ).toEqual(['✕4', '✓0']);
    expect(within(results).getByRole('table', { name: 'Cost and latency' })).toHaveTextContent(
      'jev-1.13.0, recorded Oct 9, 2026',
    );
  });

  it('traces a ledger figure back to its passage', async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole('heading', { level: 2, name: SCENARIO.title });
    await within(screen.getByRole('banner')).findByText('Recorded');
    await user.click(screen.getByRole('button', { name: 'Replay recorded run' }));
    act(() => {
      for (const frame of replayFrames) FakeEventSource.instances[0]?.send(frame.type, frame.data);
    });

    const jev = screen.getByRole('region', { name: 'Jev + code' });
    await user.click(
      within(jev).getByRole('button', { name: '$57,530.00, show in Invoice INV-2026-04' }),
    );

    expect(screen.getByRole('tab', { name: /Invoice INV-2026-04/ })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    const focused = screen.getByRole('tabpanel').querySelector('mark.quote--focused');
    expect(focused).toHaveTextContent('Fuel surcharge (22.0% of line-haul)');
    expect(within(screen.getByRole('main')).getAllByRole('status').at(-1)).toHaveTextContent(
      'Showing the passage in Invoice INV-2026-04: “| L3 | Fuel surcharge',
    );

    // Picking a tab by hand ends the trace: no outline, no stale announcement.
    await user.click(screen.getByRole('tab', { name: /Master services agreement/ }));
    await user.click(screen.getByRole('tab', { name: /Invoice INV-2026-04/ }));
    expect(screen.getByRole('tabpanel').querySelector('mark.quote--focused')).toBeNull();
    expect(within(screen.getByRole('main')).getAllByRole('status').at(-1)).toBeEmptyDOMElement();
  });

  it('forgets a run when another scenario is picked, even on coming back', async () => {
    const user = userEvent.setup();
    const OTHER = { id: 's2_other', title: 'Another scenario', description: '…' };
    vi.mocked(getScenarios).mockResolvedValue([SCENARIO, OTHER]);
    render(<App />);
    await screen.findByRole('heading', { level: 2, name: SCENARIO.title });
    await within(screen.getByRole('banner')).findByText('Recorded');
    await user.click(screen.getByRole('button', { name: 'Replay recorded run' }));
    expect(FakeEventSource.instances).toHaveLength(1);

    const picker = screen.getByRole('combobox', { name: 'Scenario' });
    await user.selectOptions(picker, OTHER.id);
    await user.selectOptions(picker, SCENARIO.id);
    await screen.findByRole('heading', { level: 2, name: SCENARIO.title });

    expect(FakeEventSource.instances).toHaveLength(1);
    expect(FakeEventSource.instances[0]?.readyState).toBe(FakeEventSource.CLOSED);
    expect(screen.getByRole('region', { name: 'Jev + code' })).toHaveTextContent('Not run yet');
  });

  it('announces that the scenario is loading', () => {
    render(<App />);

    expect(within(screen.getByRole('main')).getByRole('status')).toHaveTextContent(
      'Loading the scenario…',
    );
  });

  it('says so when there are no scenarios', async () => {
    vi.mocked(getScenarios).mockResolvedValue([]);
    render(<App />);

    expect(await screen.findByRole('alert')).toHaveTextContent('No scenarios are available.');
  });

  it('says so when the scenario cannot be loaded', async () => {
    vi.mocked(getScenarios).mockRejectedValue(
      new ApiRequestError(0, 'NETWORK', 'Could not reach the API. Is the server running?'),
    );
    render(<App />);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Could not reach the API. Is the server running?',
    );
  });

  it('tries again after a failed load, keeping nothing stale', async () => {
    const user = userEvent.setup();
    vi.mocked(getScenarios)
      .mockRejectedValueOnce(
        new ApiRequestError(0, 'NETWORK', 'Could not reach the API. Is the server running?'),
      )
      .mockResolvedValueOnce([SCENARIO]);
    render(<App />);

    await user.click(await screen.findByRole('button', { name: 'Try again' }));

    expect(
      await screen.findByRole('heading', { level: 2, name: SCENARIO.title }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('says why a run stopped, keeping what arrived before it', async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole('heading', { level: 2, name: SCENARIO.title });
    await within(screen.getByRole('banner')).findByText('Recorded');
    await user.click(screen.getByRole('button', { name: 'Replay recorded run' }));
    const started = replayFrames.find((frame) => frame.type === 'run_started');
    act(() => {
      if (started) FakeEventSource.instances[0]?.send(started.type, started.data);
      FakeEventSource.instances[0]?.send(
        'run_failed',
        JSON.stringify({
          seq: 999,
          t_ms: 1,
          type: 'run_failed',
          side: null,
          data: { code: 'RUN_FAILED', message: 'The run failed (TimeoutError).' },
        }),
      );
    });

    expect(screen.getByRole('alert')).toHaveTextContent(
      'The run stopped. The run failed (TimeoutError).',
    );
    expect(within(screen.getByRole('banner')).getByRole('status')).toHaveTextContent('Run stopped');
    expect(screen.queryByRole('region', { name: 'Results' })).toBeNull();
  });

  it('labels a replay with the recording it shows', async () => {
    render(<App />);

    expect(await within(screen.getByRole('banner')).findByText('Recorded')).toBeInTheDocument();
    expect(within(screen.getByRole('banner')).getByText('Oct 9, 2026')).toBeInTheDocument();
  });

  it('retries only the load that failed, and keeps focus in the workspace', async () => {
    const user = userEvent.setup();
    vi.mocked(getScenario)
      .mockRejectedValueOnce(new ApiRequestError(500, 'INTERNAL_ERROR', 'Something went wrong.'))
      .mockResolvedValueOnce({
        ...SCENARIO,
        llm_prompt: 'You are auditing freight invoices…',
        models: { jev: 'jev-latest', llm: 'gpt-6-luna' },
        live_enabled: false,
      });
    render(<App />);

    await user.click(await screen.findByRole('button', { name: 'Try again' }));

    expect(screen.getByRole('main')).toHaveFocus();
    expect(
      await screen.findByRole('heading', { level: 2, name: SCENARIO.title }),
    ).toBeInTheDocument();
    expect(getScenarios).toHaveBeenCalledTimes(1);
    expect(getScenario).toHaveBeenCalledTimes(2);
  });
});
