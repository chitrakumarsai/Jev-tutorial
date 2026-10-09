import { useEffect, useRef, useState } from 'react';

import { ApiRequestError, startRun } from '../../api/client';
import type { RunView } from './runReducer';

type Props = {
  scenarioId: string | null;
  view: RunView | null;
  onStarted: (runId: string) => void;
};

function describe(view: RunView | null): string {
  switch (view?.phase) {
    case undefined:
      return '';
    case 'connecting':
      return 'Connecting…';
    case 'running':
      return 'Running…';
    case 'completed':
      return view.mode === 'live' ? 'Run complete' : 'Replay complete';
    case 'failed':
      return view.error?.message ?? 'The run failed.';
  }
}

/**
 * Starts a paced replay (live mode and the recording badge arrive in U8). Mount it with
 * `key={scenarioId}` so a scenario switch starts it fresh.
 */
export function RunControl({ scenarioId, view, onStarted }: Props) {
  const [isStarting, setIsStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const isMounted = useRef(true);
  const isBusy = isStarting || view?.phase === 'connecting' || view?.phase === 'running';

  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false; // a start that lands after this belongs to nobody
    };
  }, []);

  const handleClick = async () => {
    if (!scenarioId || isBusy) return;
    setIsStarting(true);
    setStartError(null);
    try {
      const { run_id } = await startRun({ scenario_id: scenarioId, mode: 'replay', pace: true });
      if (isMounted.current) onStarted(run_id);
    } catch (error) {
      if (isMounted.current) {
        setStartError(
          error instanceof ApiRequestError ? error.message : 'The replay could not be started.',
        );
      }
    } finally {
      if (isMounted.current) setIsStarting(false);
    }
  };

  const status = isStarting ? 'Starting the replay…' : (startError ?? describe(view));

  return (
    <div className="run-control">
      {/* aria-disabled, not disabled, while busy: disabling the pressed button drops focus. */}
      <button
        type="button"
        className="run-control__button"
        disabled={!scenarioId}
        aria-disabled={isBusy}
        onClick={() => void handleClick()}
      >
        Replay recorded run
      </button>
      <p role="status" className="run-control__status">
        {status}
      </p>
    </div>
  );
}
