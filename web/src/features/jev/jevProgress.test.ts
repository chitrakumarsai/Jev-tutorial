import { describe, expect, it } from 'vitest';

import type { StepEvent } from '../../api/events';
import { completedView } from '../../test/fixtures/replay';
import type { SideProgress } from '../run/runReducer';
import { jevPipeline, questionLabel, requestLabel } from './jevProgress';

const step = (data: StepEvent['data']): StepEvent => ({
  seq: 1,
  t_ms: 1,
  type: 'step',
  side: 'jev',
  data,
});
const progress = (...steps: StepEvent[]): SideProgress => ({ steps, findings: [], result: null });

describe('questionLabel', () => {
  it.each([
    ['zone_a_rate', 'Zone A rate'],
    ['zone_a_rate__rev', 'Zone A rate, options reversed'],
    ['kind_L3', 'L3: what kind of line'],
    ['refinv_L5', 'L5: invoice referred to'],
    ['dup_L4_L5', 'L5 duplicates L4?'],
    ['mystery_L2', 'Mystery L2'],
    ['brand_new_question', 'Brand new question'],
  ])('reads %s as "%s"', (key, label) => {
    expect(questionLabel(key)).toBe(label);
  });
});

describe('requestLabel', () => {
  it('names the agreement and each invoice', () => {
    expect(requestLabel('s1.contract').short).toBe('MSA');
    expect(requestLabel('s1.invoice.inv-2026-04')).toEqual({
      short: 'Apr',
      full: 'Invoice INV-2026-04',
    });
  });
});

describe('jevPipeline', () => {
  it('starts with every stage pending', () => {
    expect(jevPipeline(null).stages).toEqual({
      candidates: 'pending',
      questions: 'pending',
      calculate: 'pending',
      gate: 'pending',
    });
  });

  it('moves through the stages as requests go out and come back', () => {
    const planned = step({ step: 'candidates', requests: 2, questions: 5 });
    const sent = step({ step: 'request_sent', purpose: 's1.contract', questions: 3 });
    const answered = step({
      step: 'answers',
      purpose: 's1.contract',
      latency_ms: 300,
      choices: { zone_a_rate: ['$1,250.00', 0.97] },
      nouls: { dup_L4_L5: 0.2 },
    });

    const asking = jevPipeline(progress(planned, sent));
    expect(asking.stages).toMatchObject({ candidates: 'done', questions: 'active' });
    expect(asking.requests).toEqual([
      expect.objectContaining({ purpose: 's1.contract', questions: 3, latencyMs: null }),
    ]);

    const oneBack = jevPipeline(progress(planned, sent, answered));
    expect(oneBack.stages.questions).toBe('active'); // one of two requests answered
    expect(oneBack.requests[0]?.answers).toEqual([
      expect.objectContaining({ key: 'zone_a_rate', answer: '$1,250.00', probability: 0.97 }),
      // P(yes) = 0.2 is a confident "no": confidence 0.8, not 0.2.
      expect.objectContaining({ key: 'dup_L4_L5', answer: 'no', kind: 'yes_no', confidence: 0.8 }),
    ]);
  });

  it('ignores an answers step without a purpose', () => {
    const pipeline = jevPipeline(progress(step({ step: 'answers', latency_ms: 1 })));

    expect(pipeline.requests).toEqual([]);
  });

  it('reads the whole recorded run', () => {
    const pipeline = jevPipeline(completedView().sides.jev);

    expect(pipeline.planned).toEqual({ requests: 13, questions: 71 });
    expect(pipeline.requests).toHaveLength(13);
    expect(pipeline.computed).toBe(14);
    expect(pipeline.gated).toEqual({ review: 0, notes: [] });
    expect(Object.values(pipeline.stages)).toEqual(['done', 'done', 'done', 'done']);
    const contract = pipeline.requests.find((r) => r.purpose === 's1.contract');
    expect(contract?.answers).toHaveLength(13);
    expect(contract?.answers.find((a) => a.key === 'late_fee_grace_days')?.probability).toBe(0.7);
  });
});
