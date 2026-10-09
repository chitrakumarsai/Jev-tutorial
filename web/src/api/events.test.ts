import { describe, expect, it } from 'vitest';

import { replayEvents, replayFrames } from '../test/fixtures/replay';
import { RUN_EVENT_TYPES, parseRunEvent } from './events';

describe('parseRunEvent', () => {
  it('accepts every event of a real replay, unchanged', () => {
    for (const frame of replayFrames) {
      const parsed = parseRunEvent(frame.type, frame.data);

      expect(parsed.ok, frame.data.slice(0, 120)).toBe(true);
      expect(parsed.ok && parsed.event).toEqual(JSON.parse(frame.data));
    }
  });

  it('listens for every event type the backend sends', () => {
    const sent = new Set(replayEvents.map((event) => (event as { type: string }).type));

    for (const type of sent) expect(RUN_EVENT_TYPES).toContain(type);
    expect(RUN_EVENT_TYPES).toContain('run_failed');
  });

  it('accepts a Jev confidence a rounding error past 1 (display only)', () => {
    const answers = {
      seq: 3,
      t_ms: 4,
      type: 'step',
      side: 'jev',
      data: {
        step: 'answers',
        purpose: 's1.contract',
        latency_ms: 300,
        choices: { q1: ['yes', 1.0000000002] },
        nouls: {},
      },
    };

    expect(parseRunEvent('step', JSON.stringify(answers)).ok).toBe(true);
  });

  it('accepts a run failure', () => {
    const failed = {
      seq: 4,
      t_ms: 9,
      type: 'run_failed',
      side: null,
      data: { code: 'RUN_FAILED', message: 'The run failed (TimeoutError).' },
    };

    expect(parseRunEvent('run_failed', JSON.stringify(failed))).toEqual({
      ok: true,
      event: failed,
    });
  });

  const started = {
    seq: 0,
    t_ms: 0,
    type: 'run_started',
    side: null,
    data: { run_id: 'r1', scenario_id: 's1_reconciliation', mode: 'replay' },
  };
  const step = {
    seq: 1,
    t_ms: 3,
    type: 'step',
    side: 'jev',
    data: { step: 'computed', findings: 2 },
  };

  it.each([
    ['text that is not JSON', 'step', '{"seq": 1,'],
    ['an unknown event type', 'tick', JSON.stringify({ ...step, type: 'tick' })],
    ['an unknown step', 'step', JSON.stringify({ ...step, data: { step: 'teleport' } })],
    ['a step without a side', 'step', JSON.stringify({ ...step, side: null })],
    ['a run-level event with a side', 'run_started', JSON.stringify({ ...started, side: 'llm' })],
    ['a negative sequence number', 'step', JSON.stringify({ ...step, seq: -1 })],
    ['a frame named differently from its payload', 'finding', JSON.stringify(step)],
  ])('rejects %s', (_label, type, data) => {
    const parsed = parseRunEvent(type, data);

    expect(parsed.ok).toBe(false);
    expect(!parsed.ok && parsed.error.code).toBe('INVALID_EVENT');
  });

  it('never echoes the rejected payload in its message', () => {
    const parsed = parseRunEvent(
      'step',
      JSON.stringify({ ...step, data: { step: 'SECRET-TEXT' } }),
    );

    expect(!parsed.ok && parsed.error.message).not.toContain('SECRET-TEXT');
  });
});
