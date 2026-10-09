/**
 * The spend budget, read while Live is chosen and again after each live run settles (that
 * run has spent from it). The last report stays on screen while a fresh one loads, so the
 * meter doesn't blink out and back.
 */
import { useState } from 'react';

import { getBudget } from '../../api/client';
import type { ApiError, BudgetReport } from '../../api/types';
import { useResource } from '../../hooks/useResource';
import type { RunView } from './runReducer';

const loadBudget = (_key: string, signal: AbortSignal) => getBudget({ signal });

/** The id of a live run that has finished, or null. */
function settledLiveRun(view: RunView | null): string | null {
  const isSettled = view?.phase === 'completed' || view?.phase === 'failed';
  return view?.mode === 'live' && isSettled ? view.runId : null;
}

export function useLiveBudget(
  isShown: boolean,
  view: RunView | null,
): { report: BudgetReport | null; error: ApiError | null } {
  // The last settled live run; a later replay doesn't reset it, so it doesn't refetch.
  const [lastSettled, setLastSettled] = useState<string | null>(null);
  const settled = settledLiveRun(view);
  if (settled !== null && settled !== lastSettled) setLastSettled(settled);

  const budget = useResource(isShown ? `budget:${lastSettled ?? 'start'}` : null, loadBudget);
  const [shown, setShown] = useState<BudgetReport | null>(null);
  if (budget.status === 'ready' && budget.data !== shown) setShown(budget.data);

  return {
    report: budget.status === 'ready' ? budget.data : shown,
    error: budget.status === 'error' ? budget.error : null,
  };
}
