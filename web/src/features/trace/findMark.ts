/** The marked passage carrying this highlight id (see DocumentViewer), or null. */
export function findMark(root: ParentNode, highlightId: string): HTMLElement | null {
  const marks = root.querySelectorAll<HTMLElement>('mark[data-highlights]');
  return (
    Array.from(marks).find((mark) => mark.dataset.highlights?.split(' ').includes(highlightId)) ??
    null
  );
}
