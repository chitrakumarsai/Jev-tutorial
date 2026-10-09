/**
 * The Jev side's pipeline, read from its step events: code finds candidates, Jev answers
 * typed questions in parallel requests, code calculates, code gates. Pure.
 */
import type { StepData } from '../../api/events';
import { documentLabel, type DocumentLabel } from '../documents/documentLabel';
import type { SideProgress } from '../run/runReducer';

export type StageState = 'pending' | 'active' | 'done';

export interface TypedAnswer {
  readonly key: string;
  readonly question: string;
  readonly answer: string;
  /** The probability Jev gave its answer (for a yes/no question, the probability of yes). */
  readonly probability: number;
  /** Confidence in the answer shown: the probability, or for yes/no max(p, 1 - p). */
  readonly confidence: number;
  readonly kind: 'choice' | 'yes_no';
}

export interface JevRequest {
  readonly purpose: string;
  readonly label: DocumentLabel;
  readonly questions: number | null;
  readonly latencyMs: number | null;
  /** 0 for the first request to come back, 1 for the next, and so on; null until then. */
  readonly answeredOrder: number | null;
  readonly answers: readonly TypedAnswer[];
}

export interface JevPipeline {
  readonly planned: { readonly requests: number; readonly questions: number } | null;
  readonly requests: readonly JevRequest[];
  readonly computed: number | null;
  readonly gated: { readonly review: number; readonly notes: readonly string[] } | null;
  readonly stages: Readonly<Record<'candidates' | 'questions' | 'calculate' | 'gate', StageState>>;
}

const TERMS: Readonly<Record<string, string>> = {
  zone_a_rate: 'Zone A rate',
  zone_b_rate: 'Zone B rate',
  detention_rate: 'Detention rate',
  discount_threshold: 'Discount threshold (loads)',
  discount_pct: 'Volume discount',
  fuel_cap_pct: 'Fuel surcharge cap',
  late_fee_pct: 'Late fee',
  late_fee_grace_days: 'Late-fee grace days',
  invoice_date: 'Invoice date',
};
const LINE_QUESTIONS: Readonly<Record<string, string>> = {
  kind: 'what kind of line',
  paid: 'date paid',
  refinv: 'invoice referred to',
  base: 'late-fee base',
};
const REVERSED = '__rev';
// The backend's cut-off for reading a yes/no answer (NOUL_YES in jev_pipeline.py).
const YES = 0.5;

function readable(key: string): string {
  const words = key.replaceAll('_', ' ').trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** A question id as a person would ask it ("L4 duplicates L5?"). */
export function questionLabel(key: string): string {
  if (key.endsWith(REVERSED)) {
    return `${questionLabel(key.slice(0, -REVERSED.length))}, options reversed`;
  }
  const term = TERMS[key];
  if (term) return term;
  const line = /^([a-z]+)_(L\d+)$/.exec(key);
  const lineQuestion = line?.[1] ? LINE_QUESTIONS[line[1]] : undefined;
  if (line?.[2] && lineQuestion) return `${line[2]}: ${lineQuestion}`;
  const duplicate = /^dup_(L\d+)_(L\d+)$/.exec(key);
  if (duplicate?.[1] && duplicate[2]) return `${duplicate[2]} duplicates ${duplicate[1]}?`;
  return readable(key);
}

/** "s1.contract" is the agreement; "s1.invoice.inv-2026-04" is that invoice. */
export function requestLabel(purpose: string): DocumentLabel {
  if (purpose.endsWith('.contract')) return documentLabel('msa');
  return documentLabel(purpose.split('.').at(-1) ?? purpose);
}

type AnswersStep = Extract<StepData, { step: 'answers' }>;

function typedAnswers(data: AnswersStep): TypedAnswer[] {
  const choices = Object.entries(data.choices ?? {}).map(
    ([key, [answer, probability]]): TypedAnswer => ({
      key,
      question: questionLabel(key),
      answer,
      probability,
      confidence: probability,
      kind: 'choice',
    }),
  );
  const yesNo = Object.entries(data.nouls ?? {}).map(([key, probability]): TypedAnswer => ({
    key,
    question: questionLabel(key),
    answer: probability >= YES ? 'yes' : 'no',
    probability,
    confidence: Math.max(probability, 1 - probability),
    kind: 'yes_no',
  }));
  return [...choices, ...yesNo];
}

function withRequest(requests: readonly JevRequest[], purpose: string): JevRequest[] {
  if (requests.some((r) => r.purpose === purpose)) return [...requests];
  const fresh: JevRequest = {
    purpose,
    label: requestLabel(purpose),
    questions: null,
    latencyMs: null,
    answeredOrder: null,
    answers: [],
  };
  return [...requests, fresh];
}

function applyStep(pipeline: JevPipeline, data: StepData): JevPipeline {
  switch (data.step) {
    case 'candidates':
      return { ...pipeline, planned: { requests: data.requests, questions: data.questions } };
    case 'request_sent':
      return {
        ...pipeline,
        requests: withRequest(pipeline.requests, data.purpose).map((r) =>
          r.purpose === data.purpose ? { ...r, questions: data.questions ?? r.questions } : r,
        ),
      };
    case 'answers': {
      const purpose = data.purpose;
      if (purpose === undefined) return pipeline;
      const order = pipeline.requests.filter(isAnswered).length;
      return {
        ...pipeline,
        requests: withRequest(pipeline.requests, purpose).map((r) =>
          r.purpose === purpose
            ? {
                ...r,
                latencyMs: data.latency_ms,
                answeredOrder: r.answeredOrder ?? order,
                answers: typedAnswers(data),
              }
            : r,
        ),
      };
    }
    case 'computed':
      return { ...pipeline, computed: data.findings };
    case 'gated':
      return { ...pipeline, gated: { review: data.review, notes: data.notes ?? [] } };
    case 'done':
      return pipeline;
  }
}

export function isAnswered(request: JevRequest): boolean {
  return request.latencyMs !== null;
}

function stagesOf(p: Omit<JevPipeline, 'stages'>): JevPipeline['stages'] {
  const answered = p.requests.filter(isAnswered).length;
  const allAnswered = p.planned !== null && answered >= p.planned.requests;
  const later = p.computed !== null || p.gated !== null;
  const questions: StageState =
    allAnswered || later ? 'done' : p.requests.length > 0 ? 'active' : 'pending';
  return {
    candidates: p.planned ? 'done' : 'pending',
    questions,
    calculate: p.computed !== null ? 'done' : questions === 'done' ? 'active' : 'pending',
    gate: p.gated ? 'done' : p.computed !== null ? 'active' : 'pending',
  };
}

const EMPTY: Omit<JevPipeline, 'stages'> = {
  planned: null,
  requests: [],
  computed: null,
  gated: null,
};

export function jevPipeline(progress: SideProgress | null): JevPipeline {
  const folded = (progress?.steps ?? []).reduce<JevPipeline>(
    (pipeline, step) => applyStep(pipeline, step.data),
    { ...EMPTY, stages: stagesOf(EMPTY) },
  );
  return { ...folded, stages: stagesOf(folded) };
}
