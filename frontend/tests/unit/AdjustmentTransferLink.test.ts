import { render, screen } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';
import AdjustmentDetail from '../../src/routes/(app)/inventory/adjustments/[id]/+page.svelte';

const mocks = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('$lib/stores/company.svelte', () => ({ company: { id: 'company-1' } }));
vi.mock('$lib/stores/branch.svelte', () => ({ branch: { id: 'branch-1' } }));
vi.mock('$lib/stores/permissions.svelte', () => ({ permissions: { hasPermission: () => true } }));
vi.mock('$lib/features/inventory/adjustments', () => ({
  inventoryAdjustmentsApi: { get: mocks.get }
}));

function adjustment(patch: Record<string, unknown> = {}) {
  return {
    id: 'adjustment-1',
    company_id: 'company-1',
    code: 'AJ-DEMO-1',
    warehouse_id: 'warehouse-1',
    warehouse_name: 'Bodega ficticia',
    branch_id: 'branch-1',
    operational_date: '2026-10-20',
    accounting_date: '2026-10-20',
    reason: 'Prueba de vínculo',
    document_reference: 'ACTA-DEMO',
    notes: null,
    status: 'draft',
    version: 1,
    approved_version: null,
    correction_of_id: null,
    transfer_id: null,
    transfer_incident_id: null,
    transfer_discrepancy_id: null,
    transfer_discrepancy_kind: null,
    transfer_reference: null,
    linked_transfer_id: null,
    created_by_id: 'user-1',
    approved_by_id: null,
    applied_by_id: null,
    created_at: '2026-10-20T12:00:00Z',
    approved_at: null,
    applied_at: null,
    cancellation_reason: null,
    lines: [],
    documents: [],
    events: [],
    ...patch
  };
}

beforeEach(() => {
  mocks.get.mockReset();
});

it.each([
  ['surplus', 'Sobrante'],
  ['damage', 'Avería'],
  ['shortage', 'Faltante']
])('un ajuste de %s indica a qué traslado está vinculado y no se edita', async (kind, label) => {
  mocks.get.mockResolvedValue(
    adjustment({
      transfer_discrepancy_id: 'disc-1',
      transfer_discrepancy_kind: kind,
      transfer_reference: 'TR-DEMO-A',
      linked_transfer_id: 'transfer-a',
      // A shortage also carries the transfer; damage and surplus only the discrepancy.
      transfer_id: kind === 'shortage' ? 'transfer-a' : null
    })
  );
  render(AdjustmentDetail, { data: { adjustmentId: 'adjustment-1' } });
  expect(
    await screen.findByRole('heading', { name: `Vinculado a ${label} del traslado TR-DEMO-A` })
  ).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /Abrir el traslado TR-DEMO-A/ })).toHaveAttribute(
    'href',
    '/transfers?transfer=transfer-a'
  );
  expect(screen.queryByRole('button', { name: 'Editar borrador' })).not.toBeInTheDocument();
});

it('un ajuste común sigue pudiéndose editar y no muestra vínculo', async () => {
  mocks.get.mockResolvedValue(adjustment());
  render(AdjustmentDetail, { data: { adjustmentId: 'adjustment-1' } });
  expect(await screen.findByRole('button', { name: 'Editar borrador' })).toBeInTheDocument();
  expect(screen.queryByText(/Vinculado a/)).not.toBeInTheDocument();
});

it('un ajuste aplicado vinculado no ofrece corregir el movimiento', async () => {
  mocks.get.mockResolvedValue(
    adjustment({
      status: 'applied',
      transfer_discrepancy_id: 'disc-1',
      transfer_discrepancy_kind: 'damage',
      transfer_reference: 'TR-DEMO-A',
      linked_transfer_id: 'transfer-a'
    })
  );
  render(AdjustmentDetail, { data: { adjustmentId: 'adjustment-1' } });
  await screen.findByRole('heading', { name: /Vinculado a Avería/ });
  expect(screen.queryByRole('button', { name: 'Corregir movimiento…' })).not.toBeInTheDocument();
});
