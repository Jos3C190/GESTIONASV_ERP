import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Panel from './WarehouseMovementsPanel.svelte';
import type { InventoryMovementHistory } from '../types';

const mocks = vi.hoisted(() => ({ list: vi.fn() }));
vi.mock('../services', () => ({ inventoryApi: { listWarehouseMovements: mocks.list } }));
const row = {
  id: 'line-1',
  movement_id: 'movement-1',
  movement_type: 'receipt',
  source_reference: 'purchase:COM-00028',
  posted_at: '2026-10-28T16:00:00Z',
  operator: 'rodrigo.molina.bodega',
  product_name: 'Chocolate de Cobertura Semiamargo 5kg',
  product_sku: 'PRD-CHO-006',
  from_warehouse_id: null,
  to_warehouse_id: 'matrix',
  to_location_code: 'A02-R01-N01-P01',
  base_unit_symbol: 'cj',
  quantity_base: '1.000000',
  lot_code: 'FAB-28',
  receipt_lot_code: 'LOT-COM-00028',
  measurement_status: 'verified'
} as InventoryMovementHistory;
beforeEach(() => {
  vi.clearAllMocks();
  mocks.list.mockResolvedValue([row]);
});
afterEach(cleanup);

describe('Movimientos del bodeguero', () => {
  it('consulta su bodega y muestra datos físicos con detalle, sin costos', async () => {
    render(Panel, { warehouseId: 'matrix', contextKey: 'company-1' });
    expect(await screen.findByText(row.product_name!)).toBeInTheDocument();
    expect(mocks.list.mock.calls[0]?.[0]).toBe('matrix');
    expect(screen.queryByText(/USD|Costo promedio|Valoración/)).not.toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: /Ver detalle de Chocolate/ }));
    expect(await screen.findByRole('dialog')).toHaveTextContent('LOT-COM-00028');
  });
  it('envía los filtros juntos al servidor al consultar', async () => {
    render(Panel, { warehouseId: 'matrix' });
    await screen.findByText(row.product_name!);
    for (const [label, value] of [
      [/Producto, SKU o unidad/, 'Chocolate'],
      [/Desde/, '2026-10-01'],
      [/Hasta/, '2026-10-28'],
      [/Lote de recepción/, 'LOT-COM'],
      [/Referencia del movimiento/, 'purchase:COM']
    ] as const)
      await fireEvent.input(screen.getByLabelText(label), { target: { value } });
    for (const [label, value] of [
      ['Tipo de movimiento', 'receipt'],
      ['Sentido', 'incoming']
    ] as const) {
      const select = screen.getByLabelText(label) as HTMLSelectElement;
      await fireEvent.change(select, { target: { value } });
    }
    await fireEvent.click(screen.getByRole('button', { name: 'Consultar' }));
    await waitFor(() => expect(mocks.list).toHaveBeenCalledTimes(2));
    expect(mocks.list.mock.calls[1]?.slice(0, 5)).toEqual([
      'matrix',
      26,
      'receipt',
      0,
      {
        period_from: '2026-10-01',
        period_to: '2026-10-28',
        q: 'Chocolate',
        lot_code: 'LOT-COM',
        source_reference: 'purchase:COM',
        direction: 'incoming'
      }
    ]);
    expect(await screen.findByRole('list', { name: 'Filtros aplicados' })).toHaveTextContent('Tipo: Recepción');
    expect(screen.getByRole('list', { name: 'Filtros aplicados' })).toHaveTextContent('Sentido: Entradas');
  });
  it('rechaza fechas invertidas sin lanzar otra consulta', async () => {
    render(Panel, { warehouseId: 'matrix' });
    await screen.findByText(row.product_name!);
    await fireEvent.input(screen.getByLabelText('Desde'), { target: { value: '2026-12-01' } });
    await fireEvent.input(screen.getByLabelText('Hasta'), { target: { value: '2026-10-28' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Consultar' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Desde debe ser anterior');
    expect(screen.getByLabelText('Desde')).toHaveFocus();
    expect(mocks.list).toHaveBeenCalledOnce();
  });
  it('pagina registros y reinicia la página al limpiar filtros', async () => {
    mocks.list.mockResolvedValue(
      Array.from({ length: 26 }, (_, i) => ({ ...row, id: `line-${i}` }))
    );
    render(Panel, { warehouseId: 'matrix' });
    const next = await screen.findByRole('button', { name: 'Siguiente' });
    await waitFor(() => expect(next).not.toBeDisabled());
    mocks.list.mockResolvedValue([row]);
    await fireEvent.click(next);
    await waitFor(() => expect(mocks.list.mock.calls[1]?.[3]).toBe(25));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Siguiente' })).toBeDisabled());
    await fireEvent.click(screen.getByRole('button', { name: 'Limpiar filtros' }));
    await waitFor(() => expect(mocks.list.mock.calls[2]?.[3]).toBe(0));
    expect(mocks.list.mock.calls[2]?.[4]).toMatchObject({ period_from: '', period_to: '' });
  });
  it('ofrece reintento y un vacío con recuperación', async () => {
    mocks.list.mockRejectedValueOnce(new Error('Sin conexión')).mockResolvedValue([]);
    render(Panel, { warehouseId: 'matrix' });
    expect(await screen.findByRole('alert')).toHaveTextContent('Sin conexión');
    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar consulta' }));
    expect(await screen.findByText('No hay movimientos con estos filtros')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ver todo el historial' })).toBeInTheDocument();
  });
  it('descarta una respuesta anterior al cambiar de bodega o contexto', async () => {
    let finish!: (rows: InventoryMovementHistory[]) => void;
    mocks.list
      .mockReturnValueOnce(
        new Promise((resolve) => {
          finish = resolve;
        })
      )
      .mockResolvedValue([]);
    const view = render(Panel, { warehouseId: 'matrix', contextKey: 'company-1' });
    await waitFor(() => expect(mocks.list).toHaveBeenCalledOnce());
    await view.rerender({ warehouseId: 'branch', contextKey: 'company-2' });
    await screen.findByText('No hay movimientos con estos filtros');
    finish([row]);
    await Promise.resolve();
    expect(screen.queryByText(row.product_name!)).not.toBeInTheDocument();
    expect(mocks.list.mock.calls[0]?.[5].aborted).toBe(true);
  });
});
