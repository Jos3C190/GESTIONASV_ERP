import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';
import TransferOperationsPage from '../../src/lib/features/inventory/components/TransferOperationsPage.svelte';
import type { InventoryTransfer } from '../../src/lib/features/inventory/transfer-documents';

const mocks = vi.hoisted(() => ({
  get: vi.fn(), list: vi.fn(), openIncident: vi.fn(), resolveIncident: vi.fn(), receive: vi.fn(),
  getWarehouses: vi.fn(), listLocations: vi.fn(), listTransferUnits: vi.fn(), listDemand: vi.fn(), listVehicles: vi.fn(),
  canOperate: true
}));
vi.mock('$lib/stores/company.svelte', () => ({ company: { id: 'company-1' } }));
vi.mock('$lib/stores/branch.svelte', () => ({ branch: { id: null, ready: true, accessAllBranches: true, branches: [] } }));
vi.mock('$lib/stores/permissions.svelte', () => ({ permissions: { hasPermission: () => mocks.canOperate } }));
vi.mock('$lib/services/warehouses', () => ({ getWarehouses: mocks.getWarehouses }));
vi.mock('$lib/features/locations/services', () => ({ listLocations: mocks.listLocations }));
vi.mock('$lib/features/inventory/services', () => ({ inventoryApi: { listTransferUnits: mocks.listTransferUnits } }));
vi.mock('$lib/features/inventory/transfer-documents', () => ({ inventoryTransfersApi: {
  get: mocks.get, list: mocks.list, openIncident: mocks.openIncident, resolveIncident: mocks.resolveIncident,
  receive: mocks.receive, listDemand: mocks.listDemand, listVehicles: mocks.listVehicles
} }));

const transfer: InventoryTransfer = {
  id: 'transfer-a', company_id: 'company-1', code: 'TR-DEMO-A',
  origin_warehouse_id: 'origin', origin_warehouse_name: 'Central', origin_branch_id: 'matrix',
  destination_warehouse_id: 'destination', destination_warehouse_name: 'Sucursal', destination_branch_id: 'branch',
  vehicle: null, status: 'in_transit', notes: null, created_by_id: 'user-1',
  created_at: '2026-10-19T12:00:00Z', dispatched_by_id: 'user-1', dispatched_at: '2026-10-19T12:01:00Z',
  received_by_id: null, received_at: null, dispatch_movement_id: 'movement-1', lines: [], incidents: []
};

beforeEach(() => {
  mocks.canOperate = true;
  mocks.get.mockReset().mockResolvedValue(transfer);
  mocks.list.mockReset().mockResolvedValue([transfer]);
  mocks.openIncident.mockReset();
  mocks.resolveIncident.mockReset();
  mocks.receive.mockReset();
  mocks.getWarehouses.mockReset().mockResolvedValue({ items: [], meta: { pages: 1 } });
  mocks.listLocations.mockReset().mockResolvedValue({ items: [], meta: { pages: 1 } });
  mocks.listTransferUnits.mockReset().mockResolvedValue([]);
  mocks.listDemand.mockReset().mockResolvedValue([]);
  mocks.listVehicles.mockReset().mockResolvedValue([]);
  sessionStorage.clear();
});

async function openDocument() {
  render(TransferOperationsPage);
  await fireEvent.click(await screen.findByRole('button', { name: 'Documentos' }));
  await fireEvent.click(await screen.findByRole('button', { name: /TR-DEMO-A/ }));
}

it('envía los formularios de incidencia y resolución mediante controles submit', async () => {
  await openDocument();
  await fireEvent.click(await screen.findByRole('button', { name: 'Reportar incidencia' }));
  await fireEvent.input(screen.getByLabelText('Motivo de la incidencia'), { target: { value: 'Faltante revisado en destino' } });
  const saveIncident = screen.getByRole('button', { name: 'Guardar incidencia' });
  expect(saveIncident).toHaveAttribute('type', 'submit');
  const incident: InventoryTransfer = { ...transfer, status: 'incident', incidents: [{
    id: 'incident-1', status: 'open', reason: 'Faltante revisado en destino', evidence_reference: null,
    opened_by_id: 'user-1', opened_at: '2026-10-19T12:02:00Z', resolution: null, resolution_notes: null,
    resolved_by_id: null, resolved_at: null
  }] };
  mocks.openIncident.mockResolvedValue(incident);
  mocks.get.mockResolvedValue(incident);
  mocks.list.mockResolvedValue([incident]);
  await fireEvent.submit(saveIncident.closest('form')!);
  await waitFor(() => expect(mocks.openIncident).toHaveBeenCalledWith('transfer-a', expect.objectContaining({ reason: 'Faltante revisado en destino', idempotency_key: expect.any(String) })));
  await fireEvent.click(await screen.findByRole('button', { name: 'Resolver incidencia autorizada' }));
  await fireEvent.input(screen.getByLabelText('Notas de resolución'), { target: { value: 'Se puede reanudar el tránsito' } });
  const saveResolution = screen.getByRole('button', { name: 'Guardar resolución' });
  expect(saveResolution).toHaveAttribute('type', 'submit');
  mocks.resolveIncident.mockResolvedValue(transfer);
  mocks.get.mockResolvedValue(transfer);
  mocks.list.mockResolvedValue([transfer]);
  await fireEvent.submit(saveResolution.closest('form')!);
  await waitFor(() => expect(mocks.resolveIncident).toHaveBeenCalledWith('transfer-a', expect.objectContaining({ resolution: 'resume_transit', resolution_notes: 'Se puede reanudar el tránsito', idempotency_key: expect.any(String) })));
});

it('no ofrece registrar incidencias a un perfil de consulta', async () => {
  mocks.canOperate = false;
  await openDocument();
  expect(await screen.findByRole('button', { name: 'Reportar incidencia' })).toBeDisabled();
  expect(mocks.openIncident).not.toHaveBeenCalled();
});

it('distingue la cantidad recibida del faltante autorizado al cerrar con ajuste', async () => {
  mocks.get.mockResolvedValue({ ...transfer, status: 'closed_with_adjustment', lines: [{
    id: 'line-1', line_number: 1, inventory_item_id: 'item-1', product_id: 1, variant_id: null,
    sku: 'SKU-DEMO', product_name: 'Producto de incidencia', base_unit_id: 1, base_unit_name: 'Unidad',
    base_unit_symbol: 'u', presentation_name: null, inventory_lot_detail_id: null, inventory_lot_detail_code: null,
    source_handling_unit_id: 'hu-source', source_handling_unit_code: 'HU-SOURCE', transit_handling_unit_id: 'hu-transit',
    transit_handling_unit_code: 'HU-TRANSIT', quantity_planned: '3', quantity_dispatched: '3',
    quantity_received: '2', quantity_in_transit: '0', quantity_returned: '0', quantity_adjusted_out: '1',
    excess_reason: null, notes: null, demand_allocations: [], receipts: []
  }] });
  await openDocument();
  expect(await screen.findByText('Faltante documentado 1 u · Devuelto 0 u')).toBeInTheDocument();
  expect(screen.getByText('Despachado 3 · Recibido 2 · En tránsito 0')).toBeInTheDocument();
});

it('recupera una recepción parcial cuya respuesta se perdió y permite completar el saldo restante', async () => {
  const line: InventoryTransfer['lines'][number] = {
    id: 'line-1', line_number: 1, inventory_item_id: 'item-1', product_id: 1, variant_id: null,
    sku: 'SKU-DEMO', product_name: 'Producto de prueba', base_unit_id: 1, base_unit_name: 'Unidad',
    base_unit_symbol: 'u', presentation_name: null, inventory_lot_detail_id: null, inventory_lot_detail_code: null,
    source_handling_unit_id: 'hu-source', source_handling_unit_code: 'HU-SOURCE', transit_handling_unit_id: 'hu-transit',
    transit_handling_unit_code: 'HU-TRANSIT', quantity_planned: '3', quantity_dispatched: '3',
    quantity_received: '0', quantity_in_transit: '3', quantity_returned: '0', quantity_adjusted_out: '0',
    excess_reason: null, notes: null, demand_allocations: [], receipts: []
  };
  const initial = { ...transfer, lines: [line] };
  const partial = { ...initial, lines: [{ ...line, quantity_received: '2', quantity_in_transit: '1' }] };
  const final = { ...partial, status: 'received' as const, lines: [{ ...line, quantity_received: '3', quantity_in_transit: '0' }] };
  mocks.get.mockReset().mockResolvedValueOnce(initial).mockResolvedValueOnce(partial).mockResolvedValueOnce(final);
  mocks.list.mockResolvedValue([initial]);
  mocks.listLocations.mockResolvedValue({ items: [{
    id: 'location-1', warehouse_id: 'destination', capacity_group_id: null, code: 'SEC-01', area: null,
    aisle: 'SEC', rack: 'R01', level: 'N01', position: 'P01', certified_max_weight_kg: null,
    operational_max_weight_kg: null, certified_usable_volume_m3: null, operational_usable_volume_m3: null,
    capacity_profile: 'general_mixed', capacity_enforcement_mode: 'observe', capacity_status: 'available',
    storage_eligible: true, usable_length_m: null, usable_width_m: null, usable_height_m: null, notes: null,
    location_type: 'storage', lifecycle_status: 'active', barcode: null, verification_code: null,
    pick_sequence: null, putaway_sequence: null, external_id: null, scheme_id: null, scheme_version: null,
    code_source: 'generated', is_active: true, created_at: '2026-10-20T12:00:00Z', updated_at: null
  }], meta: { pages: 1 } });
  mocks.receive.mockRejectedValueOnce(new Error('Respuesta interrumpida')).mockResolvedValueOnce(final);

  await openDocument();
  const quantity = await screen.findByLabelText('Cantidad contada ahora');
  const location = await screen.findByLabelText('Ubicación de recepción / cuarentena');
  await fireEvent.input(quantity, { target: { value: '2' } });
  await fireEvent.change(location, { target: { value: 'location-1' } });
  await fireEvent.click(screen.getByRole('button', { name: 'Confirmar cantidades recibidas' }));

  expect(await screen.findByText(/La consulta confirmó las cantidades recibidas/)).toBeInTheDocument();
  expect(screen.getByText(/Recibido 2 · En tránsito 1/)).toBeInTheDocument();
  expect(screen.getByLabelText('Cantidad contada ahora')).toHaveValue(null);

  await fireEvent.input(screen.getByLabelText('Cantidad contada ahora'), { target: { value: '1' } });
  await fireEvent.change(screen.getByLabelText('Ubicación de recepción / cuarentena'), { target: { value: 'location-1' } });
  await fireEvent.click(screen.getByRole('button', { name: 'Confirmar cantidades recibidas' }));

  expect(await screen.findByText(/Traslado recibido\. La mercancía ingresó en cuarentena/)).toBeInTheDocument();
  expect(mocks.receive).toHaveBeenCalledTimes(2);
  expect(mocks.receive).toHaveBeenNthCalledWith(1, 'transfer-a', expect.any(String), [{ transfer_detail_id: 'line-1', destination_location_id: 'location-1', quantity_base: '2' }]);
  expect(mocks.receive).toHaveBeenNthCalledWith(2, 'transfer-a', expect.any(String), [{ transfer_detail_id: 'line-1', destination_location_id: 'location-1', quantity_base: '1' }]);
});
