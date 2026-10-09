import { describe, expect, it } from 'vitest';

import { completedView } from '../../test/fixtures/replay';
import { initialRunView } from '../run/runReducer';
import { highlightsByDocument } from './highlights';

describe('highlightsByDocument', () => {
  it('is empty before any finding arrives', () => {
    expect(highlightsByDocument(null).size).toBe(0);
    expect(highlightsByDocument(initialRunView('r1')).size).toBe(0);
  });

  it("files each finding's evidence under its document, toned by side", () => {
    const byDoc = highlightsByDocument(completedView());

    expect(byDoc.get('msa')?.filter((h) => h.tone === 'jev')).toHaveLength(25);
    expect(byDoc.get('msa')?.filter((h) => h.tone === 'llm')).toHaveLength(17);
    expect(byDoc.get('inv-2026-10')).toHaveLength(4);
    expect(byDoc.has('inv-2026-01')).toBe(false);
  });

  it('gives every highlight a distinct id', () => {
    const all = [...highlightsByDocument(completedView()).values()].flat();

    expect(new Set(all.map((h) => h.id)).size).toBe(all.length);
  });
});
