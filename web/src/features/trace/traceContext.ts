/** Lets any number on screen ask to be traced back to the passage it came from. */
import { createContext, useContext } from 'react';

export interface TraceTarget {
  /** The highlight id of the evidence span (see evidenceHighlightId). */
  readonly highlightId: string;
  readonly docId: string;
  /** The quoted words, for the announcement. */
  readonly quote: string;
}

export type TraceFn = (target: TraceTarget, from: HTMLElement) => void;

export const TraceContext = createContext<TraceFn | null>(null);

export function useTrace(): TraceFn | null {
  return useContext(TraceContext);
}
