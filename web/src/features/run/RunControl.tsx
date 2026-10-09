import { useEffect, useRef, useState } from 'react';

import { ApiRequestError, getRecordings, startRun } from '../../api/client';
import type { ApiError, Mode, RunRequest } from '../../api/types';
import { Segmented } from '../../components/segmented/Segmented';
import { useResource, type Resource } from '../../hooks/useResource';
import { BudgetMeter } from '../budget/BudgetMeter';
import { RecordingBadge } from './RecordingBadge';
import type { RunView } from './runReducer';
import { startProblem } from './startProblem';
import { useLiveBudget } from './useLiveBudget';

type Props = {
  scenarioId: string | null;
  /** The server's LIVE_ENABLED. Off, a live run is refused before anything is spent. */
  isLiveEnabled: boolean;
  view: RunView | null;
  onStarted: (runId: string) => void;
};

type Recordings = Resource<Awaited<ReturnType<typeof getRecordings>>>;

const MODES: readonly Mode[] = ['replay', 'live'];
const MODE_LABELS: Record<Mode, string> = { replay: 'Replay', live: 'Live' };
const START_FAILED: ApiError = { code: 'START_FAILED', message: 'The run could not be started.' };
const CONFIRM_LIVE =
  'A live run calls OpenAI and TypeSafe and spends from the budget. Press again to confirm, or Escape to cancel.';

const loadRecordings = (scenarioId: string, signal: AbortSignal) =>
  getRecordings(scenarioId, { signal });

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
      return 'Run stopped'; // the workspace says why
  }
}

/** The newest recording, which a replay uses; null while unknown or when there is none. */
function newest(recordings: Recordings) {
  return recordings.status === 'ready' ? (recordings.data[0] ?? null) : null;
}

function ReplayContext({ recordings, onRetry }: { recordings: Recordings; onRetry: () => void }) {
  const recording = newest(recordings);
  if (recording) return <RecordingBadge recording={recording} />;
  if (recordings.status === 'ready') {
    return <p className="run-control__note">No recordings yet. Record a live run first.</p>;
  }
  if (recordings.status === 'error') {
    return (
      <p className="run-control__note">
        Recordings unavailable: {recordings.error.message}{' '}
        <button type="button" className="run-control__link" onClick={onRetry}>
          Try again
        </button>
      </p>
    );
  }
  return <p className="run-control__note">Finding the latest recording…</p>;
}

function LiveContext({ isLiveEnabled }: { isLiveEnabled: boolean }) {
  return (
    <p className="run-control__note">
      {isLiveEnabled
        ? 'Calls both APIs now. Spend is capped per key.'
        : 'Live calls are turned off on this server. Replays still work.'}
    </p>
  );
}

/** Ends with a full stop unless it already ends a sentence, so a hint can follow it. */
function sentence(text: string): string {
  return /[.!?…]$/.test(text.trim()) ? text.trim() : `${text.trim()}.`;
}

function Refusal({ error }: { error: ApiError }) {
  const { message, hint } = startProblem(error);
  return (
    <p role="alert" className="run-control__problem">
      <span aria-hidden="true">✕ </span>
      {sentence(message)}
      {hint && ` ${hint}`}
    </p>
  );
}

/** Starts runs, remembering why the last start was refused. */
function useStart(onStarted: (runId: string) => void) {
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const isMounted = useRef(true);

  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false; // a start that lands after this belongs to nobody
    };
  }, []);

  const start = async (request: RunRequest) => {
    setIsStarting(true);
    setError(null);
    try {
      const { run_id } = await startRun(request);
      if (isMounted.current) onStarted(run_id);
    } catch (caught) {
      if (isMounted.current) {
        setError(
          caught instanceof ApiRequestError
            ? { code: caught.code, message: caught.message }
            : START_FAILED,
        );
      }
    } finally {
      if (isMounted.current) setIsStarting(false);
    }
  };

  return {
    isStarting,
    error,
    start,
    clearError: () => {
      setError(null);
    },
  };
}

/**
 * Picks Replay or Live and starts a run. Replays say which recording they show; live runs
 * ask for a second press and show the budget. Mount it with `key={scenarioId}` so a scenario
 * switch starts it fresh.
 */
export function RunControl({ scenarioId, isLiveEnabled, view, onStarted }: Props) {
  const [mode, setMode] = useState<Mode>('replay');
  const [isConfirming, setIsConfirming] = useState(false);
  const [recordingsAttempt, setRecordingsAttempt] = useState(0);
  const runButton = useRef<HTMLButtonElement>(null);
  const { isStarting, error, start, clearError } = useStart(onStarted);
  const recordings = useResource(scenarioId, loadRecordings, recordingsAttempt);
  const budget = useLiveBudget(mode === 'live', view);
  const isBusy = isStarting || view?.phase === 'connecting' || view?.phase === 'running';
  const recording = newest(recordings);
  const isUnavailable = !scenarioId || (mode === 'live' ? !isLiveEnabled : recording === null);

  const cancelConfirm = () => {
    setIsConfirming(false);
    runButton.current?.focus(); // never leave focus on a Cancel button that is going away
  };

  const handleClick = () => {
    if (!scenarioId || isBusy || isUnavailable) return;
    clearError();
    if (mode === 'live' && !isConfirming) {
      setIsConfirming(true);
      return;
    }
    setIsConfirming(false);
    void start({
      scenario_id: scenarioId,
      mode,
      pace: true,
      recording_id: mode === 'replay' ? (recording?.id ?? null) : null,
    });
  };

  const status = isStarting
    ? `Starting the ${mode === 'live' ? 'live run' : 'replay'}…`
    : isConfirming
      ? CONFIRM_LIVE
      : describe(view);
  const label =
    mode === 'replay' ? 'Replay recorded run' : isConfirming ? 'Confirm live run' : 'Run live';

  return (
    <div
      className="run-control"
      onKeyDown={(event) => {
        if (event.key === 'Escape' && isConfirming) cancelConfirm();
      }}
      onBlur={(event) => {
        // An armed confirmation only lasts while focus stays here: a later click is a first press.
        if (isConfirming && !event.currentTarget.contains(event.relatedTarget)) {
          setIsConfirming(false);
        }
      }}
    >
      <div className="run-control__row">
        <Segmented
          label="Run mode"
          options={MODES}
          labels={MODE_LABELS}
          value={mode}
          isDisabled={isBusy}
          onChange={(next) => {
            setMode(next);
            setIsConfirming(false);
            clearError();
          }}
        />
        {/* aria-disabled, not disabled, while busy: disabling the pressed button drops focus. */}
        <button
          ref={runButton}
          type="button"
          className={`run-control__button${isConfirming ? ' run-control__button--confirm' : ''}`}
          disabled={isUnavailable}
          aria-disabled={isBusy}
          onClick={handleClick}
        >
          {label}
        </button>
        {isConfirming && (
          <button type="button" className="run-control__cancel" onClick={cancelConfirm}>
            Cancel
          </button>
        )}
      </div>
      {mode === 'replay' ? (
        <ReplayContext
          recordings={recordings}
          onRetry={() => {
            setRecordingsAttempt((count) => count + 1);
          }}
        />
      ) : (
        <LiveContext isLiveEnabled={isLiveEnabled} />
      )}
      <p role="status" className="run-control__status">
        {status}
      </p>
      {error && <Refusal error={error} />}
      {mode === 'live' && budget.report && <BudgetMeter report={budget.report} />}
      {mode === 'live' && budget.error && (
        <p className="run-control__note">Budget unavailable: {budget.error.message}</p>
      )}
    </div>
  );
}
