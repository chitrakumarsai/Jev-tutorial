import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { App } from './App';

describe('App', () => {
  it('renders the product name as the main heading inside a banner', () => {
    render(<App />);

    const banner = screen.getByRole('banner');
    expect(banner).toContainElement(
      screen.getByRole('heading', { level: 1, name: 'Jev Audit Lens' }),
    );
  });

  it('offers the theme choice in the masthead', () => {
    render(<App />);

    expect(screen.getByRole('banner')).toContainElement(
      screen.getByRole('radiogroup', { name: 'Theme' }),
    );
  });

  it('has a main landmark for the comparison', () => {
    render(<App />);

    expect(screen.getByRole('main')).toBeInTheDocument();
  });
});
