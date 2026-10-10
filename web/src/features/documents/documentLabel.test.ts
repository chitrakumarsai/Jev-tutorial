import { describe, expect, it } from 'vitest';

import { documentLabel } from './documentLabel';

describe('documentLabel', () => {
  it.each([
    ['msa', { short: 'MSA', full: 'Master services agreement' }],
    ['inv-2026-01', { short: 'Jan', full: 'Invoice INV-2026-01' }],
    ['inv-2026-12', { short: 'Dec', full: 'Invoice INV-2026-12' }],
    ['inv-2026-13', { short: 'INV-2026-13', full: 'Document INV-2026-13' }],
    ['rider-a', { short: 'RIDER-A', full: 'Document RIDER-A' }],
  ])('labels %s', (docId, label) => {
    expect(documentLabel(docId)).toEqual(label);
  });

  it('names the S2 addendum', () => {
    expect(documentLabel('addendum')).toEqual({
      short: 'Addendum',
      full: 'Data processing addendum',
    });
  });
});
