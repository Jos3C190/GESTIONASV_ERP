import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';

const { fiscalBooksApi } = vi.hoisted(() => ({
  fiscalBooksApi: {
    month: vi.fn(),
    workbook: vi.fn(),
    bookPdf: vi.fn(),
    f07Zip: vi.fn(),
    purchase: vi.fn(),
    recordPurchase: vi.fn(),
    settings: vi.fn(),
    saveSettings: vi.fn()
  }
}));
vi.mock('#lib/api/fiscal-books.ts', () => ({ fiscalBooksApi }));

import type { FiscalMonth } from '#lib/types/fiscal-books.ts';
import FiscalBooksPage from './FiscalBooksPage.svelte';
import { previousPeriod } from './labels.ts';

function month(overrides: Partial<FiscalMonth> = {}): FiscalMonth {
  return {
    period: '2026-11',
    label: 'noviembre de 2026',
    mode: 'simulated',
    modes: ['simulated'],
    issuer: { name: 'Grupo Lorena, S.A. de C.V.', nit: '1217-060102-101-1', nrc: '1234567' },
    warnings: ['1 compra(s) recibidas en el mes no tienen registrado el documento del proveedor.'],
    summary: {
      contributor_taxed: '100.00',
      contributor_vat: '13.00',
      consumer_taxed_with_vat: '11.30',
      consumer_vat: '1.30',
      exempt_sales: '0.00',
      not_subject_sales: '0.00',
      debit: '14.30',
      purchase_taxed: '50.00',
      credit: '6.50',
      perception_collected: '0.00',
      balance: '7.80'
    },
    contributor_book: [
      {
        number: 1,
        issued_on: '2026-11-05',
        document_type: '03',
        generation_code: 'ABC',
        control_number: 'DTE-03-M001P001-000000000000001',
        customer: 'Cafetería El Trigal, S.A. de C.V.',
        registry: '12345',
        exempt: '0.00',
        not_subject: '0.00',
        taxed: '100.00',
        vat: '13.00',
        perception: '0.00',
        total: '113.00'
      }
    ],
    consumer_book: [
      {
        day: '2026-10-28',
        first_control: 'DTE-01-M001P001-000000000000004',
        last_control: 'DTE-01-M001P001-000000000000004',
        point_of_sale: 'M001P001',
        exempt: '0.00',
        not_subject: '0.00',
        taxed: '-5.00',
        exports: '0.00',
        total: '-5.00',
        third_parties: '0.00',
        note: 'Invalidada el 03/11/2026'
      }
    ],
    purchase_book: [],
    annexes: [
      {
        key: 'anexo1',
        title: 'Detalle de Ventas a Contribuyentes',
        file_name: 'F07_anexo1_2026-11_SIMULADO.csv',
        rows: [['05/11/2026', '4', '03']]
      },
      {
        key: 'anexo3',
        title: 'Detalle de Compras',
        file_name: 'F07_anexo3_2026-11_SIMULADO.csv',
        rows: []
      }
    ],
    pending_purchases: [
      {
        id: 'p-1',
        code: 'COM-00001',
        supplier: 'Harinas de El Salvador',
        invoice_number: 'F-100',
        invoice_date: '2026-11-08',
        total: '2090.50'
      }
    ],
    ...overrides
  };
}

beforeEach(() => {
  for (const fn of Object.values(fiscalBooksApi)) fn.mockReset();
  fiscalBooksApi.settings.mockResolvedValue({
    operation: 1,
    classification: 1,
    sector: 2,
    cost_type: 5
  });
});

it('muestra el resumen, el aviso de simulado y los libros por pestaña', async () => {
  fiscalBooksApi.month.mockResolvedValue(month());
  render(FiscalBooksPage, { canManage: false });

  expect(await screen.findByText('$14.30')).toBeInTheDocument();
  expect(fiscalBooksApi.month).toHaveBeenCalledWith(previousPeriod(), null);
  expect(screen.getByText(/sin validez fiscal/)).toBeInTheDocument();
  expect(screen.getByText('Cafetería El Trigal, S.A. de C.V.')).toBeInTheDocument();

  await fireEvent.click(screen.getByRole('tab', { name: /Consumidor final/ }));
  expect(screen.getByText('Invalidada el 03/11/2026')).toBeInTheDocument();
  expect(screen.getAllByText('-$5.00').length).toBeGreaterThan(0);

  await fireEvent.click(screen.getByRole('tab', { name: /Anexos F-07/ }));
  expect(screen.getByText(/F07_anexo1_2026-11_SIMULADO.csv/)).toBeInTheDocument();

  await fireEvent.click(screen.getByRole('tab', { name: /Compras pendientes/ }));
  expect(screen.getByRole('link', { name: 'COM-00001' })).toHaveAttribute('href', '/purchases/p-1');
  expect(screen.queryByRole('button', { name: 'Registrar documento' })).not.toBeInTheDocument();
});

it('descarga el PDF con el folio inicial y avisa si falla', async () => {
  fiscalBooksApi.month.mockResolvedValue(month());
  fiscalBooksApi.bookPdf.mockRejectedValue(new Error('boom'));
  render(FiscalBooksPage, { canManage: true });

  await screen.findByText('$14.30');
  await fireEvent.input(screen.getByLabelText('Folio inicial'), { target: { value: '41' } });
  await fireEvent.click(screen.getByRole('button', { name: 'PDF compras' }));
  expect(fiscalBooksApi.bookPdf).toHaveBeenCalledWith('2026-11', 'purchases', 41, 'simulated');
  expect(await screen.findByText('No se pudo generar el archivo.')).toBeInTheDocument();
});

it('muestra el error de carga', async () => {
  fiscalBooksApi.month.mockRejectedValue(new Error('down'));
  render(FiscalBooksPage, { canManage: true });
  expect(await screen.findByText('No se pudieron cargar los libros.')).toBeInTheDocument();
});
