import { LayoutGroup } from 'motion/react';
import { useCallback, useMemo, useState } from 'react';

import { DocumentViewer } from '../features/documents/DocumentViewer';
import { documentLabel } from '../features/documents/documentLabel';
import { highlightsByDocument } from '../features/documents/highlights';
import { JevPipeline } from '../features/jev/JevPipeline';
import { Ledger } from '../features/ledger/Ledger';
import { ReviewLane } from '../features/ledger/ReviewLane';
import { LlmResponse } from '../features/llm/LlmResponse';
import { SidePane } from '../features/panes/SidePane';
import { Results } from '../features/results/Results';
import type { RunView, SideProgress } from '../features/run/runReducer';
import type { LoadedScenario } from '../features/scenario/loadScenario';
import { TraceLine } from '../features/trace/TraceLine';
import { TraceContext, type TraceFn, type TraceTarget } from '../features/trace/traceContext';

type Props = {
  scenario: LoadedScenario;
  runView: RunView | null;
};

interface ActiveTrace extends TraceTarget {
  readonly seq: number;
  /** The pressed figure while its line is showing; null once the line has faded. */
  readonly from: HTMLElement | null;
}

/** The notes of the Jev side's gate step, or null before the gate has run. */
function gateNotes(jev: SideProgress | null): readonly string[] | null {
  const gated = jev?.steps.findLast((s) => s.data.step === 'gated')?.data;
  return gated?.step === 'gated' ? (gated.notes ?? []) : null;
}

/** One scenario side by side: the source, the plain LLM and Jev + code, then the results. */
export function Comparison({ scenario, runView }: Props) {
  const [chosenDoc, setChosenDoc] = useState<string | null>(null);
  const [trace, setTrace] = useState<ActiveTrace | null>(null);
  const highlights = useMemo(() => highlightsByDocument(runView), [runView]);
  const { detail, documents } = scenario;
  const selectedDoc = chosenDoc ?? documents[0]?.doc_id ?? '';
  const llm = runView?.sides.llm ?? null;
  const jev = runView?.sides.jev ?? null;
  const notes = gateNotes(jev);

  const traceTo = useCallback<TraceFn>((target, from) => {
    setChosenDoc(target.docId);
    setTrace((previous) => ({ ...target, from, seq: (previous?.seq ?? 0) + 1 }));
  }, []);
  const focus = useMemo(
    () => (trace ? { highlightId: trace.highlightId, seq: trace.seq } : null),
    [trace],
  );
  const traceSeq = trace?.seq;
  const endLine = useCallback(() => {
    setTrace((current) =>
      current && current.seq === traceSeq ? { ...current, from: null } : current,
    );
  }, [traceSeq]);

  return (
    <TraceContext value={traceTo}>
      <div className="workspace__intro">
        <h2 className="workspace__title">{detail.title}</h2>
        <p className="workspace__description">{detail.description}</p>
      </div>
      <LayoutGroup>
        <div className="workspace__grid">
          <DocumentViewer
            documents={documents}
            highlights={highlights}
            selected={selectedDoc}
            onSelect={(docId) => {
              setChosenDoc(docId);
              setTrace(null); // a tab picked by hand ends the trace
            }}
            focus={focus}
          />
          <SidePane side="llm" model={detail.models.llm} progress={llm}>
            <details className="prompt">
              <summary>Exact prompt sent to the LLM</summary>
              <pre>{detail.llm_prompt}</pre>
            </details>
            {/* Keyed by run, so a new run types its result out again. */}
            <LlmResponse
              key={runView?.runId ?? 'none'}
              progress={llm}
              mode={runView?.mode ?? null}
            />
            {llm && <Ledger side="llm" findings={llm.findings} result={llm.result} />}
          </SidePane>
          <SidePane side="jev" model={detail.models.jev} progress={jev}>
            <JevPipeline progress={jev} />
            {jev && (
              <Ledger
                side="jev"
                findings={jev.findings}
                result={jev.result}
                isReviewSeparate={notes !== null}
              />
            )}
            {jev && notes !== null && (
              <ReviewLane findings={jev.findings} result={jev.result} notes={notes} />
            )}
          </SidePane>
        </div>
      </LayoutGroup>
      {runView?.result && <Results result={runView.result} />}
      {trace?.from && (
        <TraceLine
          key={trace.seq}
          from={trace.from}
          highlightId={trace.highlightId}
          onDone={endLine}
        />
      )}
      <p role="status" className="visually-hidden">
        {/* A no-break space on alternate traces makes a repeat of the same trace announce. */}
        {trace &&
          `Showing the passage in ${documentLabel(trace.docId).full}: “${trace.quote}”${
            trace.seq % 2 === 0 ? '\u00a0' : ''
          }`}
      </p>
    </TraceContext>
  );
}
