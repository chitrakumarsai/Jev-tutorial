import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  ApiRequestError,
  MAX_MESSAGE_LENGTH,
  getBudget,
  getRun,
  getScenarios,
  runEventsUrl,
  startRun,
} from './client';

const fetchMock = vi.fn<typeof fetch>();

function respond(status: number, body: unknown, contentType = 'application/json'): void {
  const text = typeof body === 'string' ? body : JSON.stringify(body);
  fetchMock.mockResolvedValueOnce(
    new Response(text, { status, headers: { 'Content-Type': contentType } }),
  );
}

function lastCall(): [string, RequestInit] {
  const call = fetchMock.mock.lastCall;
  if (!call) throw new Error('fetch was not called');
  return [call[0] as string, call[1] ?? {}];
}

async function failure(promise: Promise<unknown>): Promise<ApiRequestError> {
  const error: unknown = await promise.then(
    () => new Error('expected a failure'),
    (reason: unknown) => reason,
  );
  if (!(error instanceof ApiRequestError)) throw error;
  return error;
}

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  fetchMock.mockReset();
  vi.unstubAllGlobals();
});

const scenarios = [
  { id: 's1_reconciliation', title: 'Freight reconciliation', description: 'Twelve invoices' },
];

describe('api client', () => {
  it('returns the data of a success envelope', async () => {
    respond(200, { success: true, data: scenarios, error: null });

    await expect(getScenarios()).resolves.toEqual(scenarios);
    const [url, init] = lastCall();
    expect(url).toBe('/api/scenarios');
    expect(new Headers(init.headers).get('Accept')).toBe('application/json');
  });

  it('passes the abort signal through', async () => {
    respond(200, { success: true, data: scenarios, error: null });
    const controller = new AbortController();

    await getScenarios({ signal: controller.signal });

    expect(lastCall()[1].signal).toBe(controller.signal);
  });

  it('posts a run request as JSON', async () => {
    respond(202, { success: true, data: { run_id: 'r1' }, error: null });

    await expect(
      startRun({ scenario_id: 's1_reconciliation', mode: 'replay', pace: true }),
    ).resolves.toEqual({ run_id: 'r1' });
    const [url, init] = lastCall();
    expect(url).toBe('/api/runs');
    expect(init.method).toBe('POST');
    expect(new Headers(init.headers).get('Content-Type')).toBe('application/json');
    expect(JSON.parse(init.body as string)).toEqual({
      scenario_id: 's1_reconciliation',
      mode: 'replay',
      pace: true,
    });
  });

  it.each(['..', '../budget?x=1', 'a/b', '', 'x'.repeat(65)])(
    'refuses %j as an id without calling the API',
    async (id) => {
      const error = await failure(getRun(id));

      expect(error).toMatchObject({ status: 0, code: 'INVALID_ID' });
      expect(fetchMock).not.toHaveBeenCalled();
      expect(() => runEventsUrl(id)).toThrow(ApiRequestError);
    },
  );

  it('builds paths from valid ids', () => {
    expect(runEventsUrl('3f2a9c_d-1')).toBe('/api/runs/3f2a9c_d-1/events');
  });

  it('caps a long server message', async () => {
    respond(500, {
      success: false,
      data: null,
      error: { code: 'X', message: 'm'.repeat(5000) },
    });

    const error = await failure(getBudget());

    expect(error.message.length).toBeLessThanOrEqual(MAX_MESSAGE_LENGTH);
  });

  it('turns a failure envelope into an ApiRequestError', async () => {
    respond(403, {
      success: false,
      data: null,
      error: { code: 'LIVE_DISABLED', message: 'Live mode is off.' },
    });

    const error = await failure(
      startRun({ scenario_id: 's1_reconciliation', mode: 'live', pace: true }),
    );

    expect(error).toMatchObject({
      status: 403,
      code: 'LIVE_DISABLED',
      message: 'Live mode is off.',
    });
  });

  it.each([
    ['a non-JSON body (a proxy error page)', 502, '<html>Bad gateway: SECRET</html>', 'text/html'],
    ['JSON that is not an envelope', 200, { ok: true, note: 'SECRET' }, 'application/json'],
    [
      'an envelope with data of the wrong shape',
      200,
      { success: true, data: { totals: 'SECRET' }, error: null },
      'application/json',
    ],
  ])('reports %s as BAD_RESPONSE without echoing it', async (_label, status, body, type) => {
    respond(status, body, type);

    const error = await failure(getBudget());

    expect(error).toMatchObject({ status, code: 'BAD_RESPONSE' });
    expect(error.message).not.toContain('SECRET');
  });

  it('reports a network failure as NETWORK', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'));

    const error = await failure(getScenarios());

    expect(error).toMatchObject({ status: 0, code: 'NETWORK' });
  });

  it('lets an abort through unchanged, so callers can ignore it', async () => {
    const abort = new DOMException('The operation was aborted.', 'AbortError');
    fetchMock.mockRejectedValueOnce(abort);

    await expect(getScenarios()).rejects.toBe(abort);
  });
});
