import { describe, expect, it } from 'vitest';

import { splitCitations } from './citations';

describe('splitCitations', () => {
  it('splits memo text around its [Cn] markers', () => {
    expect(splitCitations('Rates match. [C1] Totals [C10].')).toEqual([
      'Rates match. ',
      { citationId: 'C1', text: '[C1]' },
      ' Totals ',
      { citationId: 'C10', text: '[C10]' },
      '.',
    ]);
  });

  it('leaves text without markers, and look-alikes, as one piece', () => {
    expect(splitCitations('Section [C] and [c2] and C3')).toEqual(['Section [C] and [c2] and C3']);
    expect(splitCitations('')).toEqual([]);
  });
});
