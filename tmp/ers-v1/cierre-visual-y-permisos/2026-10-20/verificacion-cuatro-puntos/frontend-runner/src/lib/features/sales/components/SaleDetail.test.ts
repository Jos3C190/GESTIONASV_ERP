import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';
import { permissions } from '$lib/stores/permissions.svelte';
import { confirmation } from '$lib/stores/confirmation.svelte';
import SaleDetail from './SaleDetail.svelte';

const { salesApi } = vi.hoisted(() => ({ salesApi: { sale: vi.fn(), updateSale: vi.fn(), confirmSale: vi.fn() } }));
vi.mock('$lib/api/sales', () => ({ salesApi }));

const draft = {
  id: 'sale-dirty', status: 'draft', version: 1, code: 'VTA-DEMO', customer_name: 'Cliente de prueba',
  quotation_id: 'quote-1', quotation_code: 'CV-DEMO', currency: 'USD', subtotal: '10', total: '10',
  delivery_progress: 'pending', notes: null,
  lines: [{ id: 'line-1', source_quotation_line_id: 'source-1', product_name: 'Producto de prueba',
    product_sku: 'DEMO', unit_name: 'Unidad', base_unit_name: 'u', unit_factor: '1', quantity: '1.000000',
    unit_price: '10.000000', line_total: '10', quantity_delivered_base: '0', quantity_pending_base: '1' }]
};

beforeEach(() => {
  confirmation.reset();
  permissions.set(['sales:manage', 'sales:confirm'], false);
  salesApi.sale.mockReset().mockResolvedValue(draft);
  salesApi.updateSale.mockReset().mockResolvedValue({ ...draft, version: 2, lines: [{ ...draft.lines[0], quantity: '2.000000' }] });
  salesApi.confirmSale.mockReset().mockResolvedValue({ ...draft, status: 'confirmed', version: 3 });
});

it('solicita confirmación dentro de la aplicación y cancelar no ejecuta la venta', async () => {
  const view = render(SaleDetail, { id: draft.id });
  await fireEvent.click(await screen.findByRole('button', { name: 'Confirmar venta' }));
  expect(confirmation.current?.title).toBe('Confirmar VTA-DEMO');
  expect(confirmation.current?.description).toContain('no descuenta inventario');
  expect(salesApi.confirmSale).not.toHaveBeenCalled();
  confirmation.cancel();
  expect(confirmation.open).toBe(false);
  expect(salesApi.confirmSale).not.toHaveBeenCalled();
  view.unmount();
});

it('solo confirma la revisión capturada al aceptar el diálogo', async () => {
  const view = render(SaleDetail, { id: draft.id });
  await fireEvent.click(await screen.findByRole('button', { name: 'Confirmar venta' }));
  await confirmation.proceed();
  expect(salesApi.confirmSale).toHaveBeenCalledExactlyOnceWith(draft.id, draft.version);
  expect(confirmation.open).toBe(false);
  view.unmount();
});

it('salir del detalle cancela una confirmación pendiente', async () => {
  const view = render(SaleDetail, { id: draft.id });
  await fireEvent.click(await screen.findByRole('button', { name: 'Confirmar venta' }));
  view.unmount();
  expect(confirmation.open).toBe(false);
  await confirmation.proceed();
  expect(salesApi.confirmSale).not.toHaveBeenCalled();
});

it('exige guardar cantidades editadas antes de confirmar los términos de la venta', async () => {
  render(SaleDetail, { id: draft.id });
  const confirm = await screen.findByRole('button', { name: 'Confirmar venta' });
  expect(confirm).toBeEnabled();
  await fireEvent.input(screen.getByLabelText('Cantidad de Producto de prueba'), { target: { value: '2' } });
  expect(confirm).toBeDisabled();
  expect(screen.getByRole('status')).toHaveTextContent('Guarda los cambios');
  expect(salesApi.confirmSale).not.toHaveBeenCalled();
  const save = screen.getByRole('button', { name: 'Guardar borrador' });
  expect(save).toHaveAttribute('type', 'submit');
  await fireEvent.submit(save.closest('form')!);
  await waitFor(() => expect(salesApi.updateSale).toHaveBeenCalledOnce());
  await waitFor(() => expect(screen.getByRole('button', { name: 'Confirmar venta' })).toBeEnabled());
});
