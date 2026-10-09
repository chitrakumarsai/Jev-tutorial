/**
 * Folds a run's events into what the screens show. Events arrive in `seq` order at the
 * recorded pace, so the timeline plays itself; the reducer only has to apply each once.
 * Pure and immutable: every change returns a new view, and a no-op returns the same one.
 */
import type { RunEvent, StepEvent } from '../../api/events';
import type {
  ApiError,
  Finding,
  Mode,
  RunResult,
  RunStatus,
  SideName,
  SideResult,
} from '../../api/types';

export type RunPhase = 'connecting' | 'running' | 'completed' | 'failed';

export interface SideProgress {
  readonly steps: readonly StepEvent[];
  readonly findings: readonly Finding[];
  readonly result: SideResult | null;
}

export interface RunView {
  readonly runId: string;
  readonly phase: RunPhase;
  readonly mode: Mode | null;
  /** The highest `seq` applied; anything at or below it is a repeat (a resumed stream). */
  readonly lastSeq: number;
  readonly timeline: readonly RunEvent[];
  readonly sides: Readonly<Record<SideName, SideProgress>>;
  readonly result: RunResult | null;
  readonly error: ApiError | null;
}

export type RunAction =
  | { type: 'event'; event: RunEvent }
  | { type: 'snapshot'; status: RunStatus }
  | { type: 'failed'; error: ApiError }
  | { type: 'reset'; runId: string };

const EMPTY_SIDE: SideProgress = { steps: [], findings: [], result: null };
const GENERIC_FAILURE: ApiError = { code: 'RUN_FAILED', message: 'The run failed.' };
const MISSING_RESULT: ApiError = {
  code: 'BAD_RESPONSE',
  message: 'The run finished, but its result is not available.',
};

export function initialRunView(runId: string): RunView {
  return {
    runId,
    phase: 'connecting',
    mode: null,
    lastSeq: -1,
    timeline: [],
    sides: { jev: EMPTY_SIDE, llm: EMPTY_SIDE },
    result: null,
    error: null,
  };
}

function isOver(view: RunView): boolean {
  return view.phase === 'completed' || view.phase === 'failed';
}

function updateSide(view: RunView, side: SideName, patch: Partial<SideProgress>): RunView['sides'] {
  return { ...view.sides, [side]: { ...view.sides[side], ...patch } };
}

function completed(view: RunView, result: RunResult): RunView {
  const fromResult = (side: SideName): SideProgress => {
    const outcome = result.sides[side];
    const current = view.sides[side];
    if (!outcome) return current;
    // The result is authoritative: a stream that dropped part-way may have missed findings.
    return { ...current, findings: outcome.findings, result: outcome };
  };
  return {
    ...view,
    phase: 'completed',
    mode: result.mode,
    result,
    sides: { jev: fromResult('jev'), llm: fromResult('llm') },
  };
}

function applyEvent(view: RunView, event: RunEvent): RunView {
  const seen: RunView = {
    ...view,
    phase: 'running',
    lastSeq: event.seq,
    timeline: [...view.timeline, event],
  };
  switch (event.type) {
    case 'run_started':
      return { ...seen, mode: event.data.mode };
    case 'step':
      return {
        ...seen,
        sides: updateSide(view, event.side, { steps: [...view.sides[event.side].steps, event] }),
      };
    case 'finding':
      return {
        ...seen,
        sides: updateSide(view, event.side, {
          findings: [...view.sides[event.side].findings, event.data.finding],
        }),
      };
    case 'side_completed':
      return { ...seen, sides: updateSide(view, event.side, { result: event.data.result }) };
    case 'run_completed':
      return completed(seen, event.data.result);
    case 'run_failed':
      return { ...seen, phase: 'failed', error: event.data };
  }
}

function applySnapshot(view: RunView, status: RunStatus): RunView {
  if (status.status === 'completed') {
    return status.result
      ? completed(view, status.result)
      : { ...view, phase: 'failed', error: MISSING_RESULT };
  }
  if (status.status === 'failed') {
    return { ...view, phase: 'failed', mode: status.mode, error: status.error ?? GENERIC_FAILURE };
  }
  return view; // still running: nothing new to show yet
}

export function runReducer(view: RunView, action: RunAction): RunView {
  if (action.type === 'reset') return initialRunView(action.runId);
  if (isOver(view)) return view;
  switch (action.type) {
    case 'event':
      return action.event.seq <= view.lastSeq ? view : applyEvent(view, action.event);
    case 'snapshot':
      return applySnapshot(view, action.status);
    case 'failed':
      return { ...view, phase: 'failed', error: action.error };
  }
}
