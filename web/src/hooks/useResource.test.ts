import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ApiRequestError } from '../api/client';
import { useResource } from './useResource';

function deferred<T>() {
  let resolve: (value: T) => void = () => undefined;
  let reject: (reason: unknown) => void = () => undefined;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe('useResource', () => {
  it('stays idle without a key', () => {
    const load = vi.fn<(key: string, signal: AbortSignal) => Promise<string>>();

    expect(renderHook(() => useResource(null, load)).result.current).toEqual({ status: 'idle' });
    expect(load).not.toHaveBeenCalled();
  });

  it('loads, then holds the data', async () => {
    const pending = deferred<string>();
    const load = vi.fn(() => pending.promise);
    const { result } = renderHook(() => useResource('s1', load));
    expect(result.current).toEqual({ status: 'loading' });

    await act(async () => {
      pending.resolve('data');
      await pending.promise;
    });

    expect(result.current).toEqual({ status: 'ready', data: 'data' });
    expect(load).toHaveBeenCalledWith('s1', expect.any(AbortSignal));
  });

  it('turns a failure into a displayable error', async () => {
    const pending = deferred<string>();
    const { result } = renderHook(() => useResource('s1', () => pending.promise));

    await act(async () => {
      pending.reject(new ApiRequestError(404, 'UNKNOWN_SCENARIO', 'Unknown scenario'));
      await pending.promise.catch(() => undefined);
    });

    expect(result.current).toEqual({
      status: 'error',
      error: { code: 'UNKNOWN_SCENARIO', message: 'Unknown scenario' },
    });
  });

  it('describes an unexpected failure without echoing it', async () => {
    const pending = deferred<string>();
    const { result } = renderHook(() => useResource('s1', () => pending.promise));

    await act(async () => {
      pending.reject(new Error('SECRET internals'));
      await pending.promise.catch(() => undefined);
    });

    expect(result.current.status).toBe('error');
    expect(JSON.stringify(result.current)).not.toContain('SECRET');
  });

  it('does not reload when only the load function changes', () => {
    const load = vi.fn(() => new Promise<string>(() => undefined));
    const { rerender } = renderHook(() => useResource('s1', () => load()));

    rerender();
    rerender();

    expect(load).toHaveBeenCalledTimes(1);
  });

  it('aborts the old load and never shows its data under a new key', async () => {
    const first = deferred<string>();
    const signals: AbortSignal[] = [];
    const load = vi.fn((key: string, signal: AbortSignal) => {
      signals.push(signal);
      return key === 'a' ? first.promise : new Promise<string>(() => undefined);
    });
    const { result, rerender } = renderHook(({ key }) => useResource(key, load), {
      initialProps: { key: 'a' },
    });

    rerender({ key: 'b' });
    await act(async () => {
      first.resolve('stale');
      await first.promise;
    });

    expect(signals[0]?.aborted).toBe(true);
    expect(result.current).toEqual({ status: 'loading' });
  });
});
