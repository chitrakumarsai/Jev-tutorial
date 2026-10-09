// Names for the generated API types. Regenerate schema.gen.ts with `npm run gen:api`.
import type { components } from './schema.gen';

export type Schemas = components['schemas'];

export type ApiError = Schemas['ApiError'];
export type BudgetReport = Schemas['BudgetReport'];
export type DocumentText = Schemas['DocumentText'];
export type Finding = Schemas['Finding'];
export type Health = Schemas['Health'];
export type RecordingMeta = Schemas['RecordingMeta'];
export type RunRequest = Schemas['RunRequest'];
export type RunResult = Schemas['RunResult'];
export type RunStarted = Schemas['RunStarted'];
export type RunStatus = Schemas['RunStatus'];
export type ScenarioDetail = Schemas['ScenarioDetail'];
export type ScenarioSummary = Schemas['ScenarioSummary'];
export type SideResult = Schemas['SideResult'];
export type Mode = RunStatus['mode'];
export type SideName = SideResult['side'];
