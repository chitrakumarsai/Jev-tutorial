import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ConfidenceRing } from './ConfidenceRing';

describe('ConfidenceRing', () => {
  it('says the confidence in words beside the ring', () => {
    render(<ConfidenceRing value={0.8} label="Lowest confidence" />);

    expect(screen.getByText(/80%/)).toHaveTextContent('Lowest confidence 80%');
  });

  it('keeps a value a hair out of range inside the ring', () => {
    render(<ConfidenceRing value={1.0000001} tone="review" />);

    expect(screen.getByText(/100%/)).toBeInTheDocument();
  });
});
