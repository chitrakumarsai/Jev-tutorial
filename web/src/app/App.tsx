import { MotionConfig } from 'motion/react';
import { useRef, useState } from 'react';

import { getScenarios } from '../api/client';
import type { ApiError } from '../api/types';
import { ThemeToggle } from '../components/theme-toggle/ThemeToggle';
import { RunControl } from '../features/run/RunControl';
import { useRunEvents } from '../features/run/useRunEvents';
import { ScenarioPicker } from '../features/scenario/ScenarioPicker';
import { loadScenario } from '../features/scenario/loadScenario';
import { useResource } from '../hooks/useResource';
import { Comparison } from './Comparison';
import './app.css';

const CATALOG = 'catalog';
const NO_SCENARIOS: ApiError = { code: 'NO_SCENARIOS', message: 'No scenarios are available.' };
const loadCatalog = (_key: string, signal: AbortSignal) => getScenarios({ signal });

function Problem({ error, onRetry }: { error: ApiError; onRetry: () => void }) {
  return (
    <div role="alert" className="workspace__problem">
      <p>{error.message}</p>
      <button type="button" className="workspace__retry" onClick={onRetry}>
        Try again
      </button>
    </div>
  );
}

export function App() {
  // Bumped by "Try again", each only when its own load failed, so healthy data (and a run
  // in progress) is kept.
  const [catalogAttempt, setCatalogAttempt] = useState(0);
  const [scenarioAttempt, setScenarioAttempt] = useState(0);
  const workspace = useRef<HTMLElement>(null);
  const catalog = useResource(CATALOG, loadCatalog, catalogAttempt);
  const [chosenScenario, setChosenScenario] = useState<string | null>(null);
  const scenarioId =
    chosenScenario ?? (catalog.status === 'ready' ? (catalog.data[0]?.id ?? null) : null);
  const scenario = useResource(scenarioId, loadScenario, scenarioAttempt);
  // A run belongs to the scenario it was started for; picking another clears it.
  const [run, setRun] = useState<{ scenarioId: string; runId: string } | null>(null);
  const runView = useRunEvents(run && run.scenarioId === scenarioId ? run.runId : null);
  const problem =
    (catalog.status === 'error' && catalog.error) ||
    (catalog.status === 'ready' && catalog.data.length === 0 && NO_SCENARIOS) ||
    (scenario.status === 'error' && scenario.error) ||
    null;

  return (
    // reducedMotion="user": with the OS setting on, motion drops transforms and keeps fades.
    <MotionConfig reducedMotion="user">
      <header className="masthead">
        <div className="masthead__title">
          <p className="eyebrow">Typed decisions vs. a plain LLM</p>
          <h1>Jev Audit Lens</h1>
        </div>
        <div className="masthead__controls">
          {catalog.status === 'ready' && scenarioId && (
            <ScenarioPicker
              scenarios={catalog.data}
              value={scenarioId}
              onChange={(id) => {
                setChosenScenario(id);
                setRun(null); // a run belongs to the scenario it was started on
              }}
            />
          )}
          <RunControl
            key={scenarioId}
            scenarioId={scenario.status === 'ready' ? scenarioId : null}
            isLiveEnabled={scenario.status === 'ready' && scenario.data.detail.live_enabled}
            view={runView}
            onStarted={(runId) => {
              if (scenarioId) setRun({ scenarioId, runId });
            }}
          />
          <ThemeToggle />
        </div>
      </header>
      <main ref={workspace} className="workspace" tabIndex={-1}>
        {problem ? (
          <Problem
            error={problem}
            onRetry={() => {
              if (catalog.status === 'error') setCatalogAttempt((count) => count + 1);
              if (scenario.status === 'error') setScenarioAttempt((count) => count + 1);
              // The alert (and its button) is about to go: keep focus in the workspace.
              workspace.current?.focus();
            }}
          />
        ) : scenario.status === 'ready' ? (
          <Comparison key={scenarioId} scenario={scenario.data} runView={runView} />
        ) : (
          <p className="workspace__loading" role="status">
            Loading the scenario…
          </p>
        )}
      </main>
    </MotionConfig>
  );
}
