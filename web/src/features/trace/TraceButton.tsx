import type { ReactNode } from 'react';

import { documentLabel } from '../documents/documentLabel';
import { useTrace, type TraceTarget } from './traceContext';
import './trace.css';

type Props = {
  target: TraceTarget;
  children: ReactNode;
};

/** A figure that, pressed, shows where it came from. Plain text when nothing can trace. */
export function TraceButton({ target, children }: Props) {
  const trace = useTrace();
  if (!trace) return <>{children}</>;
  return (
    <button
      type="button"
      className="trace-button"
      onClick={(event) => {
        trace(target, event.currentTarget);
      }}
    >
      {children}
      <span className="visually-hidden">, show in {documentLabel(target.docId).full}</span>
    </button>
  );
}
