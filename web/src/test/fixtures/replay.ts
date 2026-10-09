// A real S1 replay's events (tests/api/test_event_fixture.py keeps it current). Parsed as
// `unknown` on purpose: the guards under test must not trust it.
import raw from './s1-replay-events.json?raw';

export const replayEvents = JSON.parse(raw) as readonly unknown[];

/** The fixture's events as SSE frames would carry them: the type plus the JSON text. */
export const replayFrames = replayEvents.map((event) => ({
  type: (event as { type: string }).type,
  data: JSON.stringify(event),
}));

export function lastReplayEvent(): Record<string, unknown> {
  return replayEvents.at(-1) as Record<string, unknown>;
}
