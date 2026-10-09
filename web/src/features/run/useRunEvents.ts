/**
 * Streams a run's events (SSE) into a `RunView`. The browser resumes a dropped stream by
 * itself (sending Last-Event-ID); when it gives up, the run's status is read instead, and
 * polled while the run is still going. Unreadable events fail the view closed.
 */
import { useEffect, useReducer } from 'react';

import { ApiRequestError, getRun, runEventsUrl } from '../../api/client';
import { RUN_EVENT_TYPES, TERMINAL_EVENT_TYPES, parseRunEvent } from '../../api/events';
import type { ApiError } from '../../api/types';
import { initialRunView, runReducer, type RunView } from './runReducer';

export const STATUS_POLL_MS = 1000;
/** Consecutive failed status reads (network, 5xx) before the view gives up. */
export const MAX_STATUS_FAILURES = 3;

/** A 4xx (e.g. an unknown run) won't fix itself; outages and 5xx might. */
function isLasting(error: unknown): boolean {
  return error instanceof ApiRequestError && error.status >= 400 && error.status < 500;
}

function toApiError(error: unknown): ApiError {
  if (error instanceof ApiRequestError) return { code: error.code, message: error.message };
  return { code: 'STATUS_UNAVAILABLE', message: 'Could not read the run status.' };
}

export function useRunEvents(runId: string | null): RunView | null {
  const [view, dispatch] = useReducer(runReducer, runId ?? '', initialRunView);

  useEffect(() => {
    // Reset on null too, so a run id that comes back never shows its old view.
    dispatch({ type: 'reset', runId: runId ?? '' });
    if (runId === null) return;
    const controller = new AbortController();
    let pollTimer: ReturnType<typeof setTimeout> | undefined;
    const source = new EventSource(runEventsUrl(runId));

    const onFrame = (frame: MessageEvent<string>): void => {
      const parsed = parseRunEvent(frame.type, frame.data);
      if (!parsed.ok) {
        source.close();
        dispatch({ type: 'failed', error: parsed.error });
        return;
      }
      dispatch({ type: 'event', event: parsed.event });
      if (TERMINAL_EVENT_TYPES.has(parsed.event.type)) source.close(); // else it reconnects
    };
    for (const type of RUN_EVENT_TYPES) source.addEventListener(type, onFrame);

    let failures = 0;
    const readStatus = async (): Promise<void> => {
      try {
        const status = await getRun(runId, { signal: controller.signal });
        if (controller.signal.aborted) return;
        failures = 0;
        dispatch({ type: 'snapshot', status });
        if (status.status === 'running') {
          pollTimer = setTimeout(() => void readStatus(), STATUS_POLL_MS);
        }
      } catch (error) {
        if (controller.signal.aborted) return;
        failures += 1;
        if (isLasting(error) || failures >= MAX_STATUS_FAILURES) {
          dispatch({ type: 'failed', error: toApiError(error) });
        } else {
          pollTimer = setTimeout(() => void readStatus(), STATUS_POLL_MS);
        }
      }
    };
    // CONNECTING: the browser is retrying. CLOSED: it gave up (an HTTP error, or a 204
    // once every event was seen), so the status endpoint has the answer.
    source.onerror = () => {
      if (source.readyState === EventSource.CLOSED) void readStatus();
    };

    return () => {
      source.close();
      controller.abort();
      clearTimeout(pollTimer);
    };
  }, [runId]);

  if (runId === null) return null;
  // Until the reset lands, don't show the previous run's view under the new id.
  return view.runId === runId ? view : initialRunView(runId);
}
