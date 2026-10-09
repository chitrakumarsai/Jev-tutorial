/** Turns the evidence quoted by each side's findings into highlights, filed by document. */
import type { Highlight } from '../../lib/segments';
import type { RunView } from '../run/runReducer';

/** The id of a finding's i-th evidence span, shared by the viewer and the trace line. */
export function evidenceHighlightId(findingId: string, index: number): string {
  return `${findingId}#${String(index)}`;
}

export function highlightsByDocument(
  view: RunView | null,
): ReadonlyMap<string, readonly Highlight[]> {
  const byDoc = new Map<string, Highlight[]>();
  if (!view) return byDoc;
  for (const tone of ['jev', 'llm'] as const) {
    for (const finding of view.sides[tone].findings) {
      finding.evidence.forEach((span, i) => {
        const highlight: Highlight = {
          id: evidenceHighlightId(finding.id, i),
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
