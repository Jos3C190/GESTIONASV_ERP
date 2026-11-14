import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import RetaceoCreateEditor from '$lib/features/retaceos/components/RetaceoCreateEditor.svelte';
import { saveRetaceoPreview } from './retaceo-preview';

const mocks = vi.hoisted(() => ({ getPurchase: vi.fn(), create: vi.fn(), goto: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto: mocks.goto }));
vi.mock('$lib/api/purchases', () => ({ purchasesApi: { get: mocks.getPurchase } }));
vi.mock('$lib/api/retaceos', () => ({ retaceosApi: { create: mocks.create } }));
vi.mock('$lib/api/catalog', () => ({
  catalogApi: {
    getProduct: vi
      .fn()
      .mockResolvedValue({ id_product: 4, sku: 'PRD-AZU-004', name: 'Azúcar Glass Premium 10kg' })
  }
}));
vi.mock('$lib/stores/permissions.svelte', () => ({ permissions: { hasPermission: () => true } }));

const purchase = {
  id: 'purchase',
  code: 'COM-00026',
  status: 'received',
  inventory_workflow: 'retaceo_before_inventory',
  currency: 'USD',
  subtotal: '40000',
  supplier_invoice_number: 'FAC-26',
  supplier_invoice_date: '2026-10-27',
  details: [
    {
      id: 'line',
      product_id: 4,
      quantity_received: '10',
      quantity_accepted: null,
      subtotal: '40000',
      discount: '10',
      tax_amount: '0'
    }
  ]
};

describe('Retaceo manual creation', () => {
  beforeEach(() => {
    mocks.getPurchase.mockReset().mockResolvedValue(purchase);
    mocks.create.mockReset().mockResolvedValue({ id: 'retaceo-new' });
    mocks.goto.mockReset();
  });

  it('starts freight and DAI empty, shows the invoice FOB and keeps the invoice read-only', async () => {
    const { container } = render(RetaceoCreateEditor, { purchaseId: 'purchase' });
    expect(await screen.findByText('FOB desde la factura (fijo)')).toBeInTheDocument();
    expect(screen.getByRole('spinbutton', { name: /Flete y seguro/ })).toHaveValue(null);
    expect(screen.getByRole('spinbutton', { name: /^DAI/ })).toHaveValue(null);
    // 40000 - 10 of discount, shown as the fixed FOB (also in the per-product list).
    expect(screen.getAllByText(/39,990\.00/).length).toBeGreaterThan(0);
    expect(screen.queryByRole('radio')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Factura de importación')).toHaveValue('FAC-26');
    expect(screen.getByLabelText('Factura de importación')).toHaveAttribute('readonly');
    expect(screen.getByLabelText('Fecha de factura')).toHaveAttribute('readonly');
    saveRetaceoPreview('crear-retaceo', container);
  });

  it('does not silently use zero for an omitted fixed component', async () => {
    const { container } = render(RetaceoCreateEditor, { purchaseId: 'purchase' });
    await fireEvent.input(await screen.findByRole('spinbutton', { name: /Flete y seguro/ }), {
      target: { value: '12' }
    });
    await fireEvent.submit(container.querySelector('form')!);
    expect(mocks.create).not.toHaveBeenCalled();
    expect(
      screen.getByText('Completa el flete y seguro y el DAI; escribe 0 cuando no apliquen.')
    ).toBeInTheDocument();
    expect(screen.getByText('Escribe un importe; usa 0 si no aplica.')).toBeInTheDocument();
  });

  it('sends only the typed freight and DAI; the FOB is never sent', async () => {
    const { container } = render(RetaceoCreateEditor, { purchaseId: 'purchase' });
    await fireEvent.input(await screen.findByRole('spinbutton', { name: /Flete y seguro/ }), {
      target: { value: '12' }
    });
    await fireEvent.input(screen.getByRole('spinbutton', { name: /^DAI/ }), {
      target: { value: '0' }
    });
    await fireEvent.submit(container.querySelector('form')!);
    await waitFor(() =>
      expect(mocks.create).toHaveBeenCalledWith(
        expect.objectContaining({
          purchase_id: 'purchase',
          total_freight: '12',
          total_dai: '0',
          total_expenses: '0'
        })
      )
    );
    expect(mocks.create.mock.calls[0]![0]).not.toHaveProperty('fob_lines');
    expect(mocks.create.mock.calls[0]![0]).not.toHaveProperty('import_vat');
    expect(mocks.goto).toHaveBeenCalledWith('/retaceos/retaceo-new/edit');
  });
});
