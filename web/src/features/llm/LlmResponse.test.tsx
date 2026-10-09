import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { StepEvent } from '../../api/events';
import { completedView } from '../../test/fixtures/replay';
import type { SideProgress } from '../run/runReducer';
import { LlmResponse } from './LlmResponse';
import { llmState } from './llmProgress';

const step = (data: StepEvent['data']): StepEvent => ({
  seq: 1,
  t_ms: 1,
  type: 'step',
  side: 'llm',
  data,
});
const progress = (steps: StepEvent[]): SideProgress => ({ steps, findings: [], result: null });

beforeEach(() => {
  // Reduced motion: the typed text is complete at once.
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('llmState', () => {
  it('follows the request from idle to waiting to answered', () => {
    expect(llmState(null)).toEqual({ kind: 'idle' });
    expect(llmState(progress([]))).toEqual({ kind: 'idle' });
    expect(llmState(progress([step({ step: 'request_sent', purpose: 's1.llm' })]))).toEqual({
      kind: 'waiting',
    });
    expect(
      llmState(progress([step({ step: 'answers', latency_ms: 900, refusal: 'I cannot help.' })])),
    ).toEqual({ kind: 'answered', latencyMs: 900, problem: 'I cannot help.' });
  });
});

describe('LlmResponse', () => {
  it('renders nothing before the run', () => {
    const { container } = render(<LlmResponse progress={null} />);

    expect(container).toBeEmptyDOMElement();
  });

  it('says it is waiting for one complete response', () => {
    render(
      <LlmResponse progress={progress([step({ step: 'request_sent', purpose: 's1.llm' })])} />,
    );

    expect(screen.getByText(/Waiting for the complete response/)).toBeInTheDocument();
  });

  it('says how long the live response took', () => {
    render(<LlmResponse progress={completedView().sides.llm} mode="live" />);

    expect(screen.getByText(/arrived after/)).toHaveTextContent('34.4 s');
  });

  it('calls the wait the recorded one in a replay', () => {
    render(<LlmResponse progress={completedView().sides.llm} mode="replay" />);

    expect(screen.getByText(/The recorded response took/)).toHaveTextContent('34.4 s');
  });

  it('labels the typed-out text honestly', () => {
    const { container } = render(<LlmResponse progress={completedView().sides.llm} />);

    expect(screen.getByText(/it was not streamed/)).toBeInTheDocument();
    const text = container.querySelector('pre');
    expect(text).toHaveAttribute('aria-hidden', 'true');
    expect(text?.textContent.split('\n')).toHaveLength(18);
    expect(text).toHaveTextContent('inv-2026-02 L4 other billed 340.00');
  });

  it('shows why there was no usable answer', () => {
    render(
      <LlmResponse
        progress={progress([step({ step: 'answers', latency_ms: 50, error: 'Timed out' })])}
      />,
    );

    expect(screen.getByText('No usable answer: Timed out')).toBeInTheDocument();
    expect(screen.queryByText(/not streamed/)).not.toBeInTheDocument();
  });
});
