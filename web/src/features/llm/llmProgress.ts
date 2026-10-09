/** What the LLM side has done so far, read from its step events. */
import type { StepData } from '../../api/events';
import type { SideProgress } from '../run/runReducer';

type AnswersStep = Extract<StepData, { step: 'answers' }>;

export type LlmState =
  | { readonly kind: 'idle' }
  | { readonly kind: 'waiting' }
  | {
      readonly kind: 'answered';
      readonly latencyMs: number;
      /** The model's refusal or the call's error, if there was no usable answer. */
      readonly problem: string | null;
    };

export function llmState(progress: SideProgress | null): LlmState {
  if (!progress) return { kind: 'idle' };
  const answers = progress.steps
    .map((step) => step.data)
    .find((data): data is AnswersStep => data.step === 'answers');
  if (answers) {
    return {
      kind: 'answered',
      latencyMs: answers.latency_ms,
      problem: answers.refusal ?? answers.error ?? null,
    };
  }
  return progress.steps.some((step) => step.data.step === 'request_sent')
    ? { kind: 'waiting' }
    : { kind: 'idle' };
}
