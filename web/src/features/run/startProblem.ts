/**
 * What to do next when a run can't start. The server's message says what went wrong (it is
 * written for display and never contains keys); the hint says what the viewer can do.
 */
import type { ApiError } from '../../api/types';

const HINTS: Readonly<Record<string, string>> = {
  LIVE_DISABLED: 'Use Replay, or switch live mode on at the server.',
  BUDGET_EXCEEDED: 'The spending cap is reached. Replays still work.',
  MISSING_KEYS: 'Add the API keys to the server environment and restart it.',
  LEDGER_MISSING: 'Set up the spend ledger before live runs. Replays still work.',
  LEDGER_CORRUPT: 'The spend ledger needs repair before live runs. Replays still work.',
  UNKNOWN_MODEL: 'Pick a model with known pricing, so spend can be capped.',
  RUN_IN_PROGRESS: 'Wait for that run to finish, then try again.',
  NO_RECORDING: 'Record a live run from the command line first.',
  RECORDING_INVALID: 'Record the run again; this recording cannot be read.',
};

export interface StartProblem {
  readonly message: string;
  readonly hint: string | null;
}

export function startProblem(error: ApiError): StartProblem {
  return { message: error.message, hint: HINTS[error.code] ?? null };
}
