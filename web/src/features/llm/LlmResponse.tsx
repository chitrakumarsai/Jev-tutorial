import { useMemo } from 'react';

import type { Mode } from '../../api/types';
import { formatDuration } from '../../lib/format';
import { useTypewriter } from '../../hooks/useTypewriter';
import { parsedLine } from '../findings/findingText';
import type { SideProgress } from '../run/runReducer';
import { llmState } from './llmProgress';
import './llm.css';

type Props = {
  progress: SideProgress | null;
  /** In a replay the wait shown is the recorded one, and the words say so. */
  mode?: Mode | null;
};

/**
 * The plain LLM's single request. Its answer arrives in one piece, so the waiting is shown
 * as waiting, and the parsed result is typed out afterwards with a label that says so.
 */
export function LlmResponse({ progress, mode = null }: Props) {
  const state = llmState(progress);
  const findings = progress?.findings;
  const parsed = useMemo(() => (findings ?? []).map(parsedLine).join('\n'), [findings]);
  const typed = useTypewriter(parsed);

  if (state.kind === 'idle') return null;
  if (state.kind === 'waiting') {
    return (
      <p className="llm-wait">
        <span className="llm-wait__pulse" aria-hidden="true" />
        One request sent. Waiting for the complete response; nothing arrives until it is done.
      </p>
    );
  }
  return (
    <figure className="llm-response">
      <p className="llm-response__arrived">
        {mode === 'replay' ? 'The recorded response took ' : 'The response arrived after '}
        <data value={state.latencyMs}>{formatDuration(state.latencyMs)}</data>.
      </p>
      {state.problem && <p className="llm-response__problem">No usable answer: {state.problem}</p>}
      {parsed && (
        <>
          {/* The ledger below lists these findings for screen readers; this is the visual echo. */}
          <pre className="llm-response__text" aria-hidden="true">
            {typed.text}
            {!typed.done && <span className="llm-response__caret" />}
          </pre>
          <figcaption className="llm-response__caption">
            Parsed result, typed out for readability. The model returned it in one response; it was
            not streamed.
          </figcaption>
        </>
      )}
    </figure>
  );
}
