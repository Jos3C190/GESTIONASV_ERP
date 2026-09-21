import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import RetaceoCreateEditor from '$lib/features/retaceos/components/RetaceoCreateEditor.svelte';
import type { Purchase } from '$lib/types/purchase';

const mocks = vi.hoisted(() => ({
  goto: vi.fn(),
  getPurchase: vi.fn(),
  create: vi.fn(),
  hasPermission: vi.fn()
}));

vi.mock('$app/navigation', () => ({
  goto: mocks.goto
}));

vi.mock('$lib/api/purchases', () => ({
  purchasesApi: {
    get: mocks.getPurchase
  }
}));

vi.mock('$lib/api/retaceos', () => ({
  retaceosApi: {
    create: mocks.create
  }
}));

vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: {
    hasPermission: mocks.hasPermission
  }
}));

const purchase: Purchase = {
  id: '11111111-1111-1111-1111-111111111111',
  company_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  code: 'COM-0001',
  purchase_order_id: '22222222-2222-2222-2222-222222222222',
  supplier_id: 25,
  branch_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  warehouse_id: 'cccccccc-cccc-cccc-cccc-cccccccccccc',
  created_by_id: 'dddddddd-dddd-dddd-dddd-dddddddddddd',
  purchase_date: '2026-09-20T12:00:00-06:00',
  supplier_invoice_number: 'FAC-001',
  supplier_invoice_date: '2026-09-20',
  currency: 'USD',
  details: [],
  subtotal: '100.000000',
  discount: '0.000000',
  tax: '13.000000',
  total: '113.000000',
  status: 'received',
  notes: null,
  created_at: null,
  updated_at: null
};

describe('RetaceoCreateEditor', () => {
  beforeEach(() => {
    mocks.goto.mockReset();
    mocks.getPurchase.mockReset();
    mocks.create.mockReset();
    mocks.hasPermission.mockReset();

    mocks.hasPermission.mockImplementation((code: string) => code === 'retaceos:manage');
    mocks.getPurchase.mockResolvedValue(purchase);
  });

  it('creates a retaceo from the selected purchase and redirects to detail', async () => {
    mocks.create.mockResolvedValue({
      id: '99999999-9999-9999-9999-999999999999'
    });

    render(RetaceoCreateEditor, {
      props: { purchaseId: purchase.id }
    });

    expect(await screen.findByText('COM-0001')).toBeInTheDocument();
    expect(screen.getByText('Recibida')).toBeInTheDocument();

    await fireEvent.input(screen.getByLabelText('Flete'), {
      target: { value: '10.000000' }
    });

    await fireEvent.input(screen.getByLabelText('Gastos'), {
      target: { value: '5.000000' }
    });

    await fireEvent.input(screen.getByLabelText('DAI'), {
      target: { value: '3.000000' }
    });

    await fireEvent.input(screen.getByLabelText('IVA de importación'), {
      target: { value: '2.340000' }
    });

    await fireEvent.input(screen.getByLabelText('Notas'), {
      target: { value: 'Importación septiembre' }
    });

    await fireEvent.submit(screen.getByRole('button', { name: 'Crear retaceo' }).closest('form')!);

    await waitFor(() => {
      expect(mocks.create).toHaveBeenCalledWith({
        purchase_id: purchase.id,
        total_freight: '10.000000',
        total_expenses: '5.000000',
        total_dai: '3.000000',
        import_vat: '2.340000',
        notes: 'Importación septiembre'
      });
    });

    expect(mocks.goto).toHaveBeenCalledWith('/retaceos/99999999-9999-9999-9999-999999999999');
  });

  it('does not load purchase data without retaceos:manage', async () => {
    mocks.hasPermission.mockReturnValue(false);

    render(RetaceoCreateEditor, {
      props: { purchaseId: purchase.id }
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No tienes permiso para gestionar retaceos.'
    );

    expect(mocks.getPurchase).not.toHaveBeenCalled();
  });

  it('shows backend creation errors', async () => {
    mocks.create.mockRejectedValue(new Error('La compra no es elegible para retaceo.'));

    render(RetaceoCreateEditor, {
      props: { purchaseId: purchase.id }
    });

    expect(await screen.findByText('COM-0001')).toBeInTheDocument();

    await fireEvent.click(screen.getByRole('button', { name: 'Crear retaceo' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'La compra no es elegible para retaceo.'
    );
  });
});
