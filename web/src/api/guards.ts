/**
 * Runtime guards for every API response. The server is ours, but its payloads are still
 * data crossing a boundary: validate, drop unknown keys, and fail closed on drift.
 * The compile-time checks at the bottom keep each guard in step with schema.gen.ts.
 */
import { z } from 'zod';

import type { Schemas } from './types';

/** Python's `str(Decimal)`: plain or exponent form ("0E-8"); never formatted ("$1,250.00"). */
export const MoneySchema = z.string().regex(/^-?\d+(\.\d+)?(E[+-]?\d+)?$/i, 'not a Decimal string');

const Count = z.number().int().nonnegative();
const Probability = z.number().min(0).max(1);
const Mode = z.enum(['live', 'replay']);
const Side = z.enum(['jev', 'llm']);

export const ApiErrorSchema = z.object({ code: z.string(), message: z.string() });

export const SpanRefSchema = z
  .object({ doc_id: z.string(), start: Count, end: Count, text: z.string() })
  .refine((span) => span.end >= span.start, 'span ends before it starts');

export const FindingSchema = z.object({
  id: z.string(),
  kind: z.string(),
  doc_id: z.string(),
  line_ref: z.string().nullable().exactOptional(),
  billed: MoneySchema.nullable().exactOptional(),
  expected: MoneySchema.nullable().exactOptional(),
  variance: MoneySchema.nullable().exactOptional(),
  lane: z.enum(['auto', 'review']),
  confidence: Probability.nullable().exactOptional(),
  review_reason: z.string().nullable().exactOptional(),
  evidence: z.array(SpanRefSchema),
  traceable: z.boolean(),
  // S2: is the checklist clause in the agreement? S3: does the citation hold up?
  verdict: z
    .enum(['present', 'absent', 'partial', 'verified', 'unsupported', 'contradicted', 'fabricated'])
    .nullable()
    .exactOptional(),
  risk: z.enum(['low', 'medium', 'high', 'critical']).nullable().exactOptional(),
  claim: z.string().nullable().exactOptional(),
});

export const MetricsSchema = z.object({
  latency_ms: Count,
  requests: Count,
  input_tokens: Count,
  output_tokens: Count,
  cost_usd: MoneySchema.nullable(),
});

export const ScorecardSchema = z.object({
  items: z.array(
    z.object({
      key_id: z.string(),
      status: z.enum(['correct', 'correct_in_review', 'wrong_value', 'missed']),
      finding_id: z.string().nullable(),
      label: z.string().nullable().exactOptional(),
    }),
  ),
  false_positives: z.array(z.string()),
  trap_hits: z.array(z.string()),
  summary: z.array(
    z
      .object({
        label: z.string(),
        kind: z.enum(['count', 'money', 'text']),
        value: z.string().nullable(),
        note: z.string().nullable().exactOptional(),
        ok: z.boolean().nullable().exactOptional(),
      })
      // The UI formats counts and money from these strings, so they must be numbers.
      .refine(
        (row) =>
          row.value === null ||
          (row.kind === 'count' && /^\d+$/.test(row.value)) ||
          (row.kind === 'money' && MoneySchema.safeParse(row.value).success) ||
          row.kind === 'text',
        { message: 'summary value does not suit its kind' },
      ),
  ),
  variance: z
    .object({ expected: MoneySchema, reported: MoneySchema.nullable(), exact: z.boolean() })
    .nullable()
    .exactOptional(),
  of: Count,
  correct: Count,
  correct_in_review: Count,
});

export const ProvenanceSchema = z.object({
  kind: z.enum(['live', 'recorded']),
  models: z.array(z.string()),
  recording_id: z.string().nullable().exactOptional(),
  recorded_at: z.string().nullable().exactOptional(),
});

export const SideResultSchema = z.object({
  side: Side,
  findings: z.array(FindingSchema),
  metrics: MetricsSchema,
  scorecard: ScorecardSchema,
  provenance: ProvenanceSchema,
  notes: z.array(z.string()),
});

export const RunResultSchema = z.object({
  run_id: z.string(),
  scenario_id: z.string(),
  mode: Mode,
  sides: z.record(z.string(), SideResultSchema),
  recording_id: z.string().nullable().exactOptional(),
});

export const RunStatusSchema = z.object({
  run_id: z.string(),
  mode: Mode,
  status: z.enum(['running', 'completed', 'failed']),
  error: ApiErrorSchema.nullable(),
  result: RunResultSchema.nullable(),
});

export const RunStartedSchema = z.object({ run_id: z.string() });
export const HealthSchema = z.object({ status: z.literal('ok') });

export const ScenarioSummarySchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
});

export const ScenarioDetailSchema = ScenarioSummarySchema.extend({
  llm_prompt: z.string(),
  models: z.object({ jev: z.string(), llm: z.string() }),
  live_enabled: z.boolean(),
});

export const DocumentTextSchema = z.object({ doc_id: z.string(), text: z.string() });

export const RecordingMetaSchema = z.object({
  id: z.string(),
  scenario_id: z.string(),
  recorded_at: z.string(),
  jev_model: z.string(),
  llm_model: z.string(),
});

export const BudgetReportSchema = z.object({
  ledger_initialised: z.boolean(),
  providers: z.array(
    z.object({
      provider: z.string(),
      cap: MoneySchema,
      key_configured: z.boolean(),
      spent: MoneySchema.nullable(),
      reserved: MoneySchema.nullable(),
      remaining: MoneySchema.nullable(),
    }),
  ),
});

/** `{success, data, error}`: data on success, an error on failure, never both. */
export function envelopeOf<T extends z.ZodType>(data: T) {
  return z.discriminatedUnion('success', [
    z.object({ success: z.literal(true), data, error: z.null().exactOptional() }),
    z.object({ success: z.literal(false), data: z.null().exactOptional(), error: ApiErrorSchema }),
  ]);
}

// Compile-time drift checks: each guard's output must match the generated type both ways.
type Same<A, B> = [A] extends [B] ? ([B] extends [A] ? true : false) : false;
type Expect<T extends true> = T;
export type GuardsMatchSchema = [
  Expect<Same<z.infer<typeof ApiErrorSchema>, Schemas['ApiError']>>,
  Expect<Same<z.infer<typeof FindingSchema>, Schemas['Finding']>>,
  Expect<Same<z.infer<typeof SideResultSchema>, Schemas['SideResult']>>,
  Expect<Same<z.infer<typeof RunResultSchema>, Schemas['RunResult']>>,
  Expect<Same<z.infer<typeof RunStatusSchema>, Schemas['RunStatus']>>,
  Expect<Same<z.infer<typeof RunStartedSchema>, Schemas['RunStarted']>>,
  Expect<Same<z.infer<typeof HealthSchema>, Schemas['Health']>>,
  Expect<Same<z.infer<typeof ScenarioSummarySchema>, Schemas['ScenarioSummary']>>,
  Expect<Same<z.infer<typeof ScenarioDetailSchema>, Schemas['ScenarioDetail']>>,
  Expect<Same<z.infer<typeof DocumentTextSchema>, Schemas['DocumentText']>>,
  Expect<Same<z.infer<typeof RecordingMetaSchema>, Schemas['RecordingMeta']>>,
  Expect<Same<z.infer<typeof BudgetReportSchema>, Schemas['BudgetReport']>>,
];
