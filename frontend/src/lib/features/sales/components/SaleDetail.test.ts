import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';
import { permissions } from '#lib/stores/permissions.svelte.ts';
import { order, orderLine } from '#lib/features/sales/test-fixtures.ts';
import SaleDetail from './SaleDetail.svelte';

const { salesApi } = vi.hoisted(() => ({
  salesApi: {
    sale: vi.fn(),
    orderAction: vi.fn(),
    deliveriesForSale: vi.fn(),
    deliveryStock: vi.fn(),
    returnsForSale: vi.fn(),
    returnableAllocations: vi.fn()
  }
}));
vi.mock('#lib/api/sales.ts', () => ({ salesApi }));

const REASON = {
  code: 'discount_above_limit' as const,
  message: 'El descuento supera el tope de tu rol.'
};

beforeEach(() => {
  permissions.set(['sales:read', 'sales:manage', 'sales:confirm', 'sales:cancel'], false);
  salesApi.sale.mockReset();
  salesApi.orderAction.mockReset();
  for (const fn of [
    salesApi.deliveriesForSale,
    salesApi.deliveryStock,
    salesApi.returnsForSale,
    salesApi.returnableAllocations
  ]) {
    fn.mockReset().mockResolvedValue([]);
  }
});

it('confirma un borrador con su versión y muestra la entrega comprometida', async () => {
  const draft = order({ status: 'draft', version: 1, confirmed_at: null, confirmed_by_name: null });
  salesApi.sale.mockResolvedValue(draft);
  salesApi.orderAction.mockResolvedValue({ ...draft, status: 'confirmed', version: 2 });
  render(SaleDetail, { id: draft.id });
  expect(await screen.findByText('20/11/2026')).toBeInTheDocument();
  expect(screen.getByText('Contado')).toBeInTheDocument();
  await fireEvent.click(screen.getByRole('button', { name: 'Confirmar y apartar' }));
  expect(salesApi.orderAction).toHaveBeenCalledExactlyOnceWith(draft.id, 'confirm', {
    expected_version: 1
  });
  expect(await screen.findByText('Confirmado')).toBeInTheDocument();
});

it('avisa cuando el disponible de la sucursal no alcanza y muestra el error del servidor', async () => {
  const draft = order({
    status: 'draft',
    version: 1,
    lines: [orderLine({ quantity_base: '5.000000', available_base: '2.000000' })]
  });
  salesApi.sale.mockResolvedValue(draft);
  salesApi.orderAction.mockRejectedValue(new Error('x'));
  render(SaleDetail, { id: draft.id });
  expect(await screen.findByText(/Disponible en la sucursal: 2/)).toBeInTheDocument();
  await fireEvent.click(screen.getByRole('button', { name: 'Confirmar y apartar' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo completar la acción');
});

it('quien autoriza ve los motivos y devolver exige qué corregir', async () => {
  permissions.set(['sales:read', 'sales_discounts:authorize'], false);
  const pending = order({
    status: 'pending_authorization',
    version: 3,
    authorization_reasons: [REASON]
  });
  salesApi.sale.mockResolvedValue(pending);
  salesApi.orderAction.mockResolvedValue({ ...pending, status: 'draft', version: 4 });
  render(SaleDetail, { id: pending.id });
  expect(await screen.findByText('Espera autorización')).toBeInTheDocument();
  expect(screen.getByText(REASON.message)).toBeInTheDocument();
  await fireEvent.click(screen.getByRole('button', { name: 'Devolver a borrador' }));
  const submit = screen.getAllByRole('button', { name: 'Devolver a borrador' }).at(-1)!;
  expect(submit).toBeDisabled();
  await fireEvent.input(screen.getByPlaceholderText('Qué debe corregirse'), {
    target: { value: 'Baja el descuento' }
  });
  await fireEvent.click(submit);
  await waitFor(() =>
    expect(salesApi.orderAction).toHaveBeenCalledWith(pending.id, 'return', {
      expected_version: 3,
      reason: 'Baja el descuento'
    })
  );
});

it('el crédito lo autoriza quien controla el crédito, con motivo', async () => {
  const credit = {
    code: 'credit_limit_exceeded' as const,
    message: 'El pedido pasa el límite de crédito del cliente.'
  };
  const pending = order({
    status: 'pending_authorization',
    version: 5,
    authorization_reasons: [credit]
  });
  // Quien solo autoriza descuentos no puede autorizar crédito.
  permissions.set(['sales:read', 'sales_discounts:authorize'], false);
  salesApi.sale.mockResolvedValue(pending);
  const view = render(SaleDetail, { id: pending.id });
  expect(await screen.findByText(credit.message)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Autorizar' })).not.toBeInTheDocument();
  view.unmount();

  permissions.set(['sales:read', 'sales_credit:authorize'], false);
  salesApi.orderAction.mockResolvedValue({ ...pending, status: 'confirmed', version: 6 });
  render(SaleDetail, { id: pending.id });
  await fireEvent.click(await screen.findByRole('button', { name: 'Autorizar' }));
  await fireEvent.input(screen.getByPlaceholderText('Por qué se autoriza el crédito'), {
    target: { value: 'Cliente con garantía' }
  });
  await fireEvent.click(screen.getByRole('button', { name: 'Autorizar crédito y confirmar' }));
  await waitFor(() =>
    expect(salesApi.orderAction).toHaveBeenCalledWith(pending.id, 'authorize', {
      expected_version: 5,
      note: 'Cliente con garantía'
    })
  );
});

it('autoriza el crédito de un pedido confirmado para poder facturarlo', async () => {
  permissions.set(['sales:read', 'sales_credit:authorize'], false);
  const confirmed = order({ status: 'confirmed', version: 7, payment_terms: 'credit' });
  salesApi.sale.mockResolvedValue(confirmed);
  salesApi.orderAction.mockResolvedValue({ ...confirmed, version: 8 });
  render(SaleDetail, { id: confirmed.id });
  await fireEvent.click(
    await screen.findByRole('button', { name: 'Autorizar crédito para facturar' })
  );
  await fireEvent.input(screen.getByPlaceholderText('Por qué se autoriza el crédito'), {
    target: { value: 'Pagará con cheque' }
  });
  await fireEvent.click(screen.getByRole('button', { name: 'Autorizar crédito' }));
  await waitFor(() =>
    expect(salesApi.orderAction).toHaveBeenCalledWith(confirmed.id, 'authorize-credit', {
      expected_version: 7,
      note: 'Pagará con cheque'
    })
  );
});

it('un pedido con entregas ya no ofrece cancelar', async () => {
  salesApi.sale.mockResolvedValue(order({ delivery_progress: 'partial' }));
  render(SaleDetail, { id: 'sale-1' });
  await screen.findByText('Entrega parcial');
  expect(screen.queryByRole('button', { name: 'Cancelar pedido' })).not.toBeInTheDocument();
});

it('al confirmar avisa la entrega automática y lo que queda apartado', async () => {
  const draft = order({ status: 'draft', version: 1, confirmed_at: null, confirmed_by_name: null });
  salesApi.sale.mockResolvedValue(draft);
  salesApi.orderAction.mockResolvedValue({
    ...draft,
    status: 'confirmed',
    version: 2,
    auto_delivery: {
      delivery_id: 'delivery-1',
      delivery_code: 'ENT-0001',
      pending_products: ['Harina fortificada'],
      message: null
    }
  });
  render(SaleDetail, { id: draft.id });
  await fireEvent.click(await screen.findByRole('button', { name: 'Confirmar y apartar' }));
  expect(
    await screen.findByText(/Se entregó con ENT-0001: la salida ya está en el kardex/)
  ).toBeInTheDocument();
  expect(
    screen.getByText(/Queda apartado para «Preparar entrega».*Harina fortificada/)
  ).toBeInTheDocument();
});
