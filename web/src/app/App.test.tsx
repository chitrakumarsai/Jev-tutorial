import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiRequestError, getDocuments, getScenario, getScenarios, startRun } from '../api/client';
import { FakeEventSource } from '../test/fakeEventSource';
import { replayDocuments, replayFrames } from '../test/fixtures/replay';
import { App } from './App';

vi.mock('../api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api/client')>()),
  getScenarios: vi.fn(),
  getScenario: vi.fn(),
  getDocuments: vi.fn(),
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
  vi.mocked(startRun).mockResolvedValue({ run_id: 'r1' });
});

afterEach(() => {
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
    await user.click(screen.getByRole('button', { name: 'Replay recorded run' }));
    expect(FakeEventSource.instances[0]?.url).toBe('/api/runs/r1/events');
    act(() => {
      for (const frame of replayFrames) FakeEventSource.instances[0]?.send(frame.type, frame.data);
    });

    expect(screen.getByRole('status')).toHaveTextContent('Replay complete');
    expect(screen.getByRole('region', { name: 'Jev + code' })).toHaveTextContent('14 findings');
    expect(screen.getByRole('region', { name: 'Plain LLM' })).toHaveTextContent('18 findings');
    expect(screen.getByRole('tabpanel').querySelectorAll('mark').length).toBeGreaterThan(0);
  });

  it('forgets a run when another scenario is picked, even on coming back', async () => {
    const user = userEvent.setup();
    const OTHER = { id: 's2_other', title: 'Another scenario', description: '…' };
    vi.mocked(getScenarios).mockResolvedValue([SCENARIO, OTHER]);
    render(<App />);
    await screen.findByRole('heading', { level: 2, name: SCENARIO.title });
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
});
