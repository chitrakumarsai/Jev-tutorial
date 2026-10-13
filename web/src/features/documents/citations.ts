/** A memo's citation marker, e.g. "[C3]". */
export interface CitationMarker {
  readonly citationId: string;
  readonly text: string;
}

const MARKER = /\[(C\d+)\]/g;

/** Splits text around its [Cn] markers, keeping every character in order. */
export function splitCitations(text: string): (string | CitationMarker)[] {
  const pieces: (string | CitationMarker)[] = [];
  let last = 0;
  for (const match of text.matchAll(MARKER)) {
    const [marker, citationId] = match;
    if (match.index > last) pieces.push(text.slice(last, match.index));
    if (citationId) pieces.push({ citationId, text: marker });
    last = match.index + marker.length;
  }
  if (last < text.length) pieces.push(text.slice(last));
  return pieces;
}
