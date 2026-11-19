import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { permissions } from '#lib/stores/permissions.svelte.ts';
import { order } from '#lib/features/sales/test-fixtures.ts';
import type { FiscalDocument, InvoiceOptions } from '#lib/types/sales-invoices.ts';
import SalesInvoicePanel from './SalesInvoicePanel.svelte';

const { salesInvoicesApi } = vi.hoisted(() => ({
  salesInvoicesApi: {
    options: vi.fn(),
    invoice: vi.fn(),
    get: vi.fn(),
    retry: vi.fn(),
    json: vi.fn(),
    pdfUrl: vi.fn(),
    emails: vi.fn(),
    sendEmail: vi.fn()
  }
}));
vi.mock('#lib/api/sales-invoices.ts', () => ({ salesInvoicesApi }));

function fiscal(values: Partial<FiscalDocument> = {}): FiscalDocument {
  return {
    id: 'doc-1',
    company_id: 'company-1',
    branch_id: 'branch-1',
    sale_id: 'sale-1',
    sale_code: 'PED-0001',
    customer_name: 'Clínica San Rafael',
    customer_email: null,
    establishment_code: 'M001',
    point_of_sale_code: 'P001',
    document_type: '01',
    mode: 'simulated',
    status: 'simulated',
    generation_code: 'a1b2c3d4-0000-4000-8000-000000000001',
    control_number: 'DTE-01-M001P001-000000000000001',
    total: '22.60',
    seal: null,
    attempts: 1,
    error_code: null,
    error_message: null,
    has_json: true,
    has_pdf: true,
    issued_at: '2026-11-17T10:00:00-06:00',
    created_at: '2026-11-17T10:00:00-06:00',
    updated_at: '2026-11-17T10:00:00-06:00',
    ...values
  };
}

function options(values: Partial<InvoiceOptions> = {}): InvoiceOptions {
  return {
    document_type: '01',
    mode: 'simulated',
    establishment_code: 'M001',
    points_of_sale: [
      { id: 'pos-1', code: 'P001', name: 'Caja 1' },
      { id: 'pos-2', code: 'P002', name: 'Caja 2' }
    ],
    blockers: [],
    renta_operation_type: 1,
    renta_income_type: 3,
    document: null,
    ...values
  };
}

beforeEach(() => {
  permissions.set(['sales_invoices:read', 'sales_invoices:issue'], false);
  for (const fn of Object.values(salesInvoicesApi)) fn.mockReset();
  salesInvoicesApi.emails.mockResolvedValue({ enabled: true, customer_email: null, items: [] });
});
afterEach(() => vi.useRealTimers());

it('pide la caja cuando hay varias y factura con la elegida', async () => {
  const sale = order({ status: 'confirmed' });
  const onInvoiced = vi.fn();
  salesInvoicesApi.options.mockResolvedValue(options());
  salesInvoicesApi.invoice.mockResolvedValue(fiscal());
  render(SalesInvoicePanel, { sale, onInvoiced });
  const button = await screen.findByRole('button', { name: 'Facturar' });
  expect(button).toBeDisabled();
  await fireEvent.change(screen.getByLabelText('Punto de venta'), { target: { value: 'pos-2' } });
  expect(button).toBeEnabled();
  await fireEvent.click(button);
  expect(salesInvoicesApi.invoice).toHaveBeenCalledExactlyOnceWith(sale.id, 'pos-2', {
    operation: 1,
    income: 3
  });
  expect(await screen.findByText('DTE-01-M001P001-000000000000001')).toBeInTheDocument();
  expect(screen.getByText('Simulado')).toBeInTheDocument();
  expect(onInvoiced).toHaveBeenLastCalledWith(expect.objectContaining({ status: 'simulated' }));
});

it('muestra lo que falta para facturar y no deja intentarlo', async () => {
  salesInvoicesApi.options.mockResolvedValue(
    options({ blockers: ['Falta configurar el emisor antes de facturar: el NRC.'] })
  );
  render(SalesInvoicePanel, { sale: order({ status: 'confirmed' }) });
  expect(await screen.findByText(/Falta configurar el emisor/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Facturar' })).toBeDisabled();
});

it('sigue el documento mientras se emite y luego ofrece las descargas', async () => {
  salesInvoicesApi.options.mockResolvedValue(
    options({
      document: fiscal({ status: 'pending', control_number: null, has_json: false, has_pdf: false })
    })
  );
  salesInvoicesApi.get.mockResolvedValue(fiscal());
  salesInvoicesApi.pdfUrl.mockResolvedValue({ url: 'https://storage/dte.pdf' });
  const open = vi.spyOn(window, 'open').mockReturnValue(null);
  render(SalesInvoicePanel, { sale: order({ status: 'confirmed' }), pollMs: 10 });
  expect(await screen.findByText(/se está emitiendo/)).toBeInTheDocument();
  await waitFor(() => expect(salesInvoicesApi.get).toHaveBeenCalledWith('doc-1'));
  await fireEvent.click(await screen.findByRole('button', { name: 'Ver PDF' }));
  await waitFor(() =>
    expect(open).toHaveBeenCalledWith('https://storage/dte.pdf', '_blank', 'noopener')
  );
  open.mockRestore();
});

it('un fallo se puede reintentar con los mismos datos', async () => {
  const sale = order({ status: 'confirmed' });
  salesInvoicesApi.options.mockResolvedValue(
    options({ points_of_sale: [{ id: 'pos-1', code: 'P001', name: 'Caja 1' }] })
  );
  salesInvoicesApi.invoice.mockResolvedValue(
    fiscal({ status: 'failed', error_message: 'El tipo de DTE 01 no está habilitado' })
  );
  salesInvoicesApi.retry.mockResolvedValue(fiscal({ status: 'pending', control_number: null }));
  salesInvoicesApi.get.mockResolvedValue(fiscal());
  render(SalesInvoicePanel, { sale, pollMs: 10 });
  await fireEvent.click(await screen.findByRole('button', { name: 'Facturar' }));
  expect(salesInvoicesApi.invoice).toHaveBeenCalledWith(sale.id, 'pos-1', {
    operation: 1,
    income: 3
  });
  expect(await screen.findByText(/no está habilitado/)).toBeInTheDocument();
  await fireEvent.click(screen.getByRole('button', { name: 'Reintentar con los mismos datos' }));
  expect(salesInvoicesApi.retry).toHaveBeenCalledWith('doc-1');
  expect(await screen.findByText('Simulado')).toBeInTheDocument();
});

it('quien solo consulta no ve el botón de facturar', async () => {
  permissions.set(['sales_invoices:read'], false);
  salesInvoicesApi.options.mockResolvedValue(options());
  render(SalesInvoicePanel, { sale: order({ status: 'confirmed' }) });
  expect(await screen.findByText(/Emite la factura del pedido completo/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Facturar' })).not.toBeInTheDocument();
});

it('muestra el error del servidor al consultar', async () => {
  salesInvoicesApi.options.mockRejectedValue(new Error('caído'));
  render(SalesInvoicePanel, { sale: order({ status: 'confirmed' }) });
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'No se pudo consultar la facturación.'
  );
});

it('propone la clasificación de renta de la actividad y no factura sin ella', async () => {
  const sale = order({ status: 'confirmed' });
  salesInvoicesApi.options.mockResolvedValue(
    options({
      points_of_sale: [{ id: 'pos-1', code: 'P001', name: 'Caja 1' }],
      renta_operation_type: null,
      renta_income_type: null
    })
  );
  salesInvoicesApi.invoice.mockResolvedValue(fiscal());
  render(SalesInvoicePanel, { sale });
  const button = await screen.findByRole('button', { name: 'Facturar' });
  expect(button).toBeDisabled();
  await fireEvent.change(screen.getByLabelText('Tipo de operación (renta)'), {
    target: { value: '4' }
  });
  await fireEvent.change(screen.getByLabelText('Tipo de ingreso (renta)'), {
    target: { value: '2' }
  });
  expect(button).toBeEnabled();
  await fireEvent.click(button);
  expect(salesInvoicesApi.invoice).toHaveBeenCalledExactlyOnceWith(sale.id, 'pos-1', {
    operation: 4,
    income: 2
  });
});
