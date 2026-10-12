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

describe('S2 clause review', () => {
  it('names the clause request and its three questions per clause', () => {
    expect(requestLabel('s2.clauses')).toEqual({
      short: 'Clauses',
      full: 'Clause checklist',
    });
    expect(questionLabel('limitation_of_liability__where')).toBe(
      'Limitation of liability: which line',
    );
    expect(questionLabel('audit_rights__status')).toBe('Audit rights: is it there');
    expect(questionLabel('insurance__risk')).toBe('Insurance: risk level');
  });

  it('shows Jev’s risk answers alongside its choices', () => {
    const pipeline = jevPipeline(
      progress(
        step({ step: 'candidates', requests: 1, questions: 3 }),
        step({ step: 'request_sent', purpose: 's2.clauses', questions: 3 }),
        step({
          step: 'answers',
          purpose: 's2.clauses',
          latency_ms: 360,
          choices: {
            insurance__where: ['L055', 0.9],
            insurance__status: ['partial', 0.92],
          },
          scores: { insurance__risk: ['high', 0.88] },
        }),
      ),
    );

    const answers = pipeline.requests[0]?.answers ?? [];
    expect(answers.map((a) => [a.question, a.answer, a.confidence])).toEqual([
      ['Insurance: which line', 'L055', 0.9],
      ['Insurance: is it there', 'partial', 0.92],
      ['Insurance: risk level', 'high', 0.88],
    ]);
  });
});
