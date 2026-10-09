import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { completedView } from '../../test/fixtures/replay';
import { SidePane } from './SidePane';

describe('SidePane', () => {
  it('is a region named for its side, showing the model', () => {
    render(<SidePane side="jev" model="jev-latest" progress={null} />);

    const pane = screen.getByRole('region', { name: 'Jev + code' });
    expect(pane).toHaveTextContent('jev-latest');
    expect(pane).toHaveTextContent('Not run yet');
  });

  it('counts findings as they arrive', () => {
    render(<SidePane side="llm" model="gpt-6-luna" progress={completedView().sides.llm} />);

    expect(screen.getByRole('region', { name: 'Plain LLM' })).toHaveTextContent('18 findings');
  });

  it('shows extra content such as the exact prompt', () => {
    render(
      <SidePane side="llm" model="gpt-6-luna" progress={null}>
        <p>prompt here</p>
      </SidePane>,
    );

    expect(screen.getByText('prompt here')).toBeInTheDocument();
  });
});
