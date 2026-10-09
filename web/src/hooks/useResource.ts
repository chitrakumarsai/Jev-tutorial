/**
 * Loads data for a key (e.g. a scenario id) and aborts when the key changes or the
 * component unmounts. Only the key (or a new `revision`, for "try again") triggers a reload;
 * `load` may be an inline function.
 */
import { useEffect, useEffectEvent, useState } from 'react';

import { ApiRequestError } from '../api/client';
import type { ApiError } from '../api/types';

export type Resource<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ready'; data: T }
  | { status: 'error'; error: ApiError };

const LOADING: Resource<never> = { status: 'loading' };
const IDLE: Resource<never> = { status: 'idle' };

function toApiError(error: unknown): ApiError {
  if (error instanceof ApiRequestError) return { code: error.code, message: error.message };
  return { code: 'LOAD_FAILED', message: 'Something went wrong while loading.' };
}

export function useResource<T>(
  key: string | null,
  load: (key: string, signal: AbortSignal) => Promise<T>,
  revision = 0,
): Resource<T> {
  const [state, setState] = useState<{
    key: string | null;
    revision: number;
    resource: Resource<T>;
  }>({ key: null, revision, resource: IDLE });

  const start = useEffectEvent((forKey: string, signal: AbortSignal) => load(forKey, signal));

  useEffect(() => {
    if (key === null) return;
    const controller = new AbortController();
    start(key, controller.signal).then(
      (data) => {
        if (!controller.signal.aborted)
          setState({ key, revision, resource: { status: 'ready', data } });
      },
      (error: unknown) => {
        if (!controller.signal.aborted) {
          setState({ key, revision, resource: { status: 'error', error: toApiError(error) } });
        }
      },
    );
    return () => {
      controller.abort();
    };
  }, [key, revision]);

  if (key === null) return IDLE;
  // Until this key's load settles, show loading, never another key's (or attempt's) data.
  return state.key === key && state.revision === revision ? state.resource : LOADING;
}
