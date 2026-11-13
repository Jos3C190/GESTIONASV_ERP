import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';
import AdjustmentDetail from '../../src/routes/(app)/inventory/adjustments/[id]/+page.svelte';

const mocks = vi.hoisted(() => ({ get: vi.fn(), apply: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('$lib/stores/company.svelte', () => ({ company: { id: 'company-1' } }));
vi.mock('$lib/stores/branch.svelte', () => ({ branch: { id: 'branch-1' } }));
vi.mock('$lib/stores/permissions.svelte', () => ({ permissions: { hasPermission: () => true } }));
vi.mock('$lib/features/inventory/adjustments', () => ({
  inventoryAdjustmentsApi: { get: mocks.get, apply: mocks.apply }
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
  mocks.apply.mockReset();
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function () {
    this.open = false;
  };
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

const line = {
  id: 'line-1',
  line_number: 1,
  inventory_item_id: 'item-1',
  warehouse_id: 'warehouse-1',
  location_id: 'loc-1',
  location_code: 'VEH-VEH-SM-01',
  product_name: 'Producto de prueba',
  sku: 'SKU-DEMO',
  base_unit_id: 1,
  base_unit_name: 'Unidad (u)',
  base_unit_symbol: 'u',
  direction: 'decrease',
  quantity_base: '4.000000',
  stock_status: 'quarantine',
  handling_unit_code: null,
  handling_unit_id: null,
  inventory_lot_detail_id: null,
  documented_unit_cost: null,
  documented_total_cost: null,
  movement_id: null
};

it('muestra cantidades, unidad y ubicación sin ruido y el historial en español', async () => {
  mocks.get.mockResolvedValue(
    adjustment({
      lines: [line],
      events: [
        {
          action: 'created',
          actor_id: 'u',
          occurred_at: '2026-10-20T12:00:00Z',
          reason: null,
          version: 1,
          details: {}
        },
        {
          action: 'approved',
          actor_id: 'u',
          occurred_at: '2026-10-20T12:05:00Z',
          reason: null,
          version: 1,
          details: {}
        }
      ],
      documents: [
        {
          document_id: 'doc-1',
          original_filename: 'acta.pdf',
          checksum_sha256: 'a'.repeat(64),
          technical_status: 'active',
          upload_completed: true,
          linked_at: '2026-10-20T12:00:00Z',
          detached_at: null,
          active: true
        }
      ]
    })
  );
  render(AdjustmentDetail, { data: { adjustmentId: 'adjustment-1' } });
  expect(await screen.findByText('Salida · −4 u')).toBeInTheDocument();
  expect(screen.getByText('SKU-DEMO · Unidad (u)')).toBeInTheDocument();
  expect(screen.getByText(/Ubicación VEH-SM-01/)).toBeInTheDocument();
  expect(screen.queryByText(/VEH-VEH/)).not.toBeInTheDocument();
  // The label and its value are separate elements; the space between them must survive.
  expect(document.body.textContent).toMatch(/Condición:[\s\u00a0]+Cuarentena/);
  expect(screen.getByText('Borrador creado')).toBeInTheDocument();
  expect(screen.getByText('Aprobado')).toBeInTheDocument();
  expect(screen.getByText(/Vinculado · Validado/)).toBeInTheDocument();
  expect(screen.queryByText(/^(created|approved)$|\bactive\b/)).not.toBeInTheDocument();
});

it('si aplicar falla con valuación pendiente, cierra la confirmación y muestra el error', async () => {
  mocks.get.mockResolvedValue(adjustment({ status: 'approved', lines: [line] }));
  mocks.apply.mockRejectedValue(
    Object.assign(new Error('x'), { code: 'valuation_opening_required', status: 409 })
  );
  render(AdjustmentDetail, { data: { adjustmentId: 'adjustment-1' } });
  await fireEvent.click(await screen.findByRole('button', { name: 'Aplicar ajuste…' }));
  const dialog = document.querySelector('dialog')!;
  expect(dialog.open).toBe(true);
  await fireEvent.click(screen.getByRole('button', { name: 'Aplicar ajuste ahora' }));
  await waitFor(() => expect(dialog.open).toBe(false));
  expect(
    await screen.findByText(/Primero aprueba el saldo inicial de valuación de la empresa/)
  ).toBeInTheDocument();
});
