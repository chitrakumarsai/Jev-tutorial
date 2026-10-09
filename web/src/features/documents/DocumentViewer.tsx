import { useEffect, useEffectEvent, useId, useMemo, useRef, type KeyboardEvent } from 'react';

import type { DocumentText } from '../../api/types';
import { useReducedMotion } from '../../hooks/useReducedMotion';
import { findMark } from '../trace/findMark';
import { segmentText, type Highlight, type Segment } from '../../lib/segments';
import { documentLabel } from './documentLabel';
import './documents.css';

type Props = {
  documents: readonly DocumentText[];
  /** Quoted evidence per document id. */
  highlights: ReadonlyMap<string, readonly Highlight[]>;
  selected: string;
  onSelect: (docId: string) => void;
  /** A passage to bring into view and outline; `seq` changes on every request, even a repeat. */
  focus?: { readonly highlightId: string; readonly seq: number } | null;
};

const NO_HIGHLIGHTS: readonly Highlight[] = [];

/** Several findings often cite the same words; count each passage once. */
function distinctPassages(list: readonly Highlight[]): number {
  return new Set(list.map((h) => `${String(h.start)}:${String(h.end)}`)).size;
}

function quoteClass(segment: Segment, focusId: string | undefined): string {
  const tones = new Set(segment.highlights.map((h) => h.tone));
  const tone = tones.size > 1 ? 'both' : (segment.highlights[0]?.tone ?? 'jev');
  const isFocused = focusId !== undefined && segment.highlights.some((h) => h.id === focusId);
  return `quote quote--${tone}${isFocused ? ' quote--focused' : ''}`;
}

/** Says whose quote it is in words, since style alone doesn't reach a screen reader. */
function quotedBy(segment: Segment): string {
  const tones = new Set(segment.highlights.map((h) => h.tone));
  const sides = [tones.has('jev') && 'Jev', tones.has('llm') && 'LLM'].filter(Boolean);
  return `Quoted by ${sides.join(' and ')}`;
}

/** Tabs per WAI-ARIA APG (automatic activation): arrows, Home and End move and select. */
export function DocumentViewer({ documents, highlights, selected, onSelect, focus = null }: Props) {
  const baseId = useId();
  const tabRefs = useRef(new Map<string, HTMLButtonElement>());
  const textRef = useRef<HTMLPreElement>(null);
  const isReduced = useReducedMotion();
  const current = documents.find((d) => d.doc_id === selected) ?? documents[0];
  const currentText = current?.text ?? '';
  const currentHighlights = current
    ? (highlights.get(current.doc_id) ?? NO_HIGHLIGHTS)
    : NO_HIGHLIGHTS;
  const { segments, rejected } = useMemo(
    () => segmentText(currentText, currentHighlights),
    [currentText, currentHighlights],
  );

  const scrollToPassage = useEffectEvent((highlightId: string) => {
    const mark = textRef.current ? findMark(textRef.current, highlightId) : null;
    // jsdom has no scrollIntoView; browsers do.
    if (typeof mark?.scrollIntoView === 'function') {
      mark.scrollIntoView({ block: 'nearest', behavior: isReduced ? 'auto' : 'smooth' });
    }
  });

  // Only a new trace request (a new `seq`) scrolls; switching tabs later must not.
  useEffect(() => {
    if (focus) scrollToPassage(focus.highlightId);
  }, [focus]);

  const tabId = (docId: string) => `${baseId}-tab-${docId}`;
  const panelId = `${baseId}-panel`;

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    // Leave Alt+Arrow (browser back/forward) and other shortcuts to the browser.
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
    const index = documents.findIndex((d) => d.doc_id === current?.doc_id);
    const last = documents.length - 1;
    const target = {
      ArrowRight: index === last ? 0 : index + 1,
      ArrowLeft: index === 0 ? last : index - 1,
      Home: 0,
      End: last,
    }[event.key];
    const next = target === undefined ? undefined : documents[target];
    if (!next) return;
    event.preventDefault();
    onSelect(next.doc_id);
    tabRefs.current.get(next.doc_id)?.focus();
  };

  return (
    <section className="source" aria-labelledby={`${baseId}-heading`}>
      <h2 id={`${baseId}-heading`} className="pane-heading">
        Source documents
      </h2>
      <div role="tablist" aria-label="Documents" className="source__tabs" onKeyDown={handleKeyDown}>
        {documents.map((doc) => {
          const label = documentLabel(doc.doc_id);
          const count = distinctPassages(highlights.get(doc.doc_id) ?? NO_HIGHLIGHTS);
          const isSelected = doc.doc_id === current?.doc_id;
          return (
            <button
              key={doc.doc_id}
              ref={(node) => {
                if (node) tabRefs.current.set(doc.doc_id, node);
                else tabRefs.current.delete(doc.doc_id);
              }}
              type="button"
              role="tab"
              id={tabId(doc.doc_id)}
              aria-selected={isSelected}
              aria-controls={panelId}
              tabIndex={isSelected ? 0 : -1}
              className="source__tab"
              onClick={() => {
                onSelect(doc.doc_id);
              }}
            >
              <span>{label.short}</span> <span className="visually-hidden">{label.full}</span>
              {count > 0 && ' '}
              {count > 0 && (
                <span className="source__count">
                  {count} <span className="visually-hidden">quoted passages</span>
                </span>
              )}
            </button>
          );
        })}
      </div>
      <p className="source__legend" aria-hidden="true">
        <span className="quote quote--jev">Jev</span>
        <span className="quote quote--llm">LLM</span>
        <span className="quote quote--both">both</span>
      </p>
      <div
        role="tabpanel"
        id={panelId}
        aria-labelledby={current ? tabId(current.doc_id) : undefined}
        tabIndex={0}
        className="source__panel ledger-ruled"
      >
        {rejected.length > 0 && (
          <p className="source__notice" role="status">
            {rejected.length === 1
              ? '1 quoted passage could not be found in this document, so it is not marked.'
              : `${String(rejected.length)} quoted passages could not be found in this document, so they are not marked.`}
          </p>
        )}
        <pre ref={textRef} className="source__text">
          {segments.map((segment, i) =>
            segment.highlights.length === 0 ? (
              segment.text
            ) : (
              // Segments are positional and never reorder, so the index is a stable key.
              <mark
                key={i}
                className={quoteClass(segment, focus?.highlightId)}
                data-highlights={segment.highlights.map((h) => h.id).join(' ')}
              >
                <span className="visually-hidden">{`${quotedBy(segment)}: `}</span>
                {segment.text}
              </mark>
            ),
          )}
        </pre>
      </div>
    </section>
  );
}
