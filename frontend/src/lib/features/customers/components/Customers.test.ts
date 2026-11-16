import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { customersApi, fiscalApi, geography, gotoMock } = vi.hoisted(() => ({
  customersApi: {
    list: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    setActive: vi.fn()
  },
  fiscalApi: { catalog: vi.fn() },
  geography: { departments: vi.fn(), municipalities: vi.fn(), districts: vi.fn() },
  gotoMock: vi.fn()
}));

vi.mock('$lib/api/customers', () => ({ customersApi }));
vi.mock('$lib/api/fiscal', () => ({ fiscalApi }));
vi.mock('$app/navigation', () => ({ goto: gotoMock }));
vi.mock('$lib/api/client', () => ({
  api: { geography },
  HttpError: class HttpError extends Error {
    constructor(
      readonly code: string,
      message: string,
      readonly status: number
    ) {
      super(message);
    }
  }
}));

import { permissions } from '$lib/stores/permissions.svelte';
import type { Customer } from '$lib/types/customer';
import CustomerForm from './CustomerForm.svelte';
import CustomerList from './CustomerList.svelte';

const taxpayer: Customer = {
  id: 'customer-1',
  company_id: 'company-1',
  code: 'CLI-00001',
  customer_type: 'taxpayer',
  name: 'Cafetería ficticia, S.A. de C.V.',
  person_type: '2',
  taxpayer_category: 'other',
  is_withholding_agent: false,
  commercial_name: null,
  document_type: '36',
  document_number: '06140101011011',
  nrc: null,
  activity_code: null,
  activity_name: null,
  address: {
    department_id: null,
    municipality_id: null,
    district_id: null,
    department: null,
    department_code: null,
    municipality: null,
    municipality_code: null,
    district: null,
    district_code: null
  },
  address_line: null,
  country_code: null,
  country_name: null,
  phone: null,
  email: null,
  credit_days: 0,
  credit_limit: null,
  seller_employee_id: null,
  seller_name: null,
  is_active: true,
  is_generic: false,
  branch_id: null,
  receivable_documents: ['01'],
  tax_credit_missing: ['NRC.', 'Actividad económica.'],
  delivery_addresses: [],
  created_at: '2026-11-15T12:00:00Z',
  updated_at: '2026-11-15T12:00:00Z'
};

function grant(...codes: string[]) {
  vi.spyOn(permissions, 'hasPermission').mockImplementation((code: string) => codes.includes(code));
}

describe('customers', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    for (const group of [customersApi, fiscalApi, geography]) {
      for (const fn of Object.values(group)) fn.mockReset();
    }
    geography.departments.mockResolvedValue([]);
    grant('sales_customers:read', 'sales_customers:manage');
  });

  it('lists customers with the documents they can receive', async () => {
    customersApi.list.mockResolvedValue({
      items: [taxpayer],
      meta: { page: 1, size: 20, total: 1, pages: 1 }
    });
    render(CustomerList);
    expect(await screen.findAllByText('Cafetería ficticia, S.A. de C.V.')).not.toHaveLength(0);
    expect(screen.getAllByText('Factura').length).toBeGreaterThan(0);
    expect(screen.getAllByText('0614-010101-101-1').length).toBeGreaterThan(0);
  });

  it('shows the empty state with a call to action', async () => {
    customersApi.list.mockResolvedValue({
      items: [],
      meta: { page: 1, size: 20, total: 0, pages: 0 }
    });
    render(CustomerList);
    expect(await screen.findByText('Aún no hay clientes')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Registrar el primero' })).toBeInTheDocument();
  });

  it('explains what a taxpayer is missing for tax credit', async () => {
    customersApi.get.mockResolvedValue(taxpayer);
    render(CustomerForm, { customerId: 'customer-1' });
    expect(await screen.findByText('Para emitirle crédito fiscal falta:')).toBeInTheDocument();
    expect(screen.getByText('NRC.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Guardar cambios' })).toBeInTheDocument();
  });

  it('creates a final consumer and opens its file', async () => {
    customersApi.create.mockResolvedValue({ ...taxpayer, id: 'new-1' });
    render(CustomerForm);
    await fireEvent.input(screen.getByLabelText('Nombre o razón social'), {
      target: { value: 'Ana López' }
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Registrar cliente' }));
    expect(customersApi.create).toHaveBeenCalledWith(
      expect.objectContaining({ customer_type: 'final_consumer', name: 'Ana López', code: null })
    );
    expect(gotoMock).toHaveBeenCalledWith('/customers/new-1', { replaceState: true });
  });

  it('is read only without the manage permission', async () => {
    grant('sales_customers:read');
    customersApi.get.mockResolvedValue(taxpayer);
    render(CustomerForm, { customerId: 'customer-1' });
    await screen.findByText('Para emitirle crédito fiscal falta:');
    expect(screen.queryByRole('button', { name: 'Guardar cambios' })).not.toBeInTheDocument();
    expect(screen.getByLabelText('Nombre o razón social')).toBeDisabled();
  });
});
