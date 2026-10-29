import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { salesApi } = vi.hoisted(() => ({
  salesApi: {
    deliveryStock: vi.fn(),
    deliveriesForSale: vi.fn(),
    createDelivery: vi.fn(),
    updateDelivery: vi.fn(),
    confirmDelivery: vi.fn(),
    cancelDelivery: vi.fn()
  }
}));

vi.mock('$lib/api/sales', () => ({ salesApi }));

import { branch } from '$lib/stores/branch.svelte';
import { permissions } from '$lib/stores/permissions.svelte';
import { confirmation } from '$lib/stores/confirmation.svelte';
import type { Sale, SalesDelivery, SalesDeliveryStockLine } from '$lib/types/sales';
import SalesDeliveryPanel from './SalesDeliveryPanel.svelte';
import { HttpError } from '$lib/api/client';

const sale: Sale = {
  id: 'sale-1',
  company_id: 'company-1',
  branch_id: 'branch-1',
  customer_id: 'customer-1',
  customer_code: 'CLI-001',
  customer_name: 'Cliente de prueba',
  quotation_id: 'quotation-1',
  quotation_code: 'COT-00001',
  code: 'VEN-00001',
  currency: 'USD',
  subtotal: '100.00',
  total: '100.00',
  status: 'confirmed',
  version: 2,
  notes: null,
  delivery_progress: 'pending',
  lines: [
    {
      id: 'sale-line-1',
      source_quotation_line_id: 'quotation-line-1',
      product_id: 1,
      variant_id: null,
      inventory_item_id: 'item-1',
      product_sku: 'SKU-001',
      product_name: 'Producto de prueba',
      unit_id: 1,
      unit_name: 'Caja',
      base_unit_id: 1,
      base_unit_name: 'unidad',
      unit_factor: '1',
      quantity: '2',
      quantity_base: '2.000000',
      unit_price: '50.00',
      line_total: '100.00',
      quantity_delivered_base: '0.000000',
      quantity_pending_base: '2.000000'
    }
  ],
  created_at: '2026-10-19T12:00:00Z',
  updated_at: '2026-10-19T12:00:00Z'
};

const unit = {
  handling_unit_id: 'hu-1',
  code: 'HU-00001',
  inventory_item_id: 'item-1',
  quantity_base: '1.000000',
  base_unit_name: 'unidad',
  lot_code: 'LOT-001',
  expiry_date: '2027-01-01',
  warehouse_id: 'warehouse-1',
  warehouse_name: 'Bodega de prueba',
  location_id: 'location-1',
  location_code: 'A-01',
  packaging_snapshot: null
};

const stock: SalesDeliveryStockLine[] = [
  {
    sale_line_id: 'sale-line-1',
    product_sku: 'SKU-001',
    product_name: 'Producto de prueba',
    unit_name: 'Caja',
    base_unit_name: 'unidad',
    quantity_pending_base: '2.000000',
    units: [unit]
  }
];

const draft: SalesDelivery = {
  id: 'delivery-1',
  company_id: 'company-1',
  branch_id: 'branch-1',
  sale_id: 'sale-1',
  code: 'ENT-00001',
  status: 'draft',
  version: 1,
  notes: null,
  created_by_id: 'user-1',
  confirmed_by_id: null,
  confirmed_at: null,
  cancelled_by_id: null,
  cancelled_at: null,
  cancellation_reason: null,
  created_at: '2026-10-19T12:00:00Z',
  updated_at: '2026-10-19T12:00:00Z',
  lines: [
    {
      id: 'delivery-line-1',
      sale_line_id: 'sale-line-1',
      product_sku: 'SKU-001',
      product_name: 'Producto de prueba',
      unit_name: 'Caja',
      base_unit_name: 'unidad',
      quantity_base: '1.000000',
      quantity_in_sale_unit: '1.000000',
      unit_factor: '1.000000',
      allocations: [
        {
          id: 'allocation-1',
          handling_unit_id: 'hu-1',
          handling_unit_code: 'HU-00001',
          warehouse_id: 'warehouse-1',
          location_id: 'location-1',
          inventory_lot_detail_id: null,
          lot_code: 'LOT-001',
          expiry_date: '2027-01-01',
          quantity_base: '1.000000',
          movement_id: null,
          movement_line_id: null,
          valuation_entry_id: null
        }
      ]
    }
  ]
};

function setup() {
  return render(SalesDeliveryPanel, { sale, onChanged: vi.fn(async () => undefined) });
}

describe('SalesDeliveryPanel', () => {
  beforeEach(() => {
    confirmation.reset();
    sessionStorage.clear();
    branch.clear();
    branch.configure({
      company_id: 'company-1',
      access_all_branches: false,
      last_branch_id: 'branch-1',
      branches: [{ id: 'branch-1', company_id: 'company-1', name: 'Sucursal de prueba', code: 'S01', is_active: true }]
    });
    permissions.set(
      ['sales_deliveries:read', 'sales_deliveries:manage', 'sales_deliveries:confirm', 'sales_deliveries:cancel'],
      false
    );
    salesApi.deliveryStock.mockReset().mockResolvedValue(stock);
    salesApi.deliveriesForSale.mockReset().mockResolvedValue([]);
    salesApi.createDelivery.mockReset().mockResolvedValue(draft);
    salesApi.updateDelivery.mockReset().mockResolvedValue(draft);
    salesApi.confirmDelivery.mockReset().mockResolvedValue({ ...draft, status: 'confirmed' });
    salesApi.cancelDelivery.mockReset().mockResolvedValue({ ...draft, status: 'cancelled' });
  });

  it('prepara y cierra el formulario sin crear documentos ni tocar stock', async () => {
    setup();

    await screen.findByText('Todavía no se han preparado entregas para esta venta.');
    await fireEvent.click(screen.getByRole('button', { name: 'Preparar entrega' }));
    expect(await screen.findByText('Nueva entrega · VEN-00001')).toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: 'Cerrar preparación' }));

    expect(screen.queryByText('Nueva entrega · VEN-00001')).not.toBeInTheDocument();
    expect(salesApi.createDelivery).not.toHaveBeenCalled();
    expect(salesApi.confirmDelivery).not.toHaveBeenCalled();
  });

  it('no ofrece preparar otra entrega cuando la venta ya está completamente entregada', async () => {
    render(SalesDeliveryPanel, { sale: { ...sale, delivery_progress: 'complete' }, onChanged: vi.fn() });
    await screen.findByText('Todavía no se han preparado entregas para esta venta.');
    expect(screen.queryByRole('button', { name: 'Preparar entrega' })).not.toBeInTheDocument();
    expect(salesApi.createDelivery).not.toHaveBeenCalled();
  });

  it('consulta la disponibilidad al confirmar una venta sin exigir recargar la página', async () => {
    const view = render(SalesDeliveryPanel, { sale: { ...sale, status: 'draft' }, onChanged: vi.fn() });
    expect(await screen.findByText('Confirma la venta antes de preparar una entrega.')).toBeInTheDocument();
    expect(salesApi.deliveryStock).not.toHaveBeenCalled();
    await view.rerender({ sale });
    await waitFor(() => expect(salesApi.deliveryStock).toHaveBeenCalledWith('sale-1'));
    const prepare = await screen.findByRole('button', { name: 'Preparar entrega' });
    await waitFor(() => expect(prepare).toBeEnabled());
    await fireEvent.click(prepare);
    expect(await screen.findByRole('checkbox', { name: 'Seleccionar unidad HU-00001' })).toBeEnabled();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('guarda una selección de unidades completas como borrador sin confirmar la salida', async () => {
    setup();

    await screen.findByText('Todavía no se han preparado entregas para esta venta.');
    await fireEvent.click(screen.getByRole('button', { name: 'Preparar entrega' }));
    await fireEvent.click(await screen.findByRole('checkbox', { name: 'Seleccionar unidad HU-00001' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Crear borrador' }));

    await waitFor(() => expect(salesApi.createDelivery).toHaveBeenCalledOnce());
    expect(salesApi.createDelivery).toHaveBeenCalledWith(
      'sale-1',
      { notes: null, assignments: [{ sale_line_id: 'sale-line-1', handling_unit_id: 'hu-1' }] },
      expect.any(String)
    );
    expect(salesApi.confirmDelivery).not.toHaveBeenCalled();
  });

  it('confirma el borrador con clave estable y refresca la venta', async () => {
    const onChanged = vi.fn(async () => undefined);
    const confirmed = {
      ...draft,
      status: 'confirmed' as const,
      confirmed_by_id: 'user-1',
      confirmed_at: '2026-10-19T12:01:00Z'
    };
    salesApi.deliveriesForSale.mockResolvedValueOnce([draft]).mockResolvedValue([confirmed]);
    salesApi.confirmDelivery.mockResolvedValue(confirmed);
    render(SalesDeliveryPanel, { sale, onChanged });

    await fireEvent.click(await screen.findByRole('button', { name: 'Confirmar entrega' }));
    expect(salesApi.confirmDelivery).not.toHaveBeenCalled();
    await confirmation.proceed();
    await waitFor(() => expect(salesApi.confirmDelivery).toHaveBeenCalledOnce());
    expect(salesApi.confirmDelivery).toHaveBeenCalledWith('delivery-1', 1, expect.any(String));
    expect(onChanged).toHaveBeenCalledOnce();
    expect(await screen.findByText('Entrega confirmada. El inventario y su valoración quedaron registrados en el Kardex.')).toBeInTheDocument();
  });

  it('permite corregir una selección rechazada sin conservar un envío pendiente bloqueado', async () => {
    salesApi.createDelivery.mockRejectedValueOnce(new HttpError('sales_delivery_unit_unavailable', 'La unidad ya no está disponible', 409));
    setup();
    await screen.findByText('Todavía no se han preparado entregas para esta venta.');
    await fireEvent.click(screen.getByRole('button', { name: 'Preparar entrega' }));
    await fireEvent.click(await screen.findByRole('checkbox', { name: 'Seleccionar unidad HU-00001' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Crear borrador' }));
    await screen.findByRole('alert');
    expect(screen.getByRole('checkbox', { name: 'Seleccionar unidad HU-00001' })).toBeEnabled();
    expect(sessionStorage.getItem('sales-delivery-create:sale-1:branch-1')).toBeNull();
  });

  it('renueva el comando de confirmación al recuperar un borrador con una revisión posterior', async () => {
    sessionStorage.setItem('sales-delivery-confirm:sale-1:delivery-1:branch-1', JSON.stringify({ idempotencyKey: 'old-command', version: 1 }));
    salesApi.deliveriesForSale.mockResolvedValue([{ ...draft, version: 2 }]);
    setup();
    await fireEvent.click(await screen.findByRole('button', { name: 'Confirmar entrega' }));
    await confirmation.proceed();
    await waitFor(() => expect(salesApi.confirmDelivery).toHaveBeenCalledOnce());
    expect(salesApi.confirmDelivery).toHaveBeenCalledWith('delivery-1', 2, expect.not.stringMatching(/^old-command$/));
  });

  it('exige guardar la selección y notas editadas antes de confirmar la entrega', async () => {
    salesApi.deliveriesForSale.mockResolvedValue([draft]);
    setup();
    await fireEvent.click(await screen.findByRole('button', { name: 'Editar selección' }));
    const confirm = screen.getByRole('button', { name: 'Confirmar entrega' });
    const checkbox = screen.getByRole('checkbox', { name: 'Seleccionar unidad HU-00001' });
    expect(confirm).toBeEnabled();
    await fireEvent.click(checkbox);
    expect(confirm).toBeDisabled();
    expect(screen.getByRole('status')).toHaveTextContent('Guarda los cambios de la entrega');
    await fireEvent.click(confirm);
    expect(salesApi.confirmDelivery).not.toHaveBeenCalled();
    await fireEvent.click(checkbox);
    expect(confirm).toBeEnabled();
    const notes = screen.getByLabelText('Notas de entrega');
    await fireEvent.input(notes, { target: { value: 'Nueva revisión del despacho' } });
    expect(confirm).toBeDisabled();
    const updated = { ...draft, version: 2, notes: 'Nueva revisión del despacho' };
    salesApi.deliveriesForSale.mockResolvedValue([updated]);
    await fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));
    await waitFor(() => expect(salesApi.updateDelivery).toHaveBeenCalledOnce());
    await waitFor(() => expect(screen.getByRole('button', { name: 'Confirmar entrega' })).toBeEnabled());
  });

  it('cancelar o abandonar la confirmación no descuenta las unidades', async () => {
    salesApi.deliveriesForSale.mockResolvedValue([draft]);
    const view = render(SalesDeliveryPanel, { sale, onChanged: vi.fn() });
    const button = await screen.findByRole('button', { name: 'Confirmar entrega' });
    await fireEvent.click(button);
    expect(confirmation.current?.confirmLabel).toBe('Confirmar entrega ahora');
    expect(confirmation.current?.description).toContain('Sucursal de prueba');
    confirmation.cancel();
    expect(salesApi.confirmDelivery).not.toHaveBeenCalled();
    await fireEvent.click(button);
    view.unmount();
    expect(confirmation.open).toBe(false);
    await confirmation.proceed();
    expect(salesApi.confirmDelivery).not.toHaveBeenCalled();
  });
});
