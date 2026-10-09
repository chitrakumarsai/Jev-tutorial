import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiRequestError, getRun } from '../../api/client';
import type { RunStatus } from '../../api/types';
import { lastReplayEvent, replayFrames } from '../../test/fixtures/replay';
import { MAX_STATUS_FAILURES, STATUS_POLL_MS, useRunEvents } from './useRunEvents';

vi.mock('../../api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../api/client')>()),
  getRun: vi.fn(),
}));
const getRunMock = vi.mocked(getRun);

/** Enough of EventSource to drive the hook: named events, readyState and onerror. */
class FakeEventSource {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  static instances: FakeEventSource[] = [];

  readyState = FakeEventSource.CONNECTING;
  onerror: ((event: Event) => void) | null = null;
  private readonly listeners = new Map<string, ((event: MessageEvent<string>) => void)[]>();

  constructor(readonly url: string) {
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (event: MessageEvent<string>) => void): void {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  close(): void {
    this.readyState = FakeEventSource.CLOSED;
  }

  send(type: string, data: string): void {
    this.readyState = FakeEventSource.OPEN;
    for (const listener of this.listeners.get(type) ?? []) {
      listener(new MessageEvent(type, { data }));
    }
  }

  fail(readyState: number): void {
    this.readyState = readyState;
    this.onerror?.(new Event('error'));
  }
}

function source(index = 0): FakeEventSource {
  const found = FakeEventSource.instances[index];
  if (!found) throw new Error(`no EventSource #${String(index)}`);
  return found;
}

const result = (lastReplayEvent().data as { result: RunStatus['result'] }).result;
const status = (patch: Partial<RunStatus>): RunStatus => ({
  run_id: 'r1',
  mode: 'replay',
  status: 'completed',
  error: null,
  result,
  ...patch,
});

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal('EventSource', FakeEventSource);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  getRunMock.mockReset();
});

describe('useRunEvents', () => {
  it('does nothing without a run', () => {
    const { result: view } = renderHook(() => useRunEvents(null));

    expect(view.current).toBeNull();
    expect(FakeEventSource.instances).toHaveLength(0);
  });

  it('plays the stream into a completed view, then closes it', () => {
    const { result: view } = renderHook(() => useRunEvents('r1'));
    expect(source().url).toBe('/api/runs/r1/events');
    expect(view.current?.phase).toBe('connecting');

    act(() => {
      for (const frame of replayFrames) source().send(frame.type, frame.data);
    });

    expect(view.current?.phase).toBe('completed');
    expect(view.current?.sides.jev.findings).toHaveLength(14);
    expect(source().readyState).toBe(FakeEventSource.CLOSED);
  });

  it('fails closed on an event it cannot read', () => {
    const { result: view } = renderHook(() => useRunEvents('r1'));

    act(() => {
      source().send('step', '{"seq": 1, "type": "step", "data": {"step": "teleport"}}');
    });

    expect(view.current?.phase).toBe('failed');
    expect(view.current?.error?.code).toBe('INVALID_EVENT');
    expect(source().readyState).toBe(FakeEventSource.CLOSED);
  });

  it('leaves a dropped connection to the browser to resume', () => {
    const { result: view } = renderHook(() => useRunEvents('r1'));

    act(() => {
      source().send(replayFrames[0]?.type ?? '', replayFrames[0]?.data ?? '');
      source().fail(FakeEventSource.CONNECTING);
    });

    expect(view.current?.phase).toBe('running');
    expect(getRunMock).not.toHaveBeenCalled();
  });

  it('falls back to the run status when the stream closes for good', async () => {
    getRunMock.mockResolvedValueOnce(status({}));
    const { result: view } = renderHook(() => useRunEvents('r1'));

    await act(async () => {
      source().fail(FakeEventSource.CLOSED);
      await Promise.resolve();
    });

    expect(getRunMock).toHaveBeenCalledWith('r1', {
      signal: expect.any(AbortSignal) as AbortSignal,
    });
    expect(view.current?.phase).toBe('completed');
    expect(view.current?.result).toEqual(result);
  });

  it('polls the status while the run is still going', async () => {
    vi.useFakeTimers();
    getRunMock
      .mockResolvedValueOnce(status({ status: 'running', result: null }))
      .mockResolvedValueOnce(status({}));
    const { result: view } = renderHook(() => useRunEvents('r1'));

    await act(async () => {
      source().fail(FakeEventSource.CLOSED);
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(view.current?.phase).toBe('connecting');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(STATUS_POLL_MS);
    });

    expect(getRunMock).toHaveBeenCalledTimes(2);
    expect(view.current?.phase).toBe('completed');
  });

  it('shows why the status could not be read', async () => {
    getRunMock.mockRejectedValueOnce(new ApiRequestError(404, 'UNKNOWN_RUN', "Unknown run 'r1'"));
    const { result: view } = renderHook(() => useRunEvents('r1'));

    await act(async () => {
      source().fail(FakeEventSource.CLOSED);
      await Promise.resolve();
    });

    expect(view.current).toMatchObject({
      phase: 'failed',
      error: { code: 'UNKNOWN_RUN', message: "Unknown run 'r1'" },
    });
  });

  it('rides out a brief outage while polling', async () => {
    vi.useFakeTimers();
    getRunMock
      .mockRejectedValueOnce(new ApiRequestError(0, 'NETWORK', 'down'))
      .mockRejectedValueOnce(new ApiRequestError(502, 'BAD_RESPONSE', 'proxy'))
      .mockResolvedValueOnce(status({}));
    const { result: view } = renderHook(() => useRunEvents('r1'));

    await act(async () => {
      source().fail(FakeEventSource.CLOSED);
      await vi.advanceTimersByTimeAsync(STATUS_POLL_MS * 2);
    });

    expect(getRunMock).toHaveBeenCalledTimes(3);
    expect(view.current?.phase).toBe('completed');
  });

  it('gives up after repeated outages', async () => {
    vi.useFakeTimers();
    getRunMock.mockRejectedValue(new ApiRequestError(0, 'NETWORK', 'Could not reach the API.'));
    const { result: view } = renderHook(() => useRunEvents('r1'));

    await act(async () => {
      source().fail(FakeEventSource.CLOSED);
      await vi.advanceTimersByTimeAsync(STATUS_POLL_MS * 10);
    });

    expect(getRunMock).toHaveBeenCalledTimes(MAX_STATUS_FAILURES);
    expect(view.current).toMatchObject({ phase: 'failed', error: { code: 'NETWORK' } });
  });

  it('closes the stream and stops polling on unmount', async () => {
    let signal: AbortSignal | undefined;
    getRunMock.mockImplementationOnce((_id, options) => {
      signal = options?.signal;
      return new Promise(() => undefined);
    });
    const { unmount } = renderHook(() => useRunEvents('r1'));
    await act(async () => {
      source().fail(FakeEventSource.CLOSED);
      await Promise.resolve();
    });

    unmount();

    expect(source().readyState).toBe(FakeEventSource.CLOSED);
    expect(signal?.aborted).toBe(true);
  });

  it('does not show an old view when the same run id comes back', () => {
    const initialProps: { id: string | null } = { id: 'r1' };
    const { result: view, rerender } = renderHook(({ id }) => useRunEvents(id), { initialProps });
    act(() => {
      for (const frame of replayFrames) source().send(frame.type, frame.data);
    });

    rerender({ id: null });
    rerender({ id: 'r1' });

    expect(view.current?.phase).toBe('connecting');
  });

  it('starts afresh for a new run', () => {
    const { result: view, rerender } = renderHook(({ id }) => useRunEvents(id), {
      initialProps: { id: 'r1' },
    });
    act(() => {
      source().send(replayFrames[0]?.type ?? '', replayFrames[0]?.data ?? '');
    });

    rerender({ id: 'r2' });

    expect(source(0).readyState).toBe(FakeEventSource.CLOSED);
    expect(source(1).url).toBe('/api/runs/r2/events');
    expect(view.current).toMatchObject({ runId: 'r2', phase: 'connecting', timeline: [] });
  });
});
