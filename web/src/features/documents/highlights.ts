/** Turns the evidence quoted by each side's findings into highlights, filed by document. */
import type { Highlight } from '../../lib/segments';
import type { RunView } from '../run/runReducer';

export function highlightsByDocument(
  view: RunView | null,
): ReadonlyMap<string, readonly Highlight[]> {
  const byDoc = new Map<string, Highlight[]>();
  if (!view) return byDoc;
  for (const tone of ['jev', 'llm'] as const) {
    for (const finding of view.sides[tone].findings) {
      finding.evidence.forEach((span, i) => {
        const highlight: Highlight = {
          id: `${finding.id}#${String(i)}`,
          start: span.start,
          end: span.end,
          text: span.text,
          tone,
        };
        byDoc.set(span.doc_id, [...(byDoc.get(span.doc_id) ?? []), highlight]);
      });
    }
  }
  return byDoc;
}
