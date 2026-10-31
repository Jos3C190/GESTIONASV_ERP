import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import RetaceoDraftEditor from '$lib/features/retaceos/components/RetaceoDraftEditor.svelte';
import type { Retaceo } from '$lib/types/retaceo';

const mocks = vi.hoisted(() => ({
  goto: vi.fn(),
  getRetaceo: vi.fn(),
  update: vi.fn(),
  getPurchase: vi.fn(),
  hasPermission: vi.fn()
}));

vi.mock('$app/navigation', () => ({
  goto: mocks.goto
}));
vi.mock('$lib/api/client', async (original) => ({
  ...(await original<object>()),
  apiFetch: vi.fn().mockResolvedValue([])
}));

vi.mock('$lib/api/retaceos', () => ({
  retaceosApi: {
    get: mocks.getRetaceo,
    update: mocks.update
  }
}));

vi.mock('$lib/api/purchases', () => ({
  purchasesApi: {
    get: mocks.getPurchase
  }
}));

vi.mock('$lib/api/catalog', () => ({
  catalogApi: {
    listUnits: vi.fn().mockResolvedValue([]),
    getProduct: vi.fn().mockResolvedValue(null)
  }
}));

vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: {
    hasPermission: mocks.hasPermission
  }
}));

const retaceo: Retaceo = {
  id: '11111111-1111-1111-1111-111111111111',
  company_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  code: 'RET-0001',
  purchase_id: '22222222-2222-2222-2222-222222222222',
  branch_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  created_by_id: 'dddddddd-dddd-dddd-dddd-dddddddddddd',
  currency: 'USD',
  details: [],
  costs: [
    {
      id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
      retaceo_id: '11111111-1111-1111-1111-111111111111',
      source_purchase_order_expense_id: null,
      expense_type_id: null,
      classification: 'freight',
      title: 'Flete',
      description: null,
      amount: '10.000000',
      is_active: true,
      allocations: [],
      documents: [],
      created_at: null,
      updated_at: null
    }
  ],
  total_fob: '100.000000',
  total_freight: '10.000000',
  total_expenses: '5.000000',
  total_dai: '3.000000',
  import_vat: '15.340000',
  total_cost: '118.000000',
  freight_percentage: '10.000000',
  expense_percentage: '5.000000',
  dai_percentage: '3.000000',
  status: 'draft',
  notes: 'Inicial',
  created_at: null,
  updated_at: null
};

describe('RetaceoDraftEditor', () => {
  beforeEach(() => {
    mocks.goto.mockReset();
    mocks.getRetaceo.mockReset();
    mocks.update.mockReset();
    mocks.getPurchase.mockReset();
    mocks.hasPermission.mockReset();

    mocks.hasPermission.mockImplementation((code: string) => code === 'retaceos:manage');
    mocks.getRetaceo.mockResolvedValue(retaceo);
    mocks.getPurchase.mockResolvedValue({
      id: retaceo.purchase_id,
      code: 'COM-0001'
    });
  });

  it('reopens the saved automatic mode and recalculates taxes after a freight change', async () => {
    const detail = {
      id: 'detail',
      retaceo_id: retaceo.id,
      purchase_detail_id: 'line',
      product_id: 10,
      unit_id: 3,
      quantity: '1',
      cost_fob: '100',
      freight: '10',
      expenses: '0',
      dai: '11',
      total_cost: '121',
      unit_cost: '121',
      created_at: null,
      updated_at: null
    };
    const automatic: Retaceo = {
      ...retaceo,
      manual_entry: true,
      calculation_mode: 'automatic',
      dai_rate: '10',
      vat_rate: '13',
      details: [detail],
      total_expenses: '0',
      total_dai: '11',
      import_vat: '15.73',
      total_cost: '121'
    };
    mocks.getRetaceo.mockResolvedValue(automatic);
    mocks.getPurchase.mockResolvedValue({
      id: retaceo.purchase_id,
      code: 'COM-0001',
      details: [
        {
          id: 'line',
          product_id: 10,
          subtotal: '100',
          discount: '0',
          quantity_received: '1',
          quantity_accepted: null
        }
      ]
    });
    mocks.update.mockResolvedValue(automatic);
    render(RetaceoDraftEditor, { retaceoId: retaceo.id });
    expect(await screen.findByRole('radio', { name: /^Automático/ })).toBeChecked();
    expect(screen.getByRole('spinbutton', { name: 'DAI (%)' })).toHaveValue(10);
    expect(screen.getByRole('spinbutton', { name: 'IVA (%)' })).toHaveValue(13);
    expect(screen.queryByRole('spinbutton', { name: /FOB total/ })).not.toBeInTheDocument();
    await fireEvent.input(screen.getByRole('spinbutton', { name: /Flete y seguro total/ }), {
      target: { value: '20' }
    });
    await fireEvent.submit(
      screen.getByRole('button', { name: 'Guardar borrador' }).closest('form')!
    );
    await waitFor(() =>
      expect(mocks.update).toHaveBeenCalledWith(
        retaceo.id,
        expect.objectContaining({
          calculation_mode: 'automatic',
          dai_rate: '10',
          vat_rate: '13',
          total_freight: '20',
          total_dai: '12.000000',
          import_vat: '17.160000'
        })
      )
    );
    expect(mocks.update.mock.calls[0]![1]).not.toHaveProperty('fob_lines');
  });

  it('updates the itemized draft cost and opens the calculation step', async () => {
    mocks.update.mockResolvedValue({
      ...retaceo,
      total_freight: '12.000000',
      costs: retaceo.costs?.map((cost) => ({
        ...cost,
        title: 'Flete internacional',
        amount: '12.000000'
      }))
    });

    render(RetaceoDraftEditor, {
      props: { retaceoId: retaceo.id }
    });

    expect(
      await screen.findByRole('heading', { name: 'Costos y comprobantes' })
    ).toBeInTheDocument();
    expect(screen.getByText('Retaceo · RET-0001')).toBeInTheDocument();
    expect(screen.getByText(/Compra COM-0001/)).toBeInTheDocument();

    await fireEvent.input(screen.getByLabelText('Concepto'), {
      target: { value: 'Flete internacional' }
    });
    await fireEvent.input(screen.getByLabelText('Monto real · USD'), {
      target: { value: '12.000000' }
    });

    await fireEvent.submit(
      screen.getByRole('button', { name: 'Guardar borrador' }).closest('form')!
    );

    await waitFor(() => {
      expect(mocks.update).toHaveBeenCalledWith(retaceo.id, {
        calculation_mode: 'manual',
        dai_rate: null,
        vat_rate: null,
        import_data: {
          origin_country: null,
          import_invoice_number: null,
          import_invoice_date: null,
          import_policy_number: null,
          import_policy_date: null
        },
        total_freight: '10.000000',
        total_expenses: '5.000000',
        total_dai: '3.000000',
        import_vat: '15.340000',
        notes: 'Inicial',
        costs: [
          {
            id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
            classification: 'freight',
            title: 'Flete internacional',
            description: null,
            amount: '12.000000',
            allocations: []
          }
        ]
      });
    });

    expect(
      await screen.findByText(
        'Borrador guardado. Puedes adjuntar comprobantes de forma opcional o abrir el detalle para calcular el retaceo.'
      )
    ).toBeInTheDocument();
    expect(mocks.goto).not.toHaveBeenCalled();
  });

  it('blocks editing for a non-draft retaceo', async () => {
    mocks.getRetaceo.mockResolvedValue({
      ...retaceo,
      status: 'calculated'
    });

    render(RetaceoDraftEditor, {
      props: { retaceoId: retaceo.id }
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Solo los retaceos en borrador pueden editarse.'
    );

    expect(mocks.getPurchase).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: 'Guardar borrador' })).not.toBeInTheDocument();
  });

  it('blocks editing without retaceos:manage', async () => {
    mocks.hasPermission.mockReturnValue(false);

    render(RetaceoDraftEditor, {
      props: { retaceoId: retaceo.id }
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No tienes permiso para gestionar retaceos.'
    );

    expect(mocks.getRetaceo).not.toHaveBeenCalled();
  });
});
