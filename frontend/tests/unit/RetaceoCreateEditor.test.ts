import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import RetaceoCreateEditor from '$lib/features/retaceos/components/RetaceoCreateEditor.svelte';
import type { Purchase } from '$lib/types/purchase';
import { saveRetaceoPreview } from './retaceo-preview';

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

vi.mock('$lib/api/catalog', () => ({
  catalogApi: {
    getProduct: vi.fn().mockResolvedValue({ id_product: 10, sku: 'PROD-10', name: 'Producto A' })
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
  details: [
    {
      id: 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
      purchase_id: '11111111-1111-1111-1111-111111111111',
      purchase_order_detail_id: 'ffffffff-ffff-ffff-ffff-ffffffffffff',
      product_id: 10,
      quantity_ordered: '2',
      quantity_received: '2',
      unit_id: 3,
      unit_price: '50',
      discount: '0',
      subtotal: '100',
      tax_rate: '13',
      tax_amount: '13',
      total: '113',
      notes: null,
      created_at: null,
      updated_at: null
    }
  ],
  subtotal: '100.000000',
  discount: '0.000000',
  tax: '13.000000',
  total: '113.000000',
  status: 'verified',
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

  it('shows the invoice FOB as read-only and has no calculation mode or tax rates', async () => {
    render(RetaceoCreateEditor, { purchaseId: purchase.id });
    expect(await screen.findByText('FOB desde la factura (fijo)')).toBeInTheDocument();
    expect(screen.getByText('FOB por producto (desde la factura)')).toBeInTheDocument();
    expect(screen.getByText('PROD-10 · Producto A')).toBeInTheDocument();
    expect(screen.queryAllByRole('radio')).toHaveLength(0);
    expect(screen.queryByText(/IVA/)).not.toBeInTheDocument();
    expect(screen.queryByText(/porcentaje/i)).not.toBeInTheDocument();
    // Freight and DAI are the only typed amounts; the FOB is never an input.
    expect(screen.getAllByRole('spinbutton').map((input) => input.id)).toEqual([
      'fixed-freight',
      'fixed-dai'
    ]);
    expect(screen.getByRole('spinbutton', { name: 'Flete y seguro (USD)' })).toBeRequired();
    expect(screen.getByRole('spinbutton', { name: 'DAI (USD)' })).toBeRequired();
    expect(screen.getByText('Los registrarás después de crear el retaceo.')).toBeInTheDocument();
  });

  it('adds FOB, freight, DAI and additional expenses into the total cost', async () => {
    render(RetaceoCreateEditor, { purchaseId: purchase.id });
    await screen.findByText('FOB desde la factura (fijo)');
    await fireEvent.input(screen.getByRole('spinbutton', { name: 'Flete y seguro (USD)' }), {
      target: { value: '10' }
    });
    await fireEvent.input(screen.getByRole('spinbutton', { name: 'DAI (USD)' }), {
      target: { value: '11.5' }
    });
    expect(screen.getByText('Costo total').nextElementSibling).toHaveTextContent('121.50');
  });

  it('blocks an empty freight or DAI and explains that zero is allowed', async () => {
    const { container } = render(RetaceoCreateEditor, { purchaseId: purchase.id });
    await screen.findByText('FOB desde la factura (fijo)');
    await fireEvent.input(screen.getByRole('spinbutton', { name: 'DAI (USD)' }), {
      target: { value: '0' }
    });
    await fireEvent.submit(container.querySelector('form')!);
    expect(await screen.findAllByRole('alert')).not.toHaveLength(0);
    expect(
      screen.getByText('Completa el flete y seguro y el DAI; escribe 0 cuando no apliquen.')
    ).toBeInTheDocument();
    const freight = screen.getByRole('spinbutton', { name: 'Flete y seguro (USD)' });
    expect(freight).toBeInvalid();
    expect(freight.getAttribute('aria-describedby')).toContain('fixed-freight-error');
    expect(screen.getByText('Escribe un importe; usa 0 si no aplica.')).toBeInTheDocument();
    expect(mocks.create).not.toHaveBeenCalled();
  });

  it('uses its own validation, not the browser bubbles, when the button is clicked empty', async () => {
    const { container } = render(RetaceoCreateEditor, { purchaseId: purchase.id });
    await screen.findByText('FOB desde la factura (fijo)');
    expect(container.querySelector('form')).toHaveAttribute('novalidate');
    await fireEvent.click(screen.getByRole('button', { name: 'Crear retaceo' }));
    expect(
      await screen.findByText('Completa el flete y seguro y el DAI; escribe 0 cuando no apliquen.')
    ).toBeInTheDocument();
    expect(screen.getAllByText('Escribe un importe; usa 0 si no aplica.')).toHaveLength(2);
    expect(screen.getByRole('spinbutton', { name: 'DAI (USD)' })).toBeRequired();
    expect(mocks.create).not.toHaveBeenCalled();
  });

  it('rejects negative amounts and more than six decimals without calling the API', async () => {
    const { container } = render(RetaceoCreateEditor, { purchaseId: purchase.id });
    await screen.findByText('FOB desde la factura (fijo)');
    await fireEvent.input(screen.getByRole('spinbutton', { name: 'Flete y seguro (USD)' }), {
      target: { value: '-1' }
    });
    await fireEvent.input(screen.getByRole('spinbutton', { name: 'DAI (USD)' }), {
      target: { value: '1.1234567' }
    });
    await fireEvent.submit(container.querySelector('form')!);
    expect(await screen.findByText('El importe no puede ser negativo.')).toBeInTheDocument();
    expect(
      screen.getByText('Escribe un importe válido con hasta 6 decimales.')
    ).toBeInTheDocument();
    expect(mocks.create).not.toHaveBeenCalled();
  });

  it('accepts zero for freight and DAI and sends the exact payload', async () => {
    mocks.create.mockResolvedValue({ id: 'zero-retaceo' });
    const { container } = render(RetaceoCreateEditor, { purchaseId: purchase.id });
    await screen.findByText('FOB desde la factura (fijo)');
    await fillAmounts('0', '0');
    saveRetaceoPreview('retaceo-importes-fijos', container);
    await fireEvent.submit(container.querySelector('form')!);
    await waitFor(() => expect(mocks.create).toHaveBeenCalledTimes(1));
    const payload = mocks.create.mock.calls[0]![0];
    expect(Object.keys(payload).sort()).toEqual([
      'import_data',
      'notes',
      'purchase_id',
      'total_dai',
      'total_expenses',
      'total_freight'
    ]);
    expect(payload).toMatchObject({ total_freight: '0', total_dai: '0', total_expenses: '0' });
  });

  it('creates a retaceo from the selected purchase and redirects to detail', async () => {
    mocks.create.mockResolvedValue({
      id: '99999999-9999-9999-9999-999999999999'
    });

    render(RetaceoCreateEditor, {
      props: { purchaseId: purchase.id }
    });

    expect(await screen.findByText('COM-0001')).toBeInTheDocument();
    expect(screen.getByText('Verificada')).toBeInTheDocument();

    await fireEvent.input(screen.getByLabelText('Notas'), {
      target: { value: 'Importación septiembre' }
    });
    await fillAmounts('12.5', '0');

    await fireEvent.submit(screen.getByRole('button', { name: 'Crear retaceo' }).closest('form')!);

    await waitFor(() => {
      expect(mocks.create).toHaveBeenCalledWith({
        purchase_id: purchase.id,
        import_data: {
          origin_country: null,
          import_invoice_number: 'FAC-001',
          import_invoice_date: '2026-09-20',
          import_policy_number: null,
          import_policy_date: null
        },
        total_freight: '12.5',
        total_dai: '0',
        total_expenses: '0',
        notes: 'Importación septiembre'
      });
    });

    expect(mocks.goto).toHaveBeenCalledWith('/retaceos/99999999-9999-9999-9999-999999999999/edit');
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

    await fillAmounts('0', '0');
    await fireEvent.submit(screen.getByRole('button', { name: 'Crear retaceo' }).closest('form')!);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'La compra no es elegible para retaceo.'
    );
  });
});

async function fillAmounts(freight: string, dai: string) {
  await fireEvent.input(await screen.findByRole('spinbutton', { name: 'Flete y seguro (USD)' }), {
    target: { value: freight }
  });
  await fireEvent.input(screen.getByRole('spinbutton', { name: 'DAI (USD)' }), {
    target: { value: dai }
  });
}
