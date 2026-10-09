/**
 * Typed calls to the Jev Audit Lens API (same origin; Vite proxies /api in dev).
 * Every response is checked by a guard before the UI sees it. Failures become an
 * `ApiRequestError` whose message is safe to show; aborts pass through untouched.
 */
import { z } from 'zod';

import {
  BudgetReportSchema,
  DocumentTextSchema,
  HealthSchema,
  RecordingMetaSchema,
  RunStartedSchema,
  RunStatusSchema,
  ScenarioDetailSchema,
  ScenarioSummarySchema,
  envelopeOf,
} from './guards';
import type {
  BudgetReport,
  DocumentText,
  Health,
  RecordingMeta,
  RunRequest,
  RunStarted,
  RunStatus,
  ScenarioDetail,
  ScenarioSummary,
} from './types';

export class ApiRequestError extends Error {
  override readonly name = 'ApiRequestError';

  constructor(
    /** HTTP status, or 0 when the server could not be reached. */
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

export interface RequestOptions {
  signal?: AbortSignal;
}

const BASE = '/api';
/** Every id the backend issues (run, scenario, recording) fits this. */
const ID_PATTERN = /^[A-Za-z0-9_-]{1,64}$/;
/** Server messages are written for display; still, never let one flood the page. */
export const MAX_MESSAGE_LENGTH = 300;

const Envelopes = {
  health: envelopeOf(HealthSchema),
  scenarios: envelopeOf(z.array(ScenarioSummarySchema)),
  scenario: envelopeOf(ScenarioDetailSchema),
  documents: envelopeOf(z.array(DocumentTextSchema)),
  recordings: envelopeOf(z.array(RecordingMetaSchema)),
  runStarted: envelopeOf(RunStartedSchema),
  runStatus: envelopeOf(RunStatusSchema),
  budget: envelopeOf(BudgetReportSchema),
};

function url(...segments: string[]): string {
  return [BASE, ...segments].join('/');
}

/** Refuse anything but a plain id, so no value can steer the path ("..", "/", "?"). */
function id(value: string): string {
  if (!ID_PATTERN.test(value)) throw new ApiRequestError(0, 'INVALID_ID', 'That id is not valid.');
  return value;
}

function displayable(message: string): string {
  return message.length > MAX_MESSAGE_LENGTH
    ? `${message.slice(0, MAX_MESSAGE_LENGTH - 1)}…`
    : message;
}

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError';
}

function badResponse(status: number): ApiRequestError {
  // Never echo the body: a proxy error page or a drifted payload is not for display.
  return new ApiRequestError(
    status,
    'BAD_RESPONSE',
    'The API sent a response this page cannot read.',
  );
}

async function request<T>(
  /** Built here, inside the promise, so an invalid id rejects rather than throws. */
  path: () => string,
  envelope: z.ZodType<
    { success: true; data: T } | { success: false; error: { code: string; message: string } }
  >,
  init: RequestInit,
): Promise<T> {
  const target = path();
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  let response: Response;
  try {
    response = await fetch(target, { ...init, headers });
  } catch (error) {
    if (isAbort(error)) throw error;
    throw new ApiRequestError(0, 'NETWORK', 'Could not reach the API. Is the server running?');
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch (error) {
    if (isAbort(error)) throw error;
    throw badResponse(response.status);
  }
  const parsed = envelope.safeParse(body);
  if (!parsed.success) throw badResponse(response.status);
  if (!parsed.data.success) {
    throw new ApiRequestError(
      response.status,
      parsed.data.error.code,
      displayable(parsed.data.error.message),
    );
  }
  return parsed.data.data;
}

function get<T>(
  path: () => string,
  envelope: Parameters<typeof request<T>>[1],
  options: RequestOptions,
): Promise<T> {
  return request(path, envelope, { signal: options.signal ?? null });
}

export function getHealth(options: RequestOptions = {}): Promise<Health> {
  return get(() => url('health'), Envelopes.health, options);
}

export function getScenarios(options: RequestOptions = {}): Promise<ScenarioSummary[]> {
  return get(() => url('scenarios'), Envelopes.scenarios, options);
}

export function getScenario(
  scenarioId: string,
  options: RequestOptions = {},
): Promise<ScenarioDetail> {
  return get(() => url('scenarios', id(scenarioId)), Envelopes.scenario, options);
}

export function getDocuments(
  scenarioId: string,
  options: RequestOptions = {},
): Promise<DocumentText[]> {
  return get(() => url('scenarios', id(scenarioId), 'documents'), Envelopes.documents, options);
}

export function getRecordings(
  scenarioId: string,
  options: RequestOptions = {},
): Promise<RecordingMeta[]> {
  return get(() => url('scenarios', id(scenarioId), 'recordings'), Envelopes.recordings, options);
}

export function getRun(runId: string, options: RequestOptions = {}): Promise<RunStatus> {
  return get(() => url('runs', id(runId)), Envelopes.runStatus, options);
}

export function getBudget(options: RequestOptions = {}): Promise<BudgetReport> {
  return get(() => url('budget'), Envelopes.budget, options);
}

export function startRun(body: RunRequest, options: RequestOptions = {}): Promise<RunStarted> {
  return request(() => url('runs'), Envelopes.runStarted, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: options.signal ?? null,
  });
}

/** The SSE stream for a run; open it with EventSource (see useRunEvents). */
export function runEventsUrl(runId: string): string {
  return url('runs', id(runId), 'events');
}
