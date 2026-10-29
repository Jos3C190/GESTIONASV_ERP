import { afterEach, beforeEach, expect, it, vi } from 'vitest';

const state = vi.hoisted(() => ({
  session: { token: 'old-token', clear: vi.fn(), setToken: vi.fn() },
  company: { id: 'company-lorena' },
  branch: { id: 'branch-matriz' }
}));
vi.mock('$app/environment', () => ({ browser: true }));
vi.mock('$lib/stores/session.svelte', () => ({ session: state.session }));
vi.mock('$lib/stores/company.svelte', () => ({ company: state.company }));
vi.mock('$lib/stores/branch.svelte', () => ({ branch: state.branch }));
import { apiDownload } from '$lib/api/client';

beforeEach(() => {
  state.session.token = 'old-token';
  state.session.setToken.mockImplementation((value: string) => {
    state.session.token = value;
  });
});
afterEach(() => vi.unstubAllGlobals());

it('downloads bytes with the selected company and branch headers', async () => {
  const fetch = vi.fn<typeof globalThis.fetch>(
    async () => new Response('%PDF-test', { headers: { 'Content-Type': 'application/pdf' } })
  );
  vi.stubGlobal('fetch', fetch);
  const blob = await apiDownload('/retaceos/ret/export?format=pdf');
  expect(blob.type).toBe('application/pdf');
  expect(fetch.mock.calls[0]![1]).toMatchObject({
    credentials: 'include',
    headers: {
      Authorization: 'Bearer old-token',
      'X-Company-ID': 'company-lorena',
      'X-Branch-ID': 'branch-matriz'
    }
  });
});

it('refreshes an expired session and decodes the retry as a file', async () => {
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(new Response(null, { status: 401 }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ access_token: 'new-token' })))
    .mockResolvedValueOnce(
      new Response('xlsx-data', {
        headers: {
          'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }
      })
    );
  vi.stubGlobal('fetch', fetch);
  const blob = await apiDownload('/retaceos/ret/export?format=xlsx');
  expect(blob.size).toBe(9);
  expect(fetch).toHaveBeenCalledTimes(3);
  expect(state.session.setToken).toHaveBeenCalledWith('new-token');
  expect(fetch.mock.calls[2]![1].headers['X-Company-ID']).toBe('company-lorena');
});
