import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';
import { permissions } from '$lib/stores/permissions.svelte';
import { confirmation } from '$lib/stores/confirmation.svelte';
import SalesQuotationDetail from './SalesQuotationDetail.svelte';
import ConfirmActionDialog from '$lib/components/ui/ConfirmActionDialog.svelte';

const { salesApi } = vi.hoisted(() => ({ salesApi: { quotation: vi.fn(), confirmQuotation: vi.fn() } }));
vi.mock('$lib/api/sales', () => ({ salesApi }));

const draft = {
  id: 'quote-ui', code: 'CV-UI', status: 'draft', version: 1, customer_name: 'Cliente ficticio',
  customer_code: 'DEMO', quotation_date: '2026-10-20', valid_until: '2026-10-27', currency: 'USD',
  total: '80', converted: false, lines: [], notes: null, branch_id: 'branch-1'
};

beforeEach(() => {
  confirmation.reset();
  permissions.set(['sales_quotations:confirm', 'sales_quotations:manage'], false);
  salesApi.quotation.mockReset().mockResolvedValue(draft);
  salesApi.confirmQuotation.mockReset().mockResolvedValue({ ...draft, status: 'confirmed', version: 2 });
});

it('cancelar el diálogo conserva el borrador y confirmar lo envía una sola vez', async () => {
  const dialogView = render(ConfirmActionDialog);
  const view = render(SalesQuotationDetail, { id: draft.id });
  const trigger = await screen.findByRole('button', { name: 'Confirmar cotización' });
  await fireEvent.click(trigger);
  expect(await screen.findByRole('alertdialog')).toHaveAccessibleName('Confirmar CV-UI');
  expect(confirmation.current?.confirmLabel).toBe('Confirmar cotización ahora');
  expect(salesApi.confirmQuotation).not.toHaveBeenCalled();
  await fireEvent.keyDown(window, { key: 'Escape' });
  expect(salesApi.confirmQuotation).not.toHaveBeenCalled();
  await fireEvent.click(trigger);
  await confirmation.proceed();
  expect(salesApi.confirmQuotation).toHaveBeenCalledExactlyOnceWith(draft.id, draft.version);
  expect(confirmation.open).toBe(false);
  view.unmount();
  dialogView.unmount();
});

it('al desmontar el documento no conserva una acción de la vista anterior', async () => {
  const view = render(SalesQuotationDetail, { id: draft.id });
  await fireEvent.click(await screen.findByRole('button', { name: 'Confirmar cotización' }));
  view.unmount();
  expect(confirmation.open).toBe(false);
  await confirmation.proceed();
  expect(salesApi.confirmQuotation).not.toHaveBeenCalled();
});

it('una falla conserva el diálogo con error y permite reintentar', async () => {
  const view = render(SalesQuotationDetail, { id: draft.id });
  salesApi.confirmQuotation.mockRejectedValueOnce(new Error('Sin conexión'));
  await fireEvent.click(await screen.findByRole('button', { name: 'Confirmar cotización' }));
  await confirmation.proceed();
  expect(confirmation.open).toBe(true);
  expect(confirmation.error).toContain('No se pudo confirmar');
  await confirmation.proceed();
  expect(confirmation.open).toBe(false);
  expect(salesApi.confirmQuotation).toHaveBeenCalledTimes(2);
  view.unmount();
});
