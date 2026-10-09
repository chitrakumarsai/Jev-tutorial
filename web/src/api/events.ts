/**
 * Run events from `GET /api/runs/{id}/events` (SSE). The OpenAPI spec can't describe an
 * event stream, so these guards follow src/jev/runs/events.py and the pipelines' `emit`
 * calls; the replay fixture test keeps them honest.
 */
import { z } from 'zod';

import { ApiErrorSchema, FindingSchema, RunResultSchema, SideResultSchema } from './guards';
import type { ApiError } from './types';

const Count = z.number().int().nonnegative();
const Side = z.enum(['jev', 'llm']);

const StepDataSchema = z.discriminatedUnion('step', [
  z.object({ step: z.literal('candidates'), requests: Count, questions: Count }),
  z.object({
    step: z.literal('request_sent'),
    purpose: z.string(),
    questions: Count.exactOptional(),
  }),
  z.object({
    step: z.literal('answers'),
    latency_ms: Count,
    purpose: z.string().exactOptional(),
    // Jev: question id -> [chosen option, confidence], and its "none of the above" weights
    // display only, so not range-checked: a float a hair past 1 must not fail a live run
    choices: z.record(z.string(), z.tuple([z.string(), z.number()])).exactOptional(),
    nouls: z.record(z.string(), z.number()).exactOptional(),
    // LLM: why there was no usable answer, if so
    refusal: z.string().nullable().exactOptional(),
    error: z.string().nullable().exactOptional(),
  }),
  z.object({ step: z.literal('computed'), findings: Count }),
  z.object({ step: z.literal('gated'), review: Count, notes: z.array(z.string()).exactOptional() }),
  z.object({ step: z.literal('done'), findings: Count }),
]);

const at = { seq: Count, t_ms: Count };

const RunEventSchema = z.discriminatedUnion('type', [
  z.object({
    ...at,
    type: z.literal('run_started'),
    side: z.null(),
    data: z.object({
      run_id: z.string(),
      scenario_id: z.string(),
      mode: z.enum(['live', 'replay']),
    }),
  }),
  z.object({ ...at, type: z.literal('step'), side: Side, data: StepDataSchema }),
  z.object({
    ...at,
    type: z.literal('finding'),
    side: Side,
    data: z.object({ finding: FindingSchema }),
  }),
  z.object({
    ...at,
    type: z.literal('side_completed'),
    side: Side,
    data: z.object({ result: SideResultSchema }),
  }),
  z.object({
    ...at,
    type: z.literal('run_completed'),
    side: z.null(),
    data: z.object({ result: RunResultSchema }),
  }),
  z.object({ ...at, type: z.literal('run_failed'), side: z.null(), data: ApiErrorSchema }),
]);

export type RunEvent = z.infer<typeof RunEventSchema>;
export type RunEventType = RunEvent['type'];
export type StepEvent = Extract<RunEvent, { type: 'step' }>;
export type StepData = StepEvent['data'];

/** Every named SSE event to listen for (EventSource only delivers names it was told about). */
export const RUN_EVENT_TYPES = RunEventSchema.options.map(
  (option) => option.shape.type.value,
) as readonly RunEventType[];

export const TERMINAL_EVENT_TYPES: ReadonlySet<RunEventType> = new Set([
  'run_completed',
  'run_failed',
]);

export type ParsedRunEvent = { ok: true; event: RunEvent } | { ok: false; error: ApiError };

const INVALID: ParsedRunEvent = {
  ok: false,
  // Never echo the payload: it can carry document text.
  error: { code: 'INVALID_EVENT', message: 'The server sent a run event this page cannot read.' },
};

/** Parse one SSE frame: its event name and its `data` text. */
export function parseRunEvent(name: string, data: string): ParsedRunEvent {
  let raw: unknown;
  try {
    raw = JSON.parse(data);
  } catch {
    return INVALID;
  }
  const parsed = RunEventSchema.safeParse(raw);
  if (!parsed.success || parsed.data.type !== name) return INVALID;
  return { ok: true, event: parsed.data };
}
