import { splitCitations } from './citations';

type Props = {
  text: string;
  /** Without a listener, markers stay plain text. */
  onCitation?: ((citationId: string) => void) | undefined;
};

/** Text whose [Cn] markers are buttons that show that citation's ledger rows. */
export function CitationText({ text, onCitation }: Props) {
  if (!onCitation) return text;
  // Pieces are positional and never reorder, so the index is a stable key.
  return splitCitations(text).map((piece, i) =>
    typeof piece === 'string' ? (
      piece
    ) : (
      <button
        key={i}
        type="button"
        className="citation-marker"
        // The name starts with what is on screen, so a speech user can say it.
        aria-label={`${piece.citationId}, show in the ledgers`}
        onClick={() => {
          onCitation(piece.citationId);
        }}
      >
        {piece.text}
      </button>
    ),
  );
}
