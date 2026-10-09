import { MotionConfig } from 'motion/react';
import { useState } from 'react';

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

function Problem({ error }: { error: ApiError }) {
  return (
    <p role="alert" className="workspace__problem">
      {error.message}
    </p>
  );
}

export function App() {
  const catalog = useResource(CATALOG, loadCatalog);
  const [chosenScenario, setChosenScenario] = useState<string | null>(null);
  const scenarioId =
    chosenScenario ?? (catalog.status === 'ready' ? (catalog.data[0]?.id ?? null) : null);
  const scenario = useResource(scenarioId, loadScenario);
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
            view={runView}
            onStarted={(runId) => {
              if (scenarioId) setRun({ scenarioId, runId });
            }}
          />
          <ThemeToggle />
        </div>
      </header>
      <main className="workspace">
        {problem ? (
          <Problem error={problem} />
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
