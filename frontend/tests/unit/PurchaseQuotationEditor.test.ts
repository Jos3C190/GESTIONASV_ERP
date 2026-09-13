import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseQuotationEditor from '$lib/features/purchase-quotations/components/PurchaseQuotationEditor.svelte';

const mocks = vi.hoisted(() => ({
  create: vi.fn(),
  listRequests: vi.fn(),
  listSuppliers: vi.fn(),
  currencies: vi.fn(),
  goto: vi.fn(),
  hasPermission: vi.fn()
}));

vi.mock('$app/navigation', () => ({
  goto: mocks.goto
}));

vi.mock('$lib/api/purchase-quotations', () => ({
  purchaseQuotationsApi: {
    create: mocks.create
  }
}));

vi.mock('$lib/api/purchase-requests', () => ({
  purchaseRequestsApi: {
    list: mocks.listRequests
  }
}));

vi.mock('$lib/api/suppliers', () => ({
  suppliersApi: {
    listSuppliers: mocks.listSuppliers,
    currencies: mocks.currencies
  }
}));

vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: {
    hasPermission: mocks.hasPermission
  }
}));

const request = {
  id: '11111111-1111-1111-1111-111111111111',
  company_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  code: 'SC-0001',
  branch_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  warehouse_id: 'cccccccc-cccc-cccc-cccc-cccccccccccc',
  requested_by_id: 'dddddddd-dddd-dddd-dddd-dddddddddddd',
  request_date: '2026-09-13T10:00:00-06:00',
  required_date: null,
  justification: 'Reposición',
  status: 'approved',
  notes: null,
  details: [
    {
      id: '22222222-2222-2222-2222-222222222222',
      purchase_request_id: '11111111-1111-1111-1111-111111111111',
      product_id: 10,
      unit_id: 2,
      quantity: '5.000000',
      description: 'Producto solicitado',
      notes: null,
      created_at: null,
      updated_at: null
    }
  ],
  created_at: null,
  updated_at: null
};

describe('PurchaseQuotationEditor', () => {
  beforeEach(() => {
    mocks.create.mockReset();
    mocks.listRequests.mockReset();
    mocks.listSuppliers.mockReset();
    mocks.currencies.mockReset();
    mocks.goto.mockReset();
    mocks.hasPermission.mockReset();

    mocks.hasPermission.mockImplementation((code: string) => code === 'purchase_quotations:manage');

    mocks.listSuppliers.mockResolvedValue({
      items: [
        {
          id_supplier: 25,
          uuid: 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
          code: 'PRV-025',
          name: 'Proveedor Central',
          country: 1,
          is_active: true,
          supplier_status: 'approved',
          contacts: []
        }
      ],
      meta: { page: 1, size: 100, total: 1, pages: 1 }
    });

    mocks.currencies.mockResolvedValue([
      {
        code: 'USD',
        name: 'Dólar estadounidense',
        symbol: '$',
        decimal_places: 2,
        is_active: true
      }
    ]);

    mocks.listRequests.mockImplementation((params?: { status?: string }) =>
      Promise.resolve({
        items: params?.status === 'approved' ? [request] : [],
        meta: {
          page: 1,
          size: 100,
          total: params?.status === 'approved' ? 1 : 0,
          pages: params?.status === 'approved' ? 1 : 0
        }
      })
    );
  });

  it('creates a draft with selected purchase-request lines', async () => {
    mocks.create.mockResolvedValue({
      id: '33333333-3333-3333-3333-333333333333'
    });

    render(PurchaseQuotationEditor);

    await screen.findByRole('option', {
      name: 'SC-0001 — Aprobada'
    });

    await fireEvent.change(screen.getByLabelText('Solicitud para agregar'), {
      target: { value: request.id }
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Agregar solicitud' }));

    expect(await screen.findByText('Producto #10')).toBeInTheDocument();

    await fireEvent.submit(screen.getByRole('button', { name: 'Crear borrador' }).closest('form')!);

    await waitFor(() => {
      expect(mocks.create).toHaveBeenCalledWith({
        supplier_id: 25,
        currency: 'USD',
        requests: [
          {
            purchase_request_id: request.id,
            lines: [
              {
                purchase_request_detail_id: '22222222-2222-2222-2222-222222222222',
                quantity: 5
              }
            ]
          }
        ],
        notes: null
      });
    });

    expect(mocks.goto).toHaveBeenCalledWith(
      '/purchase-quotations/33333333-3333-3333-3333-333333333333'
    );
  });

  it('requires at least one linked request', async () => {
    render(PurchaseQuotationEditor);

    await screen.findByRole('option', {
      name: 'SC-0001 — Aprobada'
    });

    await fireEvent.submit(screen.getByRole('button', { name: 'Crear borrador' }).closest('form')!);

    expect(await screen.findByText('Agrega al menos una solicitud de compra.')).toBeInTheDocument();
    expect(mocks.create).not.toHaveBeenCalled();
  });

  it('blocks direct access without manage permission', async () => {
    mocks.hasPermission.mockReturnValue(false);

    render(PurchaseQuotationEditor);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No tienes permiso para gestionar cotizaciones de compra.'
    );
    expect(mocks.listSuppliers).not.toHaveBeenCalled();
    expect(mocks.listRequests).not.toHaveBeenCalled();
  });
});
