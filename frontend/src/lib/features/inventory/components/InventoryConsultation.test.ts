import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Stock from './WarehouseStockPanel.svelte';
import Lots from './WarehouseLotsPanel.svelte';
import Map from './WarehouseLocationMap.svelte';
import Opening from './ProductStockOpening.svelte';
import Relocation from './UnitRelocation.svelte';
import type { HandlingUnit } from '../types';

const mocks = vi.hoisted(() => ({
  stock: vi.fn(),
  lots: vi.fn(),
  locations: vi.fn(),
  location: vi.fn(),
  capacity: vi.fn(),
  search: vi.fn(),
  opening: vi.fn(),
  transfer: vi.fn()
}));
vi.mock('../workspace', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  workspaceApi: { stock: mocks.stock, searchItems: mocks.search, opening: mocks.opening }
}));
vi.mock('../services', () => ({
  inventoryApi: {
    listReceiptLots: mocks.lots,
    getCapacitySummary: mocks.capacity,
    transferUnits: mocks.transfer
  }
}));
vi.mock('$lib/features/locations/services', () => ({
  listLocations: mocks.locations,
  getLocation: mocks.location
}));
const row = {
  inventory_item_id: 'item',
  product_name: 'Azúcar Glass Premium 10kg',
  sku: 'PRD-AZU-004',
  base_unit_symbol: 'cj',
  location_id: 'loc',
  location_code: 'A02-R01-N01-P01',
  stock_status: 'available',
  lot_code: null,
  expiry_date: null,
  quantity_base: '80'
};
const space = {
  id: 'loc',
  warehouse_id: 'matrix',
  code: row.location_code,
  aisle: '02',
  rack: '01',
  level: '01',
  position: '01',
  storage_eligible: true,
  is_active: true,
  lifecycle_status: 'active'
};
const item = {
  id: 'item',
  product_name: row.product_name,
  sku: row.sku,
  base_unit_symbol: 'cj',
  base_unit_name: 'Caja',
  base_unit_id: 1
};
beforeEach(() => {
  vi.clearAllMocks();
  mocks.stock.mockResolvedValue({ items: [row], total: 1, page: 1, size: 25 });
  mocks.locations.mockResolvedValue({
    items: [space, { ...space, id: 'dest', code: 'A02-R02-N01-P01' }],
    meta: { page: 1, pages: 1, total: 2 }
  });
  mocks.location.mockResolvedValue(space);
  mocks.lots.mockResolvedValue({ items: [], total: 0, page: 1, size: 10 });
  mocks.search.mockResolvedValue({ items: [item], items_total: 1, locations: [] });
  mocks.opening.mockResolvedValue({ id: 'movement', source_reference: 'SI:ACTA-01' });
  mocks.transfer.mockResolvedValue({});
  const metric = { occupied: 1, operational: 100 };
  mocks.capacity.mockResolvedValue({
    weight: metric,
    volume: metric,
    measurementStatus: 'complete'
  });
});
afterEach(cleanup);
describe('Consultas de inventario', () => {
  it('explica por qué no se puede reubicar si no hay otro espacio', async () => {
    mocks.locations.mockResolvedValue({ items: [space], meta: { page: 1, pages: 1, total: 1 } });
    render(Relocation, {
      unit: {
        ...row,
        id: 'hu',
        code: 'HU-1',
        warehouse_id: 'matrix',
        quantity_base: 80
      } as unknown as HandlingUnit,
      onclose: vi.fn(),
      onmoved: vi.fn()
    });
    expect(
      await screen.findByText(/No hay otra ubicación de almacenamiento habilitada/)
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Confirmar reubicación' })).toBeDisabled();
    await fireEvent.click(screen.getByRole('button', { name: 'Volver a consultar ubicaciones' }));
    await waitFor(() => expect(mocks.locations).toHaveBeenCalledTimes(2));
  });
  it('bloquea apertura y explica cómo continuar sin ubicaciones habilitadas', async () => {
    mocks.locations.mockResolvedValue({ items: [], meta: { page: 1, pages: 1, total: 0 } });
    render(Opening, { warehouseId: 'matrix', warehouseName: 'Matriz', onregistered: vi.fn() });
    expect(
      await screen.findByText(/No hay ubicaciones de almacenamiento habilitadas/)
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Revisar saldo inicial' })).toBeDisabled();
  });
  it('dirige el foco al espacio seleccionado y permite reintentar capacidad', async () => {
    mocks.capacity.mockRejectedValueOnce(new Error('Sin conexión'));
    render(Map, { warehouseId: 'matrix', initialLocationId: 'loc' });
    const retry = await screen.findByRole('button', { name: 'Reintentar capacidad' });
    await waitFor(() => expect(document.activeElement?.id).toBe('warehouse-selected-location'));
    await fireEvent.click(retry);
    await waitFor(() => expect(mocks.capacity).toHaveBeenCalledTimes(2));
    expect(await screen.findByText('Peso ocupado / límite operativo')).toBeInTheDocument();
  });
  it('muestra saldo, conserva ubicación y envía los filtros al servidor', async () => {
    const onlocation = vi.fn();
    render(Stock, { warehouseId: 'matrix', onlocation });
    await screen.findByText(row.product_name);
    expect(screen.queryByText(/Costo|USD/)).not.toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: row.location_code }));
    expect(onlocation).toHaveBeenCalledWith('loc');
    await fireEvent.input(screen.getByLabelText('Producto, código o lote'), {
      target: { value: 'Azúcar' }
    });
    await fireEvent.submit(screen.getByRole('button', { name: 'Consultar' }).closest('form')!);
    await waitFor(() =>
      expect(mocks.stock).toHaveBeenLastCalledWith(
        'matrix',
        expect.objectContaining({ q: 'Azúcar', page: 1 }),
        expect.any(AbortSignal)
      )
    );
  });
  it('presenta vacío y permite recuperar un error de consulta', async () => {
    mocks.stock
      .mockRejectedValueOnce(new Error('Red interrumpida'))
      .mockResolvedValueOnce({ items: [], total: 0, page: 1, size: 25 });
    render(Stock, { warehouseId: 'matrix' });
    expect(await screen.findByRole('alert')).toHaveTextContent('Red interrumpida');
    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    expect(await screen.findByText('Sin existencias para esta consulta')).toBeInTheDocument();
  });
  it('encuentra un espacio fuera de la página y consulta su contenido', async () => {
    render(Map, { warehouseId: 'matrix', initialLocationId: 'loc' });
    expect(await screen.findByRole('region', { name: 'Espacio seleccionado' })).toHaveTextContent(
      row.location_code
    );
    await waitFor(() =>
      expect(mocks.stock).toHaveBeenCalledWith(
        'matrix',
        expect.objectContaining({ location_id: 'loc' }),
        expect.any(AbortSignal)
      )
    );
    expect(mocks.location).toHaveBeenCalledWith('matrix', 'loc');
  });
  it('busca lotes en el servidor sin cargar el catálogo completo', async () => {
    render(Lots, { warehouseId: 'matrix' });
    await screen.findByText('Sin lotes para esta consulta');
    await fireEvent.input(screen.getByLabelText('Producto, compra o lote'), {
      target: { value: 'COM-00022' }
    });
    await fireEvent.submit(screen.getByRole('button', { name: 'Buscar lotes' }).closest('form')!);
    await waitFor(() =>
      expect(mocks.lots).toHaveBeenLastCalledWith(
        expect.objectContaining({ q: 'COM-00022', page: 1, size: 10 })
      )
    );
  });
  it('revisa 80 a 6.80 antes de confirmar y conserva la clave al reintentar', async () => {
    mocks.opening
      .mockRejectedValueOnce(new Error('Sin respuesta'))
      .mockResolvedValueOnce({ source_reference: 'SI:ACTA-01' });
    const callback = vi.fn();
    render(Opening, { warehouseId: 'matrix', warehouseName: 'Matriz', onregistered: callback });
    await fireEvent.click(await screen.findByRole('button', { name: 'Artículo' }));
    await fireEvent.click(await screen.findByRole('button', { name: /Azúcar Glass Premium/ }));
    await fireEvent.change(screen.getByLabelText('Ubicación de almacenamiento'), {
      target: { value: 'loc' }
    });
    for (const [label, value] of [
      ['Cantidad (cj)', '80'],
      ['Costo unitario', '6.80'],
      ['Peso bruto total (kg)', '1'],
      ['Volumen total (m³)', '0.01'],
      ['Referencia del acta o documento', 'ACTA-01'],
      ['Motivo y respaldo del conteo', 'Conteo físico inicial']
    ] as const)
      await fireEvent.input(screen.getByLabelText(label), { target: { value } });
    await fireEvent.submit(
      screen.getByRole('button', { name: 'Revisar saldo inicial' }).closest('form')!
    );
    expect(screen.getByText('544.00')).toBeInTheDocument();
    expect(mocks.opening).not.toHaveBeenCalled();
    const summary = screen.getByRole('region', { name: 'Revisa antes de registrar' });
    expect(summary).toHaveTextContent('Matriz · A02-R01-N01-P01');
    expect(summary).toHaveTextContent('80 cj');
    expect(summary).toHaveTextContent('6.80');
    await waitFor(() => expect(document.activeElement?.id).toBe('opening-review-heading'));
    await fireEvent.click(screen.getByRole('button', { name: 'Volver a revisar' }));
    await waitFor(() => expect(document.activeElement?.id).toBe('opening-product'));
    expect(screen.getByLabelText('Cantidad (cj)')).toHaveValue('80');
    await fireEvent.submit(
      screen.getByRole('button', { name: 'Revisar saldo inicial' }).closest('form')!
    );
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar saldo inicial' }));
    await screen.findByText('Sin respuesta');
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar saldo inicial' }));
    await screen.findByText('Saldo inicial registrado: SI:ACTA-01');
    expect(mocks.opening.mock.calls[0]?.[0].idempotency_key).toBe(
      mocks.opening.mock.calls[1]?.[0].idempotency_key
    );
    expect(callback).toHaveBeenCalledOnce();
  });
  it('reubica la unidad completa con motivo y otra ubicación', async () => {
    render(Relocation, {
      unit: {
        ...row,
        id: 'hu',
        code: 'HU-1',
        warehouse_id: 'matrix',
        quantity_base: 80
      } as unknown as HandlingUnit,
      onclose: vi.fn(),
      onmoved: vi.fn()
    });
    await screen.findByRole('option', { name: 'A02-R02-N01-P01' });
    await fireEvent.change(screen.getByLabelText('Nueva ubicación'), { target: { value: 'dest' } });
    await fireEvent.input(screen.getByLabelText('Motivo'), {
      target: { value: 'Reacomodo del pasillo' }
    });
    await fireEvent.submit(
      screen.getByRole('button', { name: 'Confirmar reubicación' }).closest('form')!
    );
    expect(mocks.transfer).toHaveBeenCalledWith(
      expect.any(Array),
      'dest',
      'Reubicación: Reacomodo del pasillo',
      'available',
      'available',
      expect.any(String)
    );
  });
});
