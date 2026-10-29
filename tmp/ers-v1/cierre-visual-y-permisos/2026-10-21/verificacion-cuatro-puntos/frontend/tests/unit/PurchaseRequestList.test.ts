import { render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseRequestList from '$lib/features/purchase-requests/components/PurchaseRequestList.svelte';

const apiMocks = vi.hoisted(() => ({
  list: vi.fn()
}));

vi.mock('$lib/api/purchase-requests', () => ({
  purchaseRequestsApi: {
    list: apiMocks.list
  }
}));

describe('PurchaseRequestList', () => {
  beforeEach(() => {
    apiMocks.list.mockReset();
  });

  it('renders the empty state after loading an empty page', async () => {
    apiMocks.list.mockResolvedValue({
      items: [],
      meta: { page: 1, size: 20, total: 0, pages: 0 }
    });

    render(PurchaseRequestList);

    expect(await screen.findByText('No hay solicitudes para mostrar')).toBeInTheDocument();
    expect(apiMocks.list).toHaveBeenCalledWith({
      status: undefined,
      page: 1,
      size: 20
    });
  });

  it('renders a human-readable error and retry action', async () => {
    apiMocks.list.mockRejectedValue(new Error('Servicio no disponible'));

    render(PurchaseRequestList);

    expect(await screen.findByText('Servicio no disponible')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
  });
});
