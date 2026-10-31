import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseConsolidationDetail from '$lib/features/purchase-requests/components/PurchaseConsolidationDetail.svelte';
import type { PurchaseConsolidation } from '$lib/types/purchase-consolidation';

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  eligibleRequests: vi.fn(),
  inventorySnapshot: vi.fn(),
  addRequests: vi.fn(),
  update: vi.fn(),
  cancel: vi.fn(),
  listProducts: vi.fn(),
  warehouses: vi.fn(),
  hasPermission: vi.fn()
}));

vi.mock('$app/state', () => ({ page: { params: { id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa' } } }));
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('$lib/api/purchase-consolidations', () => ({
  purchaseConsolidationsApi: {
    get: mocks.get,
    eligibleRequests: mocks.eligibleRequests,
    inventorySnapshot: mocks.inventorySnapshot,
    addRequests: mocks.addRequests,
    update: mocks.update,
    cancel: mocks.cancel
  }
}));
vi.mock('$lib/api/catalog', () => ({ catalogApi: { listProducts: mocks.listProducts } }));
vi.mock('$lib/api/client', () => ({
  api: { warehouses: { catalogue: mocks.warehouses } },
  HttpError: class HttpError extends Error {}
}));
vi.mock('$lib/stores/branch.svelte', () => ({
  branch: { id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', accessAllBranches: true, branches: [] }
}));
vi.mock('$lib/stores/permissions.svelte', () => ({ permissions: { hasPermission: mocks.hasPermission } }));

const consolidation: PurchaseConsolidation = {
  id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  company_id: 'cccccccc-cccc-cccc-cccc-cccccccccccc',
  code: 'CD-00001',
  period_start: '2026-10-04',
  period_end: '2026-10-05',
  status: 'draft',
  created_by_id: 'dddddddd-dddd-dddd-dddd-dddddddddddd',
  created_at: null,
  updated_at: null,
  central_warehouse_id: null,
  central_warehouse_name: null,
  notes: null,
  lines: [
    {
      id: 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
      product_id: 10,
      product_sku: 'PRD-10',
      product_name: 'Harina de prueba',
      unit_id: 1,
      unit_name: 'Kilogramo',
      branch_quantity: '5.000000',
      central_quantity: '0.000000',
      central_reason: null,
      total_quantity: '5.000000',
      sources: []
    }
  ],
  events: []
};

describe('PurchaseConsolidationDetail', () => {
  beforeEach(() => {
    mocks.get.mockReset().mockResolvedValue(consolidation);
    mocks.eligibleRequests.mockReset().mockResolvedValue({ items: [], total: 0, page: 1, size: 100 });
    mocks.inventorySnapshot.mockReset();
    mocks.addRequests.mockReset();
    mocks.update.mockReset();
    mocks.cancel.mockReset();
    mocks.listProducts.mockReset();
    mocks.warehouses.mockReset().mockResolvedValue([]);
    mocks.hasPermission.mockReset().mockReturnValue(false);
  });

  it('loads the consolidation when opening the detail route', async () => {
    render(PurchaseConsolidationDetail);

    expect(await screen.findByRole('heading', { name: 'CD-00001' })).toBeInTheDocument();
    expect(screen.getAllByText('Harina de prueba').length).toBeGreaterThan(0);
    expect(mocks.get).toHaveBeenCalledWith(consolidation.id);
    await waitFor(() => expect(mocks.eligibleRequests).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(mocks.warehouses).toHaveBeenCalledTimes(1));
    expect(screen.queryByText('Cargando…')).not.toBeInTheDocument();
  });

  it('explains that the mother warehouse is optional and disables central additions when it is empty', async () => {
    mocks.hasPermission.mockImplementation((permission: string) => permission === 'purchase_requests:manage');
    mocks.listProducts.mockResolvedValue({ items: [], meta: { page: 1, pages: 1 } });
    render(PurchaseConsolidationDetail);

    expect(await screen.findByText('La casa matriz recibe las cantidades del plan central. Las cantidades solicitadas por las sucursales conservan su destino; el traslado desde la matriz a cada tienda se registra después.'))
      .toBeInTheDocument();
    expect(screen.getByTestId('central-demand-destination-note'))
      .toHaveTextContent('Elige primero una bodega madre arriba.');
    expect(screen.getByRole('button', { name: 'Agregar demanda' })).toBeDisabled();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(mocks.update).not.toHaveBeenCalled();
  });

  it('explains the missing destination before saving positive central quantities', async () => {
    mocks.hasPermission.mockReturnValue(true);
    mocks.listProducts.mockResolvedValue({ items: [], meta: { page: 1, pages: 1 } });
    render(PurchaseConsolidationDetail);

    const centralQuantity = (await screen.findAllByLabelText('Cantidad central Harina de prueba'))[0];
    if (!centralQuantity) throw new Error('No se encontró el campo de cantidad central.');
    fireEvent.input(centralQuantity, { target: { value: '120' } });
    const centralReason = (await screen.findAllByLabelText('Motivo de cantidad central Harina de prueba'))[0];
    if (!centralReason) throw new Error('No se encontró el motivo de la cantidad central.');
    fireEvent.input(centralReason, { target: { value: 'Reposición de inventario' } });
    fireEvent.input(screen.getByLabelText('Motivo general de los cambios'), {
      target: { value: 'Plan de reposición' }
    });
    expect(await screen.findByText('120 Kilogramo')).toBeInTheDocument();
    expect(await screen.findByText('125 Kilogramo')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    expect(await screen.findByText('El borrador tiene cantidades destinadas a bodega central, pero falta elegir la bodega. Selecciónala arriba o pon esas cantidades en 0.'))
      .toBeInTheDocument();
    expect(mocks.update).not.toHaveBeenCalled();

    fireEvent.input(centralQuantity, { target: { value: '60' } });
    expect(screen.getByText('El borrador tiene cantidades destinadas a bodega central, pero falta elegir la bodega. Selecciónala arriba o pon esas cantidades en 0.'))
      .toBeInTheDocument();
    fireEvent.input(centralQuantity, { target: { value: '0' } });
    expect(screen.queryByText('El borrador tiene cantidades destinadas a bodega central, pero falta elegir la bodega. Selecciónala arriba o pon esas cantidades en 0.'))
      .not.toBeInTheDocument();
  });

  it('replaces an old store destination with the company mother and saves that correction', async () => {
    mocks.hasPermission.mockReturnValue(true);
    mocks.listProducts.mockResolvedValue({ items: [], meta: { page: 1, pages: 1 } });
    const oldWarehouseId = 'ffffffff-ffff-ffff-ffff-ffffffffffff';
    const motherWarehouseId = 'eeeeeeee-1111-1111-1111-eeeeeeeeeeee';
    const itemWithCentralDemand = {
      ...consolidation,
      central_warehouse_id: oldWarehouseId,
      central_warehouse_name: 'Bodega tienda El Tránsito',
      lines: [{
        ...consolidation.lines[0],
        central_quantity: '20.000000',
        central_reason: 'Reserva adicional',
        total_quantity: '25.000000'
      }]
    };
    mocks.get.mockResolvedValue(itemWithCentralDemand);
    mocks.warehouses.mockResolvedValue([
      {
        id: oldWarehouseId,
        name: 'Bodega tienda El Tránsito',
        branch_name: 'Pastelería El Tránsito',
        is_central: false,
        status: 'active'
      },
      {
        id: motherWarehouseId,
        name: 'Bodega madre',
        branch_id: null,
        branch_name: 'Casa matriz · independiente',
        is_central: true,
        status: 'active'
      }
    ]);
    mocks.update.mockResolvedValue({
      ...itemWithCentralDemand,
      central_warehouse_id: motherWarehouseId,
      central_warehouse_name: 'Bodega madre'
    });
    render(PurchaseConsolidationDetail);

    expect(await screen.findByText(/El destino guardado era una bodega de sucursal.*guarda los cambios/i)).toBeInTheDocument();
    const destination = screen.getByLabelText('Bodega madre destino (opcional)');
    expect(destination).toHaveValue(motherWarehouseId);
    expect(screen.getByRole('option', { name: /Bodega madre · Casa matriz/ })).toBeInTheDocument();
    expect(screen.getByTestId('central-demand-destination-note')).toHaveTextContent('quedará planeada para Bodega madre');
    expect(screen.getByTestId('central-demand-destination-note')).not.toHaveTextContent('El Tránsito');
    fireEvent.input(screen.getByLabelText('Motivo general de los cambios'), {
      target: { value: 'Corregir destino del plan' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith(
      consolidation.id,
      expect.objectContaining({ central_warehouse_id: motherWarehouseId })
    ));
  });

  it('saves a real draft change through the update action', async () => {
    mocks.hasPermission.mockReturnValue(true);
    mocks.listProducts.mockResolvedValue({ items: [], meta: { page: 1, pages: 1 } });
    mocks.get.mockReset().mockResolvedValueOnce(consolidation).mockRejectedValueOnce(new Error('Falló la lectura posterior.'));
    const updated = { ...consolidation, notes: 'Compra prioritaria para la semana' };
    mocks.update.mockResolvedValue(updated);
    render(PurchaseConsolidationDetail);

    const notes = await screen.findByLabelText('Notas del consolidado');
    fireEvent.input(notes, { target: { value: 'Compra prioritaria para la semana' } });
    fireEvent.input(screen.getByLabelText('Motivo general de los cambios'), {
      target: { value: 'Ajuste solicitado por operaciones' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    await waitFor(() => expect(mocks.update).toHaveBeenCalledTimes(1));
    expect(mocks.update).toHaveBeenCalledWith(consolidation.id, {
      change_reason: 'Ajuste solicitado por operaciones',
      source_changes: [],
      central_demands: [],
      notes: 'Compra prioritaria para la semana'
    });
    expect(await screen.findByText('Borrador guardado. El historial conserva los cambios y sus motivos.'))
      .toBeInTheDocument();
    expect(notes).toHaveValue('Compra prioritaria para la semana');
    expect(mocks.get).toHaveBeenCalledTimes(1);
  });

  it('does not send only the general change reason as a draft change', async () => {
    mocks.hasPermission.mockReturnValue(true);
    mocks.listProducts.mockResolvedValue({ items: [], meta: { page: 1, pages: 1 } });
    render(PurchaseConsolidationDetail);

    await screen.findByLabelText('Motivo general de los cambios');
    fireEvent.input(screen.getByLabelText('Motivo general de los cambios'), {
      target: { value: 'Cambios 1.2' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    expect(await screen.findByText('No hay cambios que guardar.')).toBeInTheDocument();
    expect(mocks.update).not.toHaveBeenCalled();
  });

  it('explains the required per-product reason instead of sending an invalid central quantity change', async () => {
    mocks.hasPermission.mockReturnValue(true);
    mocks.listProducts.mockResolvedValue({ items: [], meta: { page: 1, pages: 1 } });
    const withCentralWarehouse = {
      ...consolidation,
      central_warehouse_id: 'ffffffff-ffff-ffff-ffff-ffffffffffff',
      central_warehouse_name: 'Bodega central'
    };
    const updated = {
      ...withCentralWarehouse,
      lines: [{
        ...withCentralWarehouse.lines[0],
        central_quantity: '120.000000',
        central_reason: 'Reposición para la semana',
        total_quantity: '125.000000'
      }]
    };
    mocks.get.mockResolvedValue(withCentralWarehouse);
    mocks.update.mockResolvedValue(updated);
    mocks.warehouses.mockResolvedValue([{
      id: withCentralWarehouse.central_warehouse_id,
      name: 'Bodega central',
      branch_id: null,
      branch_name: 'Sucursal prueba',
      is_central: true,
      status: 'active'
    }]);
    render(PurchaseConsolidationDetail);

    const centralQuantity = (await screen.findAllByLabelText('Cantidad central Harina de prueba'))[0];
    if (!centralQuantity) throw new Error('No se encontró el campo de cantidad central.');
    fireEvent.input(centralQuantity, { target: { value: '120' } });
    fireEvent.input(screen.getByLabelText('Motivo general de los cambios'), {
      target: { value: 'Plan semanal de compras' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    expect(await screen.findByText('Escribe el motivo de cada cambio de cantidad del plan central.'))
      .toBeInTheDocument();
    expect(mocks.update).not.toHaveBeenCalled();

    const centralReason = (await screen.findAllByLabelText('Motivo de cantidad central Harina de prueba'))[0];
    if (!centralReason) throw new Error('No se encontró el campo de motivo central.');
    fireEvent.input(centralReason, { target: { value: 'Reposición para la semana' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    await waitFor(() => expect(mocks.update).toHaveBeenCalledTimes(1));
    expect(mocks.update).toHaveBeenCalledWith(consolidation.id, {
      change_reason: 'Plan semanal de compras',
      source_changes: [],
      central_demands: [{
        line_id: 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
        product_id: 10,
        quantity: 120,
        reason: 'Reposición para la semana'
      }],
      notes: null
    });
    expect(await screen.findByText('Borrador guardado. El historial conserva los cambios y sus motivos.'))
      .toBeInTheDocument();
  });
});
