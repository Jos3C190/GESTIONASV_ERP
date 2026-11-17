import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';
import { permissions } from '#lib/stores/permissions.svelte.ts';
import SalesQuotationEditor from './SalesQuotationEditor.svelte';
import {
  formatDay,
  formatMoney,
  formatQuantity,
  statusLabel
} from '#lib/features/sales/quotation-labels.ts';

const { salesApi, customersApi } = vi.hoisted(() => ({
  salesApi: {
    catalog: vi.fn(),
    quotationSettings: vi.fn(),
    previewQuotation: vi.fn(),
    createQuotation: vi.fn(),
    quotation: vi.fn()
  },
  customersApi: { list: vi.fn() }
}));
vi.mock('#lib/api/sales.ts', () => ({ salesApi }));
vi.mock('#lib/api/customers.ts', () => ({ customersApi }));
vi.mock('#lib/stores/branch.svelte.ts', () => ({
  branch: {
    id: 'branch-1',
    branches: [{ id: 'branch-1', name: 'Centro', code: 'C', is_active: true }]
  }
}));

const CUSTOMER = {
  id: 'customer-1',
  code: 'CLI-001',
  name: 'Clínica San Rafael',
  receivable_documents: ['01'],
  price_list_name: 'Mostrador'
};
const ITEM = {
  product_id: 7,
  variant_id: null,
  inventory_item_id: 'item-7',
  sku: 'PRD-007',
  name: 'Harina fortificada',
  base_unit_id: 1,
  base_unit_name: 'Unidad',
  units: [
    {
      unit_id: 1,
      name: 'Unidad',
      factor: '1',
      packaging_definition_id: null,
      packaging_version: null
    }
  ]
};

beforeEach(() => {
  permissions.set(['sales_quotations:manage'], false);
  customersApi.list.mockReset().mockResolvedValue({ items: [CUSTOMER] });
  salesApi.catalog.mockReset().mockResolvedValue([ITEM]);
  salesApi.quotationSettings.mockReset().mockResolvedValue({ quotation_validity_days: 15 });
  salesApi.previewQuotation.mockReset().mockResolvedValue({
    document_type: '01',
    costs_visible: false,
    requires_authorization: true,
    authorization_reasons: [
      { code: 'discount_above_limit', message: 'El descuento supera el tope de tu rol.' }
    ],
    total_taxed: '22.60',
    total_exempt: '0.00',
    total_not_subject: '0.00',
    total_discount: '0.00',
    vat: '2.60',
    vat_perceived: '0.00',
    vat_withheld: '0.00',
    total: '22.60',
    total_in_words: 'VEINTIDÓS 60/100 DÓLARES',
    lines: [
      {
        list_price: '10.00000000',
        unit_price: '10.00000000',
        price_overridden: false,
        discount_percent: '0.00',
        suggested_discount_percent: '0.00',
        suggested_discount_source: 'none',
        margin_percent: null,
        line_total: '22.60000000',
        authorization_reasons: []
      }
    ]
  });
});

async function fillDraft() {
  render(SalesQuotationEditor, {});
  const [customer, , , product] = await screen.findAllByRole('combobox');
  await fireEvent.change(customer!, { target: { value: 'customer-1' } });
  await fireEvent.change(product!, { target: { value: '7:' } });
}

it('calcula en el servidor y muestra el total y el aviso de autorización', async () => {
  await fillDraft();
  await waitFor(() => expect(salesApi.previewQuotation).toHaveBeenCalled(), { timeout: 2000 });
  const body = salesApi.previewQuotation.mock.calls.at(-1)![0];
  expect(body).toMatchObject({
    branch_id: 'branch-1',
    customer_id: 'customer-1',
    document_type: null,
    lines: [
      { product_id: 7, unit_id: 1, quantity: '1', discount_percent: null, manual_price: null }
    ]
  });
  expect(await screen.findAllByText('$22.60')).toHaveLength(3);
  expect(screen.getByText(/Por autorizar/)).toBeInTheDocument();
  expect(screen.getByText('Vacío: 15 días desde hoy.')).toBeInTheDocument();
});

it('el precio manual solo aparece con permiso para cambiar precios', async () => {
  await fillDraft();
  expect(screen.queryByText('Precio manual')).not.toBeInTheDocument();
  permissions.set(['sales_quotations:manage', 'sales_prices:override'], false);
  render(SalesQuotationEditor, {});
  expect(await screen.findByText('Precio manual')).toBeInTheDocument();
});

it('formatea montos, fechas, cantidades y estados en es-SV', () => {
  expect(formatMoney('1250')).toBe('$1,250.00');
  expect(formatDay('2026-11-16')).toBe('16/11/2026');
  expect(formatQuantity('2.000000')).toBe('2');
  expect(statusLabel({ status: 'issued', expired: true })).toBe('Vencida');
  expect(statusLabel({ status: 'pending_authorization', expired: false })).toBe('Por autorizar');
});
