import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';

import type { Highlight } from '../../lib/segments';
import { completedView, replayDocuments } from '../../test/fixtures/replay';
import { DocumentViewer } from './DocumentViewer';
import { highlightsByDocument } from './highlights';

function Harness({
  highlights = new Map<string, readonly Highlight[]>(),
}: {
  highlights?: ReadonlyMap<string, readonly Highlight[]>;
}) {
  const [selected, setSelected] = useState('msa');
  return (
    <DocumentViewer
      documents={replayDocuments}
      highlights={highlights}
      selected={selected}
      onSelect={setSelected}
    />
  );
}

describe('DocumentViewer', () => {
  it('is a labelled region with one tab per document', () => {
    render(<Harness />);

    expect(screen.getByRole('region', { name: 'Source documents' })).toBeInTheDocument();
    const tabs = screen.getAllByRole('tab');
    expect(tabs).toHaveLength(13);
    expect(tabs[0]).toHaveAccessibleName('MSA Master services agreement');
    expect(tabs[4]).toHaveAccessibleName('Apr Invoice INV-2026-04');
  });

  it('shows the selected document as plain text', () => {
    render(<Harness />);

    const panel = screen.getByRole('tabpanel', { name: /MSA/ });
    expect(panel).toHaveTextContent('Master Services Agreement — Freight Transportation');
    expect(panel).toHaveTextContent('**Agreement No.**'); // markdown is shown, never rendered as HTML
    expect(within(panel).queryByRole('heading')).toBeNull();
  });

  it('moves between documents with the arrow keys, Home and End', async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const tabs = screen.getAllByRole('tab');

    await user.click(tabs[0] as HTMLElement);
    await user.keyboard('{ArrowRight}');
    expect(screen.getByRole('tab', { name: /^Jan/ })).toHaveFocus();
    expect(screen.getByRole('tab', { name: /^Jan/ })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tabpanel')).toHaveTextContent('Invoice INV-2026-01');

    await user.keyboard('{End}');
    expect(screen.getByRole('tab', { name: /^Dec/ })).toHaveFocus();
    await user.keyboard('{ArrowRight}');
    expect(screen.getByRole('tab', { name: /^MSA/ })).toHaveFocus();
    await user.keyboard('{ArrowLeft}');
    expect(screen.getByRole('tab', { name: /^Dec/ })).toHaveFocus();
    await user.keyboard('{Home}');
    expect(screen.getByRole('tab', { name: /^MSA/ })).toHaveAttribute('aria-selected', 'true');
  });

  it('leaves modified arrows (browser back/forward) alone', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole('tab', { name: /^MSA/ }));
    await user.keyboard('{Alt>}{ArrowRight}{/Alt}');

    expect(screen.getByRole('tab', { name: /^MSA/ })).toHaveAttribute('aria-selected', 'true');
  });

  it('keeps only the selected tab in the tab order', () => {
    render(<Harness />);

    const focusable = screen.getAllByRole('tab').filter((tab) => tab.tabIndex === 0);
    expect(focusable).toHaveLength(1);
    expect(focusable[0]).toHaveAttribute('aria-selected', 'true');
  });

  it("marks each side's quotes and counts them on the tabs", async () => {
    const user = userEvent.setup();
    render(<Harness highlights={highlightsByDocument(completedView())} />);

    expect(screen.getByRole('tab', { name: /^MSA/ })).toHaveAccessibleName(
      'MSA Master services agreement 7 quoted passages',
    );
    expect(screen.getByRole('tab', { name: /^Jan/ })).not.toHaveTextContent('quoted passages');

    const panel = screen.getByRole('tabpanel');
    const marks = panel.querySelectorAll('mark');
    expect(marks.length).toBeGreaterThan(0);
    // In the MSA both sides quote the same terms; the mark says so in words, not only style.
    expect(panel.querySelector('mark.quote--both')).toHaveTextContent(/^Quoted by Jev and LLM:/);

    await user.click(screen.getByRole('tab', { name: /^Oct/ }));
    const octMarks = screen.getByRole('tabpanel').querySelectorAll('mark');
    expect(octMarks).toHaveLength(4);
    expect([...octMarks].every((mark) => mark.classList.contains('quote--jev'))).toBe(true);
  });

  it('says when quoted passages could not be placed', () => {
    const misplaced: Highlight = { id: 'x', start: 0, end: 5, text: 'Nope!', tone: 'llm' };
    render(<Harness highlights={new Map([['msa', [misplaced]]])} />);

    expect(screen.getByRole('status')).toHaveTextContent(
      /1 quoted passage could not be found in this document/,
    );
    expect(screen.getByRole('tabpanel').querySelector('mark')).toBeNull();
  });
});
