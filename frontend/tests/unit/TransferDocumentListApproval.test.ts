import { fireEvent, render, screen } from '@testing-library/svelte';
import { expect, it, vi } from 'vitest';
import TransferDocumentList from '../../src/lib/features/inventory/components/TransferDocumentList.svelte';
import type { InventoryTransfer } from '../../src/lib/features/inventory/transfer-documents';
import { makeTransfer } from './fixtures/inventory-transfer';

const listProps = {
  state: 'loaded' as const,
  error: null,
  filter: '' as const,
  statuses: [{ value: '' as const, label: 'Todos los estados' }],
  hasMore: false,
  loadingMore: false,
  formatDate: () => '19/10/2026',
  documentSummary: () => 'Resumen',
  onFilter: vi.fn(),
  onRetry: vi.fn(),
  onOpen: vi.fn(),
  onLoadMore: vi.fn()
};

const central = makeTransfer({ status: 'in_transit' });

it('distingue por color y texto lo pendiente de aprobación y lo aprobado, e indica la ruta de sucursal', () => {
  const pending: InventoryTransfer = makeTransfer({
    id: 'p',
    code: 'TR-PEND',
    status: 'pending_approval',
    route_type: 'branch_to_branch'
  });
  const approved: InventoryTransfer = makeTransfer({
    id: 'a',
    code: 'TR-APPR',
    status: 'approved',
    route_type: 'branch_to_central'
  });
  render(TransferDocumentList, { ...listProps, transfers: [pending, approved, central] });

  const pendingCard = screen.getByRole('button', { name: /TR-PEND/ });
  const pendingBadge = pendingCard.querySelector('[data-status="pending_approval"]');
  expect(pendingBadge).toHaveTextContent('Pendiente de aprobación');
  expect(pendingBadge?.className).toContain('text-warning');
  expect(pendingCard).toHaveTextContent('Entre sucursales');

  const approvedCard = screen.getByRole('button', { name: /TR-APPR/ });
  const approvedBadge = approvedCard.querySelector('[data-status="approved"]');
  expect(approvedBadge).toHaveTextContent('Aprobado');
  expect(approvedBadge?.className).toContain('text-primary');
  expect(approvedCard).toHaveTextContent('Retorno a matriz');

  // La distribución de siempre no suma ruido a cada tarjeta.
  expect(screen.getByRole('button', { name: /TR-DEMO-A/ })).not.toHaveTextContent(
    'Distribución desde matriz'
  );
});

it('ofrece «Por aprobar» solo a quien puede aprobar y avisa cuántos esperan', async () => {
  const onAwaitingApproval = vi.fn();
  const view = render(TransferDocumentList, { ...listProps, transfers: [central] });
  expect(screen.queryByRole('button', { name: /Por aprobar/ })).not.toBeInTheDocument();

  await view.rerender({ canApprove: true, pendingApprovalCount: 3, onAwaitingApproval });
  expect(screen.getByRole('button', { name: 'Todos' })).toHaveAttribute('aria-pressed', 'true');
  await fireEvent.click(screen.getByRole('button', { name: 'Por aprobar (3)' }));
  expect(onAwaitingApproval).toHaveBeenCalledWith(true);

  await view.rerender({ awaitingApproval: true });
  expect(screen.getByRole('button', { name: 'Por aprobar (3)' })).toHaveAttribute(
    'aria-pressed',
    'true'
  );
  expect(screen.getByLabelText('Estado')).toBeDisabled();
});

it('explica una bandeja vacía de aprobaciones sin confundirla con un estado vacío', () => {
  render(TransferDocumentList, {
    ...listProps,
    transfers: [],
    state: 'empty',
    canApprove: true,
    awaitingApproval: true
  });
  expect(screen.getByText('No tienes traslados por aprobar')).toBeInTheDocument();
  expect(screen.queryByText('No hay documentos en este estado')).not.toBeInTheDocument();
});
