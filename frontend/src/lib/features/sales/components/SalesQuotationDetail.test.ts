import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';
import { permissions } from '#lib/stores/permissions.svelte.ts';
import type { SalesQuotation, SalesQuotationLine } from '#lib/types/sales.ts';
import SalesQuotationDetail from './SalesQuotationDetail.svelte';

const { salesApi } = vi.hoisted(() => ({
  salesApi: {
    quotation: vi.fn(),
    quotationAction: vi.fn(),
    convertQuotation: vi.fn(),
    quotationPdfPath: (id: string) => `/sales/quotations/${id}/pdf`
  }
}));
vi.mock('#lib/api/sales.ts', () => ({ salesApi }));

function line(overrides: Partial<SalesQuotationLine> = {}): SalesQuotationLine {
  return {
    id: 'line-1',
    line_number: 1,
    product_id: 1,
    variant_id: null,
    inventory_item_id: 'item-1',
    product_sku: 'PRD-001',
    product_name: 'Harina fortificada',
    unit_id: 1,
    unit_name: 'Unidad',
    base_unit_id: 1,
    base_unit_name: 'Unidad',
    unit_factor: '1',
    quantity: '2.000000',
    quantity_base: '2.000000',
    price_list_id: 'list-1',
    list_price: '10.00000000',
    price_overridden: false,
    unit_price: '10.00000000',
    discount_percent: '10.00',
    suggested_discount_percent: '0.00',
    suggested_discount_source: 'none',
    tax_treatment: 'taxed',
    item_type: '1',
    document_unit_price: '11.30000000',
    discount_amount: '2.26000000',
    not_subject: '0',
    exempt: '0',
    taxed: '20.34000000',
    vat_item: '2.34000000',
    line_total: '20.34000000',
    cost: null,
    margin_percent: null,
    authorization_reasons: [],
    ...overrides
  };
}

function quote(overrides: Partial<SalesQuotation> = {}): SalesQuotation {
  return {
    id: 'quote-ui',
    company_id: 'company-1',
    branch_id: 'branch-1',
    customer_id: 'customer-1',
    customer_code: 'CLI-001',
    customer_name: 'Clínica San Rafael',
    code: 'COT-UI',
    quotation_date: '2026-11-16',
    valid_until: '2026-12-01',
    document_type: '01',
    price_list_id: 'list-1',
    price_list_name: 'Mostrador',
    prices_include_vat: false,
    global_discount_percent: '0.00',
    status: 'draft',
    expired: false,
    version: 1,
    notes: null,
    total_not_subject: '0.00',
    total_exempt: '0.00',
    total_taxed: '20.34',
    subtotal_sales: '20.34',
    total_discount: '2.26',
    subtotal: '20.34',
    vat: '2.34',
    vat_perceived: '0.00',
    vat_withheld: '0.00',
    total: '20.34',
    total_in_words: 'VEINTE 34/100 DÓLARES',
    requires_authorization: false,
    authorization_reasons: [],
    costs_visible: false,
    created_by_id: 'user-1',
    created_by_name: 'Ana López',
    issued_by_name: null,
    issued_at: null,
    authorized_by_name: null,
    authorized_at: null,
    authorization_note: null,
    customer_response_by_name: null,
    customer_response_at: null,
    rejection_reason: null,
    cancelled_by_name: null,
    cancelled_at: null,
    cancellation_reason: null,
    sale_id: null,
    sale_code: null,
    lines: [line()],
    created_at: null,
    updated_at: null,
    ...overrides
  };
}

const REASON = {
  code: 'discount_above_limit' as const,
  message: 'El descuento supera el tope de tu rol.'
};

beforeEach(() => {
  permissions.set(['sales_quotations:confirm', 'sales_quotations:manage'], false);
  salesApi.quotation.mockReset();
  salesApi.quotationAction.mockReset();
});

it('emite un borrador una sola vez con la versión vigente y muestra el total con formato', async () => {
  salesApi.quotation.mockResolvedValue(quote());
  salesApi.quotationAction.mockResolvedValue(quote({ status: 'issued', version: 2 }));
  render(SalesQuotationDetail, { id: 'quote-ui' });
  expect(await screen.findAllByText('$20.34')).not.toHaveLength(0);
  await fireEvent.click(screen.getByRole('button', { name: 'Emitir cotización' }));
  expect(salesApi.quotationAction).toHaveBeenCalledExactlyOnceWith('quote-ui', 'issue', {
    expected_version: 1
  });
  expect(await screen.findByText('Emitida')).toBeInTheDocument();
});

it('un borrador que pasa el tope se envía a autorización', async () => {
  salesApi.quotation.mockResolvedValue(
    quote({ requires_authorization: true, authorization_reasons: [REASON] })
  );
  render(SalesQuotationDetail, { id: 'quote-ui' });
  expect(await screen.findByRole('button', { name: 'Enviar a autorización' })).toBeInTheDocument();
});

it('quien autoriza ve costo y margen, y devolver exige qué corregir', async () => {
  permissions.set(['sales_quotations:read', 'sales_discounts:authorize'], false);
  salesApi.quotation.mockResolvedValue(
    quote({
      status: 'pending_authorization',
      authorization_reasons: [REASON],
      costs_visible: true,
      lines: [
        line({ cost: '7.00000000', margin_percent: '22.22', authorization_reasons: [REASON] })
      ]
    })
  );
  salesApi.quotationAction.mockResolvedValue(quote({ authorization_note: 'Baja el descuento' }));
  render(SalesQuotationDetail, { id: 'quote-ui' });
  expect(await screen.findByText('Espera autorización')).toBeInTheDocument();
  expect(screen.getByText('Costo / margen')).toBeInTheDocument();
  expect(screen.getByText(/22\.22 %/)).toBeInTheDocument();

  await fireEvent.click(screen.getByRole('button', { name: 'Devolver a borrador' }));
  const submit = screen.getAllByRole('button', { name: 'Devolver a borrador' }).at(-1)!;
  expect(submit).toBeDisabled();
  await fireEvent.input(screen.getByPlaceholderText('Qué debe corregirse'), {
    target: { value: 'Baja el descuento' }
  });
  expect(submit).toBeEnabled();
  await fireEvent.click(submit);
  await waitFor(() =>
    expect(salesApi.quotationAction).toHaveBeenCalledWith('quote-ui', 'return', {
      expected_version: 1,
      reason: 'Baja el descuento'
    })
  );
});

it('sin permiso de costos no muestra la columna de costo', async () => {
  salesApi.quotation.mockResolvedValue(quote());
  render(SalesQuotationDetail, { id: 'quote-ui' });
  await screen.findByText('Harina fortificada');
  expect(screen.queryByText('Costo / margen')).not.toBeInTheDocument();
});

it('una emitida vencida no se puede aceptar, pero sí rechazar', async () => {
  salesApi.quotation.mockResolvedValue(quote({ status: 'issued', expired: true }));
  render(SalesQuotationDetail, { id: 'quote-ui' });
  expect(await screen.findByText('Vencida')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'El cliente aceptó' })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'El cliente rechazó' })).toBeInTheDocument();
});

it('muestra el error del servidor en un banner', async () => {
  salesApi.quotation.mockResolvedValue(quote());
  salesApi.quotationAction.mockRejectedValue(new Error('x'));
  render(SalesQuotationDetail, { id: 'quote-ui' });
  await fireEvent.click(await screen.findByRole('button', { name: 'Emitir cotización' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo completar la acción');
});
