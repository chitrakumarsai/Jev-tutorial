// A real S1 replay's events (tests/api/test_event_fixture.py keeps it current). Parsed as
// `unknown` on purpose: the guards under test must not trust it.
import { parseRunEvent } from '../../api/events';
import { initialRunView, runReducer, type RunView } from '../../features/run/runReducer';
import documentsRaw from './s1-documents.json?raw';
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

/** The S1 documents as `GET /api/scenarios/{id}/documents` returns them. */
export const replayDocuments = JSON.parse(documentsRaw) as { doc_id: string; text: string }[];

/** The view after playing the whole replay: what the screens show once a run completes. */
export function completedView(runId = 'r1'): RunView {
  return replayFrames.reduce((view, frame) => {
    const parsed = parseRunEvent(frame.type, frame.data);
    if (!parsed.ok) throw new Error(`fixture event did not parse: ${parsed.error.message}`);
    return runReducer(view, { type: 'event', event: parsed.event });
  }, initialRunView(runId));
}
