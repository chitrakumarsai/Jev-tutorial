/** Short tab labels ("MSA", "Apr") and full accessible names for the scenario documents. */
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export interface DocumentLabel {
  readonly short: string;
  readonly full: string;
}

export function documentLabel(docId: string): DocumentLabel {
  if (docId === 'msa') return { short: 'MSA', full: 'Master services agreement' };
  if (docId === 'addendum') return { short: 'Addendum', full: 'Data processing addendum' };
  const id = docId.toUpperCase();
  const month = /^inv-\d{4}-(\d{2})$/.exec(docId)?.[1];
  const name = month ? MONTHS[Number(month) - 1] : undefined;
  return name ? { short: name, full: `Invoice ${id}` } : { short: id, full: `Document ${id}` };
}
