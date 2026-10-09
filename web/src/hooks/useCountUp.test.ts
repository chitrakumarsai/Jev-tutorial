import { renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { useCountUp } from './useCountUp';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('useCountUp', () => {
  it('starts from zero and settles on the exact figure', async () => {
    const { result } = renderHook(() => useCountUp('98510.71'));

    expect(result.current).toBe('$0.00');
    await waitFor(
      () => {
        expect(result.current).toBe('$98,510.71');
      },
      { timeout: 3000 },
    );
  });

  it('shows the exact figure at once with reduced motion', () => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
    );

    const { result } = renderHook(() => useCountUp('10460.00'));

    expect(result.current).toBe('$10,460.00');
  });
});
