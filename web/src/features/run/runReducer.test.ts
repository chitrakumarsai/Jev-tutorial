import { describe, expect, it } from 'vitest';

import { parseRunEvent, type RunEvent } from '../../api/events';
import type { RunStatus } from '../../api/types';
import { replayFrames } from '../../test/fixtures/replay';
import { initialRunView, runReducer, type RunView } from './runReducer';

const events: readonly RunEvent[] = replayFrames.map((frame) => {
  const parsed = parseRunEvent(frame.type, frame.data);
  if (!parsed.ok) throw new Error(`fixture event did not parse: ${parsed.error.message}`);
  return parsed.event;
});
const completed = events.at(-1);
if (completed?.type !== 'run_completed') throw new Error('fixture must end with run_completed');
const result = completed.data.result;

function play(list: readonly RunEvent[], from: RunView = initialRunView('r1')): RunView {
  return list.reduce((view, event) => runReducer(view, { type: 'event', event }), from);
}

describe('runReducer', () => {
  it('starts out connecting, with nothing seen', () => {
    expect(initialRunView('r1')).toMatchObject({
      runId: 'r1',
      phase: 'connecting',
      lastSeq: -1,
      timeline: [],
      result: null,
      error: null,
    });
  });

  it('plays a whole replay into a completed view', () => {
    const view = play(events);

    expect(view.phase).toBe('completed');
    expect(view.mode).toBe('replay');
    expect(view.lastSeq).toBe(events.length - 1);
    expect(view.timeline).toHaveLength(events.length);
    expect(view.sides.jev.findings).toHaveLength(14);
    expect(view.sides.llm.findings).toHaveLength(18);
    expect(view.sides.jev.steps.map((s) => s.data.step)).toContain('gated');
    expect(view.sides.llm.steps.map((s) => s.data.step)).toEqual([
      'request_sent',
      'answers',
      'done',
    ]);
    expect(view.sides.jev.result).toEqual(result.sides.jev);
    expect(view.result).toEqual(result);
  });

  it('is running once the run has started', () => {
    expect(play(events.slice(0, 1)).phase).toBe('running');
  });

  it('ignores an event it has already seen (a resumed stream)', () => {
    const view = play(events.slice(0, 5));

    expect(runReducer(view, { type: 'event', event: events[3] as RunEvent })).toBe(view);
  });

  it('ignores events after the run has ended', () => {
    const done = play(events);
    const late = { ...(events[1] as RunEvent), seq: 999 };

    expect(runReducer(done, { type: 'event', event: late })).toBe(done);
  });

  it('never changes an earlier view', () => {
    const early = play(events.slice(0, 10));
    const snapshot = JSON.stringify(early);

    play(events.slice(10), early);

    expect(JSON.stringify(early)).toBe(snapshot);
  });

  it('records a run failure', () => {
    const failed: RunEvent = {
      seq: 2,
      t_ms: 9,
      type: 'run_failed',
      side: null,
      data: { code: 'RUN_FAILED', message: 'The run failed (TimeoutError).' },
    };

    const view = play([...events.slice(0, 2), failed]);

    expect(view).toMatchObject({ phase: 'failed', error: failed.data });
  });

  describe('a status snapshot (the GET fallback)', () => {
    const status = (patch: Partial<RunStatus>): RunStatus => ({
      run_id: 'r1',
      mode: 'replay',
      status: 'completed',
      error: null,
      result,
      ...patch,
    });

    it('completes the view from the result', () => {
      const view = runReducer(initialRunView('r1'), { type: 'snapshot', status: status({}) });

      expect(view).toMatchObject({ phase: 'completed', mode: 'replay', result });
      expect(view.sides.llm.findings).toEqual(result.sides.llm?.findings);
      expect(view.sides.jev.result).toEqual(result.sides.jev);
    });

    it('trusts the result over a partly played stream', () => {
      const firstFinding = events.findIndex((e) => e.type === 'finding');
      const partial = play(events.slice(0, firstFinding + 2));
      expect(partial.sides.llm.findings.length + partial.sides.jev.findings.length).toBe(2);

      const view = runReducer(partial, { type: 'snapshot', status: status({}) });

      expect(view.sides.jev.findings).toEqual(result.sides.jev?.findings);
      expect(view.sides.llm.findings).toEqual(result.sides.llm?.findings);
    });

    it('fails a completed status that carries no result', () => {
      const view = runReducer(initialRunView('r1'), {
        type: 'snapshot',
        status: status({ result: null }),
      });

      expect(view).toMatchObject({ phase: 'failed', error: { code: 'BAD_RESPONSE' } });
    });

    it('changes nothing while the run is still going', () => {
      const view = play(events.slice(0, 4));

      expect(
        runReducer(view, { type: 'snapshot', status: status({ status: 'running', result: null }) }),
      ).toBe(view);
    });

    it('records the error of a failed run', () => {
      const error = { code: 'RUN_FAILED', message: 'The run failed (CancelledError).' };

      expect(
        runReducer(initialRunView('r1'), {
          type: 'snapshot',
          status: status({ status: 'failed', error, result: null }),
        }),
      ).toMatchObject({ phase: 'failed', error });
    });

    it('gives a failed run without an error a generic one', () => {
      const view = runReducer(initialRunView('r1'), {
        type: 'snapshot',
        status: status({ status: 'failed', result: null }),
      });

      expect(view.error?.code).toBe('RUN_FAILED');
    });
  });

  it('starts over for a new run, even after the last one ended', () => {
    expect(runReducer(play(events), { type: 'reset', runId: 'r2' })).toEqual(initialRunView('r2'));
  });

  it('records a stream failure', () => {
    const error = {
      code: 'INVALID_EVENT',
      message: 'The server sent an event this page cannot read.',
    };

    expect(runReducer(initialRunView('r1'), { type: 'failed', error })).toMatchObject({
      phase: 'failed',
      error,
    });
  });

  it('keeps a completed run when the stream fails afterwards', () => {
    const done = play(events);

    expect(runReducer(done, { type: 'failed', error: { code: 'NETWORK', message: 'x' } })).toBe(
      done,
    );
  });
});
