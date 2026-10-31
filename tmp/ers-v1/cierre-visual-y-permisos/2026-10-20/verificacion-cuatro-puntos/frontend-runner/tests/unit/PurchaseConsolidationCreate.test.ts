import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseConsolidationCreate from '$lib/features/purchase-requests/components/PurchaseConsolidationCreate.svelte';

const requestLinkedId = '11111111-1111-4111-8111-111111111111';
const requestEligibleId = '22222222-2222-4222-8222-222222222222';
const consolidationId = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';

const mocks = vi.hoisted(() => ({
  eligibleRequests: vi.fn(),
  resolveSelectedRequests: vi.fn(),
  create: vi.fn(),
  warehouses: vi.fn(),
  goto: vi.fn()
}));

vi.mock('$app/state', () => ({
  page: {
    url: new URL(
      `http://localhost/purchase-consolidations/new?request_ids=11111111-1111-4111-8111-111111111111%2C22222222-2222-4222-8222-222222222222`
    )
  }
}));
vi.mock('$app/navigation', () => ({ goto: mocks.goto }));
vi.mock('$lib/api/purchase-consolidations', () => ({
  purchaseConsolidationsApi: {
    eligibleRequests: mocks.eligibleRequests,
    resolveSelectedRequests: mocks.resolveSelectedRequests,
    create: mocks.create
  }
}));
vi.mock('$lib/api/client', () => ({
  api: { warehouses: { catalogue: mocks.warehouses } },
  HttpError: class HttpError extends Error {
    constructor(readonly code: string, message: string, readonly status: number) {
      super(message);
    }
  }
}));
vi.mock('$lib/stores/branch.svelte', () => ({
  branch: { id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', accessAllBranches: true, branches: [] }
}));

const eligibleCandidate = {
  id: requestEligibleId,
  code: 'SCR-00037',
  request_date: '2026-10-16T12:00:00Z',
  requester_name: 'Prueba',
  required_date: null,
  branch_id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
  branch_name: 'Sucursal de prueba',
  warehouse_id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
  warehouse_name: 'Bodega de prueba',
  line_count: 1,
  details: [{
    id: 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
    product_id: 10,
    product_sku: 'PRD-10',
    product_name: 'Producto de prueba',
    unit_id: 1,
    unit_name: 'Caja',
    quantity: '2',
    request_count: 1
  }]
};

describe('PurchaseConsolidationCreate selected request diagnostics', () => {
  beforeEach(() => {
    mocks.eligibleRequests.mockReset().mockImplementation(async (params: { request_ids?: string[] }) => ({
      items: [eligibleCandidate].filter((item) => !params.request_ids || params.request_ids.includes(item.id)),
      meta: { page: 1, size: 100, total: 1, pages: 1 }
    }));
    mocks.resolveSelectedRequests.mockReset().mockResolvedValue([
      {
        id: requestLinkedId,
        code: 'SCR-00035',
        eligibility: 'already_consolidated',
        consolidations: [{ id: consolidationId, code: 'CD-00005', status: 'draft' }]
      },
      {
        id: requestEligibleId,
        code: 'SCR-00037',
        eligibility: 'eligible',
        consolidations: []
      }
    ]);
    mocks.create.mockReset().mockResolvedValue({ id: 'bbbbbbbb-aaaa-4bbb-8bbb-bbbbbbbbbbbb' });
    mocks.warehouses.mockReset().mockResolvedValue([]);
    mocks.goto.mockReset();
  });

  it('explains an existing draft and lets the user remove only that local selection', async () => {
    render(PurchaseConsolidationCreate);

    expect(await screen.findByText('Ya incluida en CD-00005 · Borrador.')).toBeInTheDocument();
    const openLink = await screen.findByRole('link', { name: 'Abrir consolidado CD-00005' });
    expect(openLink).toHaveAttribute('href', `/purchase-consolidations/${consolidationId}`);
    expect(screen.getByRole('button', { name: 'Crear borrador' })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: 'Quitar SCR-00035 de esta selección' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Crear borrador' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: 'Crear borrador' }));

    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith(expect.objectContaining({
      request_ids: [requestEligibleId]
    })));
    expect(mocks.goto).toHaveBeenCalledWith('/purchase-consolidations/bbbbbbbb-aaaa-4bbb-8bbb-bbbbbbbbbbbb');
  });

  it('keeps a transient resolution failure retryable and does not call it a consolidated request', async () => {
    mocks.eligibleRequests.mockResolvedValue({ items: [], meta: { page: 1, size: 100, total: 0, pages: 0 } });
    mocks.resolveSelectedRequests
      .mockRejectedValueOnce(new Error('network unavailable'))
      .mockResolvedValueOnce([{
        id: requestLinkedId,
        code: 'SCR-00035',
        eligibility: 'already_consolidated',
        consolidations: [{ id: consolidationId, code: 'CD-00005', status: 'draft' }]
      }]);

    render(PurchaseConsolidationCreate);

    expect((await screen.findAllByText(/un fallo de consulta no significa que ya esté consolidada/)).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Ya incluida en/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Buscar' }));

    expect(await screen.findByText('Ya incluida en CD-00005 · Borrador.')).toBeInTheDocument();
  });
});
