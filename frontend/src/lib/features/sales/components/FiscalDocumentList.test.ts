import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';
import FiscalDocumentList from './FiscalDocumentList.svelte';

const { salesInvoicesApi } = vi.hoisted(() => ({
  salesInvoicesApi: { list: vi.fn() }
}));
vi.mock('#lib/api/sales-invoices.ts', () => ({ salesInvoicesApi }));

const ITEM = {
  id: 'doc-1',
  company_id: 'company-1',
  branch_id: 'branch-1',
  sale_id: 'sale-1',
  sale_code: 'PED-0001',
  customer_name: 'Clínica San Rafael',
  customer_email: null,
  establishment_code: 'M001',
  point_of_sale_code: 'P001',
  document_type: '03',
  mode: 'simulated',
  status: 'simulated',
  generation_code: null,
  control_number: 'DTE-03-M001P001-000000000000004',
  total: '1250.00',
  seal: null,
  attempts: 1,
  error_code: null,
  error_message: null,
  has_json: true,
  has_pdf: true,
  issued_at: '2026-11-17T10:00:00-06:00',
  created_at: '2026-11-17T10:00:00-06:00',
  updated_at: '2026-11-17T10:00:00-06:00'
};

beforeEach(() => {
  salesInvoicesApi.list.mockReset();
});

it('lista los documentos con su tipo, estado y total en formato local', async () => {
  salesInvoicesApi.list.mockResolvedValue({ items: [ITEM], page: 1, size: 20, total: 1, pages: 1 });
  render(FiscalDocumentList);
  expect(await screen.findByText('DTE-03-M001P001-000000000000004')).toBeInTheDocument();
  expect(screen.getByRole('cell', { name: 'Crédito fiscal' })).toBeInTheDocument();
  expect(screen.getByText('$1,250.00')).toBeInTheDocument();
  expect(screen.getByText('17/11/2026')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'PED-0001' })).toHaveAttribute('href', '/sales/sale-1');
});

it('filtra por estado y muestra el estado vacío', async () => {
  salesInvoicesApi.list.mockResolvedValue({ items: [], page: 1, size: 20, total: 0, pages: 1 });
  render(FiscalDocumentList);
  expect(
    await screen.findByText('No hay documentos fiscales para estos filtros.')
  ).toBeInTheDocument();
  await fireEvent.change(screen.getByLabelText('Estado'), { target: { value: 'failed' } });
  await waitFor(() =>
    expect(salesInvoicesApi.list).toHaveBeenLastCalledWith(
      expect.objectContaining({ status: 'failed' })
    )
  );
});

it('muestra el error del servidor con opción de reintentar', async () => {
  salesInvoicesApi.list.mockRejectedValue(new Error('caído'));
  render(FiscalDocumentList);
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'No se pudieron cargar los documentos fiscales.'
  );
});
