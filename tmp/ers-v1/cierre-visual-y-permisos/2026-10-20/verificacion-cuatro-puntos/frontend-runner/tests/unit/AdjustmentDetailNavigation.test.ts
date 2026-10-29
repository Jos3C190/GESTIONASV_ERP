import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';
import AdjustmentDetail from '../../src/routes/(app)/inventory/adjustments/[id]/+page.svelte';

const mocks = vi.hoisted(() => ({ get: vi.fn(), apply: vi.fn(), correction: vi.fn(), goto: vi.fn(), canApprove: false, canManage: false }));
vi.mock('$app/navigation', () => ({ goto: mocks.goto }));
vi.mock('$lib/stores/company.svelte', () => ({ company: { id: 'company-1' } }));
vi.mock('$lib/stores/branch.svelte', () => ({ branch: { id: 'branch-1' } }));
vi.mock('$lib/stores/permissions.svelte', () => ({ permissions: { hasPermission: (permission: string) => permission === 'inventory:adjust_approve' ? mocks.canApprove : permission === 'inventory:adjust' && mocks.canManage } }));
vi.mock('$lib/features/inventory/adjustments', () => ({ inventoryAdjustmentsApi: { get: mocks.get, apply: mocks.apply, correction: mocks.correction } }));

function adjustment(status: 'draft' | 'approved' | 'applied') {
  return {
    id: 'adjustment-1', company_id: 'company-1', code: 'AJ-DEMO-1', warehouse_id: 'warehouse-1', warehouse_name: 'Bodega ficticia',
    branch_id: 'branch-1', operational_date: '2026-10-20', accounting_date: '2026-10-20', reason: 'Prueba de recuperación',
    document_reference: 'ACTA-DEMO', notes: null, status, version: 1, approved_version: 1,
    correction_of_id: null, transfer_id: null, transfer_incident_id: null, created_by_id: 'user-1',
    approved_by_id: 'user-1', applied_by_id: status === 'applied' ? 'user-1' : null,
    created_at: '2026-10-20T12:00:00Z', approved_at: '2026-10-20T12:01:00Z',
    applied_at: status === 'applied' ? '2026-10-20T12:02:00Z' : null, cancellation_reason: null,
    lines: [], documents: [{ document_id: 'doc-1', original_filename: 'acta.pdf', checksum_sha256: 'a'.repeat(64), technical_status: 'active', upload_completed: true, linked_at: '2026-10-20T12:00:00Z', detached_at: null, active: true }], events: []
  };
}

beforeEach(() => {
  mocks.get.mockReset();
  mocks.apply.mockReset();
  mocks.correction.mockReset();
  mocks.goto.mockReset();
  mocks.canApprove = false;
  mocks.canManage = false;
});

it('carga el nuevo ajuste cuando la navegación mantiene la misma ruta de detalle', async () => {
  mocks.get.mockImplementation(async (id: string) => ({
    id, company_id: 'company-1', code: `AJ-${id}`, warehouse_id: 'warehouse-1', warehouse_name: 'Bodega ficticia',
    branch_id: 'branch-1', operational_date: '2026-10-20', accounting_date: '2026-10-20', reason: 'Prueba de navegación',
    document_reference: 'ACTA-DEMO', notes: null, status: 'draft', version: 1, approved_version: null,
    correction_of_id: null, transfer_id: null, transfer_incident_id: null, created_by_id: 'user-1',
    approved_by_id: null, applied_by_id: null, created_at: '2026-10-20T12:00:00Z', approved_at: null,
    applied_at: null, cancellation_reason: null, lines: [], documents: [], events: []
  }));
  const view = render(AdjustmentDetail, { data: { adjustmentId: 'one' } });
  expect(await screen.findByRole('heading', { name: 'AJ-one' })).toBeInTheDocument();
  await view.rerender({ data: { adjustmentId: 'two' } });
  await waitFor(() => expect(mocks.get).toHaveBeenLastCalledWith('two'));
  expect(await screen.findByRole('heading', { name: 'AJ-two' })).toBeInTheDocument();
  expect(screen.queryByRole('heading', { name: 'AJ-one' })).not.toBeInTheDocument();
});

it('recupera una aplicación confirmada aunque se haya perdido la respuesta', async () => {
  mocks.canApprove = true;
  mocks.get.mockResolvedValueOnce(adjustment('approved')).mockResolvedValueOnce(adjustment('applied'));
  mocks.apply.mockRejectedValueOnce(new Error('Respuesta interrumpida'));
  HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  HTMLDialogElement.prototype.close = function () { this.open = false; };

  render(AdjustmentDetail, { data: { adjustmentId: 'adjustment-1' } });
  await screen.findByRole('heading', { name: 'AJ-DEMO-1' });
  await fireEvent.click(screen.getByRole('button', { name: 'Aplicar ajuste…' }));
  await fireEvent.click(screen.getByRole('button', { name: 'Aplicar ajuste ahora' }));

  expect(await screen.findByRole('status')).toHaveTextContent('la consulta confirmó que el ajuste ya se aplicó');
  expect(mocks.apply).toHaveBeenCalledTimes(1);
  expect(mocks.get).toHaveBeenCalledTimes(2);
  expect(screen.queryByRole('button', { name: 'Aplicar ajuste…' })).not.toBeInTheDocument();
});

it('crea desde la ficha una corrección enlazada sin reemplazar el ajuste aplicado', async () => {
  mocks.canManage = true;
  mocks.get.mockResolvedValue(adjustment('applied'));
  mocks.correction.mockResolvedValue({ ...adjustment('draft'), id: 'correction-1', code: 'AJ-CORR-1', correction_of_id: 'adjustment-1' });

  render(AdjustmentDetail, { data: { adjustmentId: 'adjustment-1' } });
  await screen.findByRole('heading', { name: 'AJ-DEMO-1' });
  await fireEvent.click(screen.getByRole('button', { name: 'Corregir movimiento…' }));
  await fireEvent.input(screen.getByLabelText('Motivo'), { target: { value: 'Error detectado en el conteo' } });
  await fireEvent.input(screen.getByLabelText('Referencia documental'), { target: { value: 'ACTA-CORR-UI-001' } });
  await fireEvent.click(screen.getByRole('button', { name: 'Crear borrador de corrección' }));

  await waitFor(() => expect(mocks.correction).toHaveBeenCalledTimes(1));
  const correctionCall = mocks.correction.mock.calls[0];
  expect(correctionCall).toBeDefined();
  const payload = correctionCall![1];
  expect(payload).toMatchObject({
    operational_date: expect.any(String),
    accounting_date: expect.any(String),
    reason: 'Error detectado en el conteo',
    document_reference: 'ACTA-CORR-UI-001'
  });
  expect(payload.accounting_date).toBe(payload.operational_date);
  expect(mocks.goto).toHaveBeenCalledWith('/inventory/adjustments/correction-1');
  expect(screen.getByRole('heading', { name: 'AJ-DEMO-1' })).toBeInTheDocument();
  expect(screen.getByText('Aplicado y consultable en Kardex. Las nuevas entradas siguen en cuarentena.')).toBeInTheDocument();
});
