/**
 * Splits a document into plain and highlighted runs for the source viewer. Spans come from
 * the API in Python string offsets (code points), so the text is indexed by code point,
 * not UTF-16 unit. A span whose quoted text does not match the document is rejected:
 * highlighting the wrong words would be worse than highlighting none.
 */
export type HighlightTone = 'jev' | 'llm';

export interface Highlight {
  readonly id: string;
  readonly start: number;
  readonly end: number;
  readonly text: string;
  readonly tone: HighlightTone;
}

export interface Segment {
  readonly text: string;
  readonly highlights: readonly Highlight[];
}

export interface Segmented {
  readonly segments: readonly Segment[];
  readonly rejected: readonly Highlight[];
}

function fits(points: readonly string[], h: Highlight): boolean {
  return (
    Number.isInteger(h.start) &&
    Number.isInteger(h.end) &&
    h.start >= 0 &&
    h.end > h.start &&
    h.end <= points.length &&
    points.slice(h.start, h.end).join('') === h.text
  );
}

export function segmentText(text: string, highlights: readonly Highlight[]): Segmented {
  const points = Array.from(text);
  const accepted = highlights.filter((h) => fits(points, h));
  const rejected = highlights.filter((h) => !accepted.includes(h));
  const cuts = [...new Set([0, points.length, ...accepted.flatMap((h) => [h.start, h.end])])].sort(
    (a, b) => a - b,
  );
  const segments = cuts.slice(0, -1).map((from, i) => {
    const to = cuts[i + 1] ?? points.length;
    return {
      text: points.slice(from, to).join(''),
      highlights: accepted
        .filter((h) => h.start <= from && h.end >= to)
        .sort((a, b) => a.start - b.start || a.id.localeCompare(b.id)),
    };
  });
  return { segments: segments.length > 0 ? segments : [{ text, highlights: [] }], rejected };
}
