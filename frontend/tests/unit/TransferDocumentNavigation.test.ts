import { fireEvent, render, screen } from '@testing-library/svelte';
import { expect, it, vi } from 'vitest';
import TransferDocumentList from '../../src/lib/features/inventory/components/TransferDocumentList.svelte';
import type { InventoryTransfer } from '../../src/lib/features/inventory/transfer-documents';

const transfer: InventoryTransfer = {
  id: 'transfer-a', company_id: 'company-1', code: 'TR-DEMO-A',
  origin_warehouse_id: 'origin', origin_warehouse_name: 'Central', origin_branch_id: 'matrix',
  destination_warehouse_id: 'destination', destination_warehouse_name: 'Sucursal', destination_branch_id: 'branch',
  vehicle: null, status: 'in_transit', notes: null, created_by_id: 'user-1',
  created_at: '2026-10-19T12:00:00Z', dispatched_by_id: 'user-1', dispatched_at: '2026-10-19T12:01:00Z',
  received_by_id: null, received_at: null, dispatch_movement_id: 'movement-1', lines: [], incidents: []
};

it('bloquea el cambio de documento mientras se confirma una operación y lo permite al terminar', async () => {
  const onOpen = vi.fn();
  const view = render(TransferDocumentList, {
    transfers: [transfer], state: 'loaded', error: null, filter: '', statuses: [{ value: '', label: 'Todos' }],
    hasMore: true, loadingMore: false, busy: true, formatDate: () => '19/10/2026', documentSummary: () => 'En tránsito',
    onFilter: vi.fn(), onRetry: vi.fn(), onOpen, onLoadMore: vi.fn()
  });
  const document = screen.getByRole('button', { name: /TR-DEMO-A/ });
  expect(document).toBeDisabled();
  expect(screen.getByLabelText('Estado')).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Cargar más documentos' })).toBeDisabled();
  await fireEvent.click(document);
  expect(onOpen).not.toHaveBeenCalled();
  await view.rerender({ busy: false });
  expect(document).toBeEnabled();
  await fireEvent.click(document);
  expect(onOpen).toHaveBeenCalledWith('transfer-a');
});
