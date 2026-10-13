import { createContext } from 'react';

/** The citation picked in the memo (e.g. "C3"), whose ledger rows are marked current. */
export const CitationFocusContext = createContext<string | null>(null);
