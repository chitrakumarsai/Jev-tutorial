import { describe, expect, it } from 'vitest';

import { segmentText, type Highlight } from './segments';

const span = (
  start: number,
  end: number,
  text: string,
  extra: Partial<Highlight> = {},
): Highlight => ({
  id: `${String(start)}-${String(end)}`,
  start,
  end,
  text,
  tone: 'jev',
  ...extra,
});

describe('segmentText', () => {
  it('returns the whole text when nothing is highlighted', () => {
    expect(segmentText('Zone A: $1,250.00', [])).toEqual({
      segments: [{ text: 'Zone A: $1,250.00', highlights: [] }],
      rejected: [],
    });
  });

  it('cuts the text around a highlight', () => {
    const h = span(8, 17, '$1,250.00');

    expect(segmentText('Zone A: $1,250.00 per Load', [h]).segments).toEqual([
      { text: 'Zone A: ', highlights: [] },
      { text: '$1,250.00', highlights: [h] },
      { text: ' per Load', highlights: [] },
    ]);
  });

  it('stacks overlapping highlights from both sides', () => {
    const jev = span(0, 6, 'Zone A', { id: 'j', tone: 'jev' });
    const llm = span(5, 9, 'A: $', { id: 'l', tone: 'llm' });

    expect(segmentText('Zone A: $1', [llm, jev]).segments).toEqual([
      { text: 'Zone ', highlights: [jev] },
      { text: 'A', highlights: [jev, llm] },
      { text: ': $', highlights: [llm] },
      { text: '1', highlights: [] },
    ]);
  });

  it('counts offsets in code points, as Python does', () => {
    // "𝟙" is one code point but two UTF-16 units: a naive slice would cut it in half.
    const h = span(2, 5, '$12');

    expect(segmentText('𝟙 $12', [h]).segments.map((s) => s.text)).toEqual(['𝟙 ', '$12']);
  });

  it.each([
    ['text that does not match the document', span(0, 4, 'Zone')],
    ['an end past the document', span(10, 99, 'x')],
    ['an empty span', span(3, 3, '')],
    ['a negative start', span(-1, 2, 'Zo')],
  ])('rejects %s instead of highlighting the wrong words', (_label, bad) => {
    const result = segmentText('Line haul, Zone B', [bad]);

    expect(result.rejected).toEqual([bad]);
    expect(result.segments).toEqual([{ text: 'Line haul, Zone B', highlights: [] }]);
  });
});
