import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { expect, it, vi } from 'vitest';
import AdjustmentDraftEditor from '../../src/lib/features/inventory/components/AdjustmentDraftEditor.svelte';

const mocks = vi.hoisted(() => ({ create: vi.fn(), goto: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto: mocks.goto }));
vi.mock('$lib/stores/company.svelte', () => ({ company: { id: 'company-1' } }));
vi.mock('$lib/stores/branch.svelte', () => ({ branch: { id: 'branch-1' } }));
vi.mock('$lib/stores/permissions.svelte', () => ({ permissions: { hasPermission: () => true } }));
vi.mock('$lib/services/warehouses', () => ({ getWarehouses: vi.fn().mockResolvedValue({ items: [{ id: 'origin', name: 'Central', code: 'C', type: 'general', status: 'active' }] }) }));
vi.mock('$lib/features/inventory/services', () => ({ inventoryApi: { listHandlingUnits: vi.fn().mockResolvedValue([{ id: 'hu-1', code: 'HU-DEMO', location_id: 'vehicle-location', stock_status: 'in_transit', quantity_base: '2' }]) } }));
vi.mock('$lib/features/inventory/adjustments', () => ({ inventoryAdjustmentsApi: { create: mocks.create } }));
vi.mock('$lib/features/inventory/transfer-documents', () => ({ inventoryTransfersApi: {
  get: vi.fn().mockResolvedValue({ id: 'transfer-1', code: 'TR-DEMO', status: 'incident', origin_warehouse_id: 'origin', vehicle: { id: 'vehicle-1' },
    incidents: [{ id: 'incident-1', status: 'open', reason: 'Faltante documentado' }],
    lines: [{ id: 'detail-1', inventory_item_id: 'item-1', product_name: 'Producto de prueba', quantity_in_transit: '2', transit_handling_unit_id: 'hu-1' }] }),
  listVehicles: vi.fn().mockResolvedValue([{ id: 'vehicle-1', transit_warehouse_id: 'transit' }])
} }));

it('permite justificar el faltante conservando el origen de traslado y la unidad en tránsito', async () => {
  mocks.create.mockResolvedValue({ id: 'adjustment-1' });
  render(AdjustmentDraftEditor, { transferId: 'transfer-1', incidentId: 'incident-1', detailId: 'detail-1' });
  const reason = await screen.findByLabelText('Motivo');
  const reference = screen.getByLabelText('Referencia documental');
  expect(reason).toBeEnabled();
  expect(reason).toHaveClass('w-full', 'border-border', 'bg-surface', 'text-foreground');
  expect(reference).toBeEnabled();
  await fireEvent.input(reason, { target: { value: 'Faltante revisado en la recepción' } });
  await fireEvent.input(reference, { target: { value: 'ACTA-DEMO-01' } });
  await fireEvent.click(screen.getByRole('button', { name: 'Guardar borrador' }));
  await waitFor(() => expect(mocks.create).toHaveBeenCalledOnce());
  expect(mocks.create).toHaveBeenCalledWith(expect.objectContaining({ transfer_id: 'transfer-1',
    transfer_incident_id: 'incident-1', reason: 'Faltante revisado en la recepción', document_reference: 'ACTA-DEMO-01',
    lines: [expect.objectContaining({ handling_unit_id: 'hu-1', stock_status: 'in_transit', transfer_detail_id: 'detail-1' })] }));
});
