import { getDocuments, getScenario } from '../../api/client';
import type { DocumentText, ScenarioDetail } from '../../api/types';

export interface LoadedScenario {
  readonly detail: ScenarioDetail;
  readonly documents: readonly DocumentText[];
}

/** The scenario and its documents, fetched in parallel. */
export async function loadScenario(
  scenarioId: string,
  signal: AbortSignal,
): Promise<LoadedScenario> {
  const [detail, documents] = await Promise.all([
    getScenario(scenarioId, { signal }),
    getDocuments(scenarioId, { signal }),
  ]);
  return { detail, documents };
}
