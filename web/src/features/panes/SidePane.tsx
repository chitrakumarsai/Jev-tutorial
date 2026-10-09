import { useId, type ReactNode } from 'react';

import type { SideName } from '../../api/types';
import type { SideProgress } from '../run/runReducer';
import './panes.css';

const TITLES: Record<SideName, string> = { llm: 'Plain LLM', jev: 'Jev + code' };

type Props = {
  side: SideName;
  model: string;
  /** This side's progress in the current run, or null before any run. */
  progress: SideProgress | null;
  children?: ReactNode;
};

/** One contender's working column. U4 and U5 fill in how each side works. */
export function SidePane({ side, model, progress, children }: Props) {
  const headingId = useId();
  const count = progress?.findings.length ?? 0;
  return (
    <section className={`side-pane side-pane--${side}`} aria-labelledby={headingId}>
      <h2 id={headingId} className="pane-heading side-pane__heading">
        {TITLES[side]}
      </h2>
      <p className="side-pane__model">
        <span className="visually-hidden">Model: </span>
        <code>{model}</code>
      </p>
      <p className="side-pane__tally">
        {progress ? (
          <>
            <data className="figure figure--headline" value={count}>
              {count}
            </data>{' '}
            {count === 1 ? 'finding' : 'findings'}
          </>
        ) : (
          'Not run yet'
        )}
      </p>
      {children}
    </section>
  );
}
