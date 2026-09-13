import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({
  apiFetch: vi.fn()
}));

vi.mock('$lib/api/client', () => ({
  apiFetch: apiMocks.apiFetch
}));

import { purchaseRequestsApi } from '$lib/api/purchase-requests';

describe('purchaseRequestsApi', () => {
  beforeEach(() => {
    apiMocks.apiFetch.mockReset();
  });

  it('builds list filters using the backend contract', async () => {
    apiMocks.apiFetch.mockResolvedValue({
      items: [],
      meta: { page: 2, size: 20, total: 0, pages: 0 }
    });

    await purchaseRequestsApi.list({
      status: 'submitted',
      branch_id: '11111111-1111-1111-1111-111111111111',
      page: 2,
      size: 20
    });

    expect(apiMocks.apiFetch).toHaveBeenCalledWith(
      '/purchase-requests?status=submitted&branch_id=11111111-1111-1111-1111-111111111111&page=2&size=20'
    );
  });

  it('uses POST for workflow transitions', async () => {
    apiMocks.apiFetch.mockResolvedValue({});

    await purchaseRequestsApi.approve('22222222-2222-2222-2222-222222222222');

    expect(apiMocks.apiFetch).toHaveBeenCalledWith(
      '/purchase-requests/22222222-2222-2222-2222-222222222222/approve',
      { method: 'POST' }
    );
  });
});
