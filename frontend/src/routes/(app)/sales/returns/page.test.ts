import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { listReturns } = vi.hoisted(() => ({ listReturns: vi.fn() }));

vi.mock('$lib/api/sales', () => ({ salesApi: { returns: listReturns } }));
vi.mock('$lib/api/client', () => ({ HttpError: class HttpError extends Error {} }));
vi.mock('$lib/stores/branch.svelte', () => ({ branch: { id: null, label: 'Todas las sucursales' } }));

import SalesReturnsList from './+page.svelte';
import type { SalesReturn } from '$lib/types/sales';

function document(status: SalesReturn['status'], code = 'DEV-00001'): SalesReturn {
  return {
    id: 'return-1', company_id: 'company-1', branch_id: 'branch-1', sale_id: 'sale-123',
    code, status, notes: null, created_by_id: 'user-1', received_by_id: null, received_at: null,
    cancelled_at: null, cancellation_reason: null, created_at: '2026-10-19T12:00:00Z', updated_at: '2026-10-19T12:00:00Z',
    evidence: [],
    lines: [{
      id: 'line-1', delivery_id: 'delivery-1', delivery_code: 'ENT-001', delivery_allocation_id: 'allocation-1',
      source_handling_unit_id: 'hu-1', inventory_item_id: 'item-1', product_sku: 'SKU-CAFE-01',
      product_name: 'Café de prueba', unit_name: 'Caja', base_unit_name: 'kg', lot_code: 'LOT-001',
      quantity_received_base: '2.000000', quantity_accepted_base: '0.000000', quantity_rejected_base: '0.000000',
      quantity_pending_base: '2.000000', quantity_returnable_base: '0.000000', reason: 'Prueba',
      declared_condition: 'resalable', events: []
    }]
  };
}

describe('SalesReturnsList', () => {
  beforeEach(() => {
    listReturns.mockReset().mockResolvedValue([document('received')]);
  });

  it('muestra estado, artículo, entrega y acceso a la venta de origen', async () => {
    const row = document('received');
    row.lines[0]!.base_unit_name = 'Unidad (u) (u)';
    listReturns.mockResolvedValueOnce([row]);
    render(SalesReturnsList);

    expect(await screen.findByText('DEV-00001')).toBeInTheDocument();
    expect(screen.getByText(/Café de prueba · SKU-CAFE-01 · 2\.000000 Unidad \(u\)/)).toBeInTheDocument();
    expect(screen.queryByText(/Unidad \(u\) \(u\)/)).not.toBeInTheDocument();
    expect(screen.getAllByText('Recibida · pendiente de revisión')).toHaveLength(2);
    const receivedBadge = screen.getAllByText('Recibida · pendiente de revisión').find((element) => element.tagName === 'SPAN') as HTMLElement;
    expect(receivedBadge).toHaveClass('border-warning/30', 'bg-warning/10', 'text-warning');
    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite');
    expect(screen.getByRole('link', { name: 'Abrir venta y gestionar' })).toHaveAttribute('href', '/sales/sale-123#sales-returns-heading');
    expect(listReturns).toHaveBeenCalledOnce();
  });

  it('diferencia visualmente los estados y anuncia los resultados filtrados', async () => {
    listReturns.mockResolvedValueOnce([document('accepted'), { ...document('rejected'), id: 'return-2', code: 'DEV-00002' }]);
    render(SalesReturnsList);

    expect(await screen.findByText('DEV-00002')).toBeInTheDocument();
    const accepted = screen.getAllByText('Aceptada').find((element) => element.tagName === 'SPAN') as HTMLElement;
    const rejected = screen.getAllByText('Rechazada').find((element) => element.tagName === 'SPAN') as HTMLElement;
    expect(accepted).toHaveClass('border-success/30', 'bg-success/10', 'text-success');
    expect(rejected).toHaveClass('border-danger/30', 'bg-danger/10', 'text-danger');

    fireEvent.input(screen.getByLabelText('Buscar devolución, producto o entrega'), { target: { value: 'NO-EXISTE' } });
    expect(screen.getByRole('status')).toHaveTextContent('Filtros aplicados · 0 de 2 resultados');
    expect(await screen.findByText('No hay resultados para estos filtros')).toBeInTheDocument();
  });

  it('distingue una lista vacía de una falla al consultar', async () => {
    listReturns.mockResolvedValueOnce([]);
    const first = render(SalesReturnsList);
    expect(await screen.findByText('Todavía no hay devoluciones')).toBeInTheDocument();
    first.unmount();

    listReturns.mockRejectedValueOnce(new Error('offline'));
    render(SalesReturnsList);
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudieron cargar las devoluciones.');
    expect(screen.queryByText('Todavía no hay devoluciones')).not.toBeInTheDocument();
    await waitFor(() => expect(listReturns).toHaveBeenCalledTimes(2));
  });
});
