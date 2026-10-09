import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { TraceButton } from './TraceButton';
import { TraceLine } from './TraceLine';
import { TraceContext } from './traceContext';

const rect = (left: number, top: number, right: number, bottom: number) =>
  ({ left, top, right, bottom, width: right - left, height: bottom - top }) as DOMRect;

function setUp() {
  const from = document.createElement('button');
  const mark = document.createElement('mark');
  mark.dataset.highlights = 'other#0 f1#0';
  document.body.append(from, mark);
  vi.spyOn(from, 'getBoundingClientRect').mockReturnValue(rect(900, 400, 980, 420));
  vi.spyOn(mark, 'getBoundingClientRect').mockReturnValue(rect(100, 200, 160, 220));
  return { from, mark };
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  document.body.innerHTML = '';
});

describe('TraceLine', () => {
  it('draws from the figure to the passage after the scroll settles, then ends', () => {
    const { from } = setUp();
    const onDone = vi.fn();
    const { container } = render(<TraceLine from={from} highlightId="f1#0" onDone={onDone} />);

    expect(container.querySelector('path')).toBeNull();
    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(container.querySelector('path')).toHaveAttribute(
      'd',
      'M 900 410 C 530 410, 530 210, 160 210',
    );
    expect(onDone).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect(onDone).toHaveBeenCalled();
  });

  it('ends early when the page scrolls under a drawn line', () => {
    const { from } = setUp();
    const onDone = vi.fn();
    render(<TraceLine from={from} highlightId="f1#0" onDone={onDone} />);
    fireEvent.scroll(window); // before drawing: the viewer's own scroll, ignored
    expect(onDone).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(500);
    });
    fireEvent.scroll(window);

    expect(onDone).toHaveBeenCalledTimes(1);
  });

  it('draws anyway if something keeps scrolling', () => {
    const { from } = setUp();
    const { container } = render(<TraceLine from={from} highlightId="f1#0" onDone={vi.fn()} />);

    for (let elapsed = 0; elapsed < 1600; elapsed += 50) {
      fireEvent.scroll(window);
      act(() => {
        vi.advanceTimersByTime(50);
      });
      if (container.querySelector('path')) break;
    }

    expect(container.querySelector('path')).not.toBeNull();
  });

  it('draws nothing and ends when the passage is not on screen', () => {
    const { from } = setUp();
    const onDone = vi.fn();
    const { container } = render(<TraceLine from={from} highlightId="missing#0" onDone={onDone} />);

    act(() => {
      vi.advanceTimersByTime(500);
    });

    expect(container.querySelector('svg')).toBeNull();
    expect(onDone).toHaveBeenCalled();
  });
});

describe('TraceButton', () => {
  const target = { highlightId: 'f1#0', docId: 'inv-2026-04', quote: '$57,530.00' };

  it('is plain text where nothing can trace', () => {
    render(<TraceButton target={target}>$57,530.00</TraceButton>);

    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    expect(screen.getByText('$57,530.00')).toBeInTheDocument();
  });

  it('asks to trace its passage, from itself', async () => {
    vi.useRealTimers();
    const user = userEvent.setup();
    const trace = vi.fn();
    render(
      <TraceContext value={trace}>
        <TraceButton target={target}>$57,530.00</TraceButton>
      </TraceContext>,
    );

    const button = screen.getByRole('button', { name: '$57,530.00, show in Invoice INV-2026-04' });
    await user.click(button);

    expect(trace).toHaveBeenCalledWith(target, button);
  });
});
