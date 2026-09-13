import { render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseRequestDetail from '$lib/features/purchase-requests/components/PurchaseRequestDetail.svelte';

const apiMocks = vi.hoisted(() => ({
  get: vi.fn()
}));

vi.mock('$lib/api/purchase-requests', () => ({
  purchaseRequestsApi: {
    get: apiMocks.get
  }
}));

const request = {
  id: '11111111-1111-1111-1111-111111111111',
  company_id: '22222222-2222-2222-2222-222222222222',
  code: 'SC-0001',
  branch_id: '33333333-3333-3333-3333-333333333333',
  warehouse_id: '44444444-4444-4444-4444-444444444444',
  requested_by_id: '55555555-5555-5555-5555-555555555555',
  request_date: '2026-09-12T15:00:00Z',
  required_date: '2026-09-20T15:00:00Z',
  justification: 'Reposición de inventario',
  status: 'submitted',
  notes: null,
  details: [
    {
      id: '66666666-6666-6666-6666-666666666666',
      purchase_request_id: '11111111-1111-1111-1111-111111111111',
      product_id: 10,
      unit_id: 2,
      quantity: '5.000000',
      description: 'Producto requerido',
      notes: null,
      created_at: null,
      updated_at: null
    }
  ],
  created_at: null,
  updated_at: null
} as const;

describe('PurchaseRequestDetail', () => {
  beforeEach(() => {
    apiMocks.get.mockReset();
  });

  it('loads and renders the purchase request contract', async () => {
    apiMocks.get.mockResolvedValue(request);

    render(PurchaseRequestDetail, {
      props: { requestId: request.id }
    });

    expect(await screen.findByText('SC-0001')).toBeInTheDocument();
    expect(screen.getByText('Reposición de inventario')).toBeInTheDocument();
    expect(screen.getByText('Enviada')).toBeInTheDocument();
    expect(screen.getByText('5.000000')).toBeInTheDocument();
    expect(apiMocks.get).toHaveBeenCalledWith(request.id);
  });

  it('shows an error with a retry action', async () => {
    apiMocks.get.mockRejectedValue(new Error('Solicitud no disponible'));

    render(PurchaseRequestDetail, {
      props: { requestId: request.id }
    });

    expect(await screen.findByText('Solicitud no disponible')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
  });
});
