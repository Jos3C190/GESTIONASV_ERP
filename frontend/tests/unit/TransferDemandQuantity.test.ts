import { render, screen } from '@testing-library/svelte';
import { expect, it, vi } from 'vitest';
import TransferDemandOverview from '../../src/lib/features/inventory/components/TransferDemandOverview.svelte';

it('presenta el saldo agregado en unidades y no en millonésimas internas', () => {
  render(TransferDemandOverview, {
    products: [{ key: 'product-1', productId: 1, productName: 'Producto decimal', sku: 'SKU-DEC',
      unitLabel: 'kg', units: [], demands: [], availableQuantity: 2_250_000n }],
    stockState: 'loaded', demandState: 'empty', supplyError: null, search: '', canMoveInventory: true,
    onSearch: vi.fn(), onPrepareManual: vi.fn(), onPrepareDemand: vi.fn()
  });
  expect(screen.getByText('0 unidades logísticas · 2.25 kg')).toBeInTheDocument();
  expect(screen.queryByText(/2,250,000/)).not.toBeInTheDocument();
});

it('prioriza la sucursal y la cantidad pendiente y permite desplegar el avance completo', () => {
  render(TransferDemandOverview, {
    products: [{ key: 'product-2', productId: 2, productName: 'Café de prueba', sku: 'SKU-CAF', availableQuantity: 10_000_000n,
      unitLabel: 'cj', units: [{ id: 'hu-1', product_id: 2, base_unit_id: 1, quantity_base: '10' } as never],
      demands: [{ purchase_request_detail_id: 'detail-1', purchase_request_id: 'request-1', request_code: 'SCR-00042',
        request_status: 'approved', branch_id: 'branch-1', branch_name: 'Pastelería El Tránsito', request_date: '2026-10-20',
        required_date: '2026-10-22', product_id: 2, inventory_item_id: null, product_name: 'Café de prueba', sku: 'SKU-CAF',
        unit_id: 1, unit_name: 'Caja', unit_symbol: 'cj', quantity_requested: '8', quantity_assigned: '2',
        quantity_dispatched: '1', quantity_in_transit: '1', quantity_received: '0', quantity_adjusted_out: '0', quantity_pending: '6' }] }],
    stockState: 'loaded', demandState: 'loaded', supplyError: null, search: '', canMoveInventory: true,
    onSearch: vi.fn(), onPrepareManual: vi.fn(), onPrepareDemand: vi.fn()
  });

  expect(screen.getAllByText('Pastelería El Tránsito')).toHaveLength(1);
  expect(screen.getAllByText('SCR-00042')).toHaveLength(1);
  expect(screen.getAllByText('6 cj')).toHaveLength(2);
  const progressDetails = screen.getByText('Ver despacho, tránsito y recepción').closest('details');
  expect(progressDetails).not.toHaveAttribute('open');
  expect(screen.getByRole('button', { name: 'Preparar traslado' })).toHaveClass('min-h-11');
});
