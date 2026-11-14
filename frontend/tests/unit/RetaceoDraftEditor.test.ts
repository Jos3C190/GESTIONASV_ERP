import { fireEvent, render, screen, waitFor, within } from '@testing-library/svelte';
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

  it('shows the FOB read-only, previews the split by FOB and never sends allocations', async () => {
    const detail = (id: string, product: number, fob: string) => ({
      id: `detail-${id}`,
      retaceo_id: retaceo.id,
      purchase_detail_id: id,
      product_id: product,
      unit_id: 3,
      quantity: '1',
      cost_fob: fob,
      freight: '0',
      expenses: '0',
      dai: '0',
      total_cost: fob,
      unit_cost: fob,
      created_at: null,
      updated_at: null
    });
    const cost = (id: string, classification: 'freight' | 'dai', amount: string) => ({
      ...retaceo.costs![0]!,
      id,
      classification,
      title: classification === 'dai' ? 'DAI' : 'Flete',
      amount
    });
    const manual: Retaceo = {
      ...retaceo,
      manual_entry: true,
      details: [detail('line-a', 10, '100'), detail('line-b', 11, '300')],
      costs: [
        cost('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1', 'freight', '10'),
        cost('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2', 'dai', '3')
      ],
      total_expenses: '0',
      total_fob: '400'
    };
    mocks.getRetaceo.mockResolvedValue(manual);
    mocks.update.mockResolvedValue(manual);
    render(RetaceoDraftEditor, { retaceoId: retaceo.id });

    expect(await screen.findByText('FOB desde la factura (fijo)')).toBeInTheDocument();
    expect(screen.getByText('FOB por producto (desde la factura)')).toBeInTheDocument();
    expect(screen.queryAllByRole('radio')).toHaveLength(0);
    expect(screen.queryByText(/IVA/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Distribuir/ })).not.toBeInTheDocument();
    // Only freight, DAI and the cost amounts are numeric inputs; no FOB or per-line allocation input.
    expect(screen.queryByRole('spinbutton', { name: /FOB|asignado/i })).not.toBeInTheDocument();
    expect(
      screen.getAllByText(
        'Este importe se reparte automáticamente entre los productos según su FOB.'
      ).length
    ).toBeGreaterThan(0);

    await fireEvent.input(screen.getByRole('spinbutton', { name: 'Flete y seguro (USD)' }), {
      target: { value: '20' }
    });
    const split = within(screen.getAllByRole('list', { name: 'Reparto por producto' })[0]!);
    const rows = split.getAllByRole('listitem').map((row) => row.textContent ?? '');
    expect(rows[0]).toContain('5.00');
    expect(rows[1]).toContain('15.00');

    await fireEvent.submit(
      screen.getByRole('button', { name: 'Guardar borrador' }).closest('form')!
    );
    await waitFor(() => expect(mocks.update).toHaveBeenCalledTimes(1));
    const payload = mocks.update.mock.calls[0]![1];
    expect(payload).toMatchObject({ total_freight: '20', total_dai: '3.000000' });
    for (const retired of ['calculation_mode', 'dai_rate', 'vat_rate', 'import_vat', 'fob_lines']) {
      expect(payload).not.toHaveProperty(retired);
    }
    for (const sent of payload.costs) expect(sent).not.toHaveProperty('allocations');
  });

  it('blocks saving a draft with an empty freight and accepts zero', async () => {
    const manual: Retaceo = {
      ...retaceo,
      manual_entry: true,
      details: [
        {
          id: 'detail-a',
          retaceo_id: retaceo.id,
          purchase_detail_id: 'line-a',
          product_id: 10,
          unit_id: 3,
          quantity: '1',
          cost_fob: '100',
          freight: '10',
          expenses: '0',
          dai: '3',
          total_cost: '113',
          unit_cost: '113',
          created_at: null,
          updated_at: null
        }
      ],
      total_expenses: '0'
    };
    mocks.getRetaceo.mockResolvedValue(manual);
    mocks.update.mockResolvedValue(manual);
    render(RetaceoDraftEditor, { retaceoId: retaceo.id });
    const freight = await screen.findByRole('spinbutton', { name: 'Flete y seguro (USD)' });
    const form = screen.getByRole('button', { name: 'Guardar borrador' }).closest('form')!;

    expect(form).toHaveAttribute('novalidate');
    await fireEvent.input(freight, { target: { value: '' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Guardar borrador' }));
    expect(await screen.findByText('Escribe un importe; usa 0 si no aplica.')).toBeInTheDocument();
    expect(freight).toBeInvalid();
    expect(mocks.update).not.toHaveBeenCalled();

    await fireEvent.input(freight, { target: { value: '-5' } });
    await fireEvent.submit(form);
    expect(await screen.findByText('El importe no puede ser negativo.')).toBeInTheDocument();
    expect(mocks.update).not.toHaveBeenCalled();

    await fireEvent.input(freight, { target: { value: '0' } });
    await fireEvent.submit(form);
    await waitFor(() => expect(mocks.update).toHaveBeenCalledTimes(1));
    expect(mocks.update.mock.calls[0]![1]).toMatchObject({ total_freight: '0' });
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
        notes: 'Inicial',
        costs: [
          {
            id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
            classification: 'freight',
            title: 'Flete internacional',
            description: null,
            amount: '12.000000'
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
