import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import RetaceoDraftEditor from '$lib/features/retaceos/components/RetaceoDraftEditor.svelte';
import RetaceoAveragePanel from '$lib/features/retaceos/components/RetaceoAveragePanel.svelte';
import PurchaseOrderActualExpenses from '$lib/features/purchase-orders/components/PurchaseOrderActualExpenses.svelte';
import type { Retaceo } from '$lib/types/retaceo';
import type { PurchaseOrder } from '$lib/types/purchase-order';
import { saveRetaceoPreview } from './retaceo-preview';

const mocks = vi.hoisted(() => ({
  categories: vi.fn(),
  update: vi.fn(),
  actuals: vi.fn(),
  availability: vi.fn(),
  record: vi.fn(),
  average: vi.fn(),
  get: vi.fn()
}));
vi.mock('$lib/api/client', async (original) => ({
  ...(await original<object>()),
  apiFetch: mocks.categories
}));
vi.mock('$lib/api/retaceos', () => ({
  retaceosApi: {
    get: mocks.get,
    update: mocks.update,
    averageComparison: mocks.average
  }
}));
vi.mock('$lib/api/purchases', () => ({
  purchasesApi: {
    get: vi.fn(async () => ({
      code: 'COM-00026',
      purchase_order_id: 'order',
      inventory_workflow: 'retaceo_before_inventory'
    }))
  }
}));
vi.mock('$lib/api/purchase-orders', () => ({
  purchaseOrdersApi: {
    get: vi.fn(async () => ({ expenses: [], currency: 'USD' })),
    listExpenseTypes: vi.fn(async () => [
      { id: 'gas', name: 'Gasolina' },
      { id: 'freight', name: 'Flete' }
    ]),
    listExpenseDocuments: vi.fn(async () => [])
  }
}));
vi.mock('$lib/features/purchase-orders/actual-expenses', () => ({
  actualExpensesApi: { list: mocks.actuals, create: mocks.record, availability: mocks.availability }
}));
vi.mock('$lib/api/catalog', () => ({
  catalogApi: {
    getProduct: vi.fn(async () => ({
      id_product: 4,
      name: 'Azúcar Glass Premium 10kg',
      sku: 'PRD-AZU-004'
    })),
    listUnits: vi.fn(async () => [{ id_unit: 2, code: 'cj', name: 'Caja' }])
  }
}));
vi.mock('$lib/stores/permissions.svelte', () => ({ permissions: { hasPermission: () => true } }));

const record: Retaceo = {
  id: 'ret',
  company_id: 'company',
  code: 'RET-00020',
  purchase_id: 'purchase',
  branch_id: 'branch',
  created_by_id: 'admin',
  currency: 'USD',
  status: 'draft',
  manual_entry: true,
  total_fob: '100',
  total_freight: '10',
  total_dai: '0',
  import_vat: '0',
  total_expenses: '0',
  total_cost: '110',
  freight_percentage: '10',
  expense_percentage: '0',
  dai_percentage: '0',
  notes: null,
  created_at: null,
  updated_at: null,
  details: [
    {
      id: 'detail',
      retaceo_id: 'ret',
      purchase_detail_id: 'line',
      product_id: 4,
      unit_id: 2,
      quantity: '10',
      cost_fob: '100',
      freight: '10',
      dai: '0',
      expenses: '0',
      total_cost: '110',
      unit_cost: '11',
      created_at: null,
      updated_at: null
    }
  ],
  costs: [
    {
      id: 'cost',
      retaceo_id: 'ret',
      source_purchase_order_expense_id: null,
      expense_type_id: null,
      classification: 'freight',
      title: 'Flete',
      amount: '10',
      is_active: true,
      description: null,
      allocations: [{ purchase_detail_id: 'line', amount: '10' }],
      documents: [],
      created_at: null,
      updated_at: null
    }
  ]
};

describe('Manual retaceo and actual spending', () => {
  beforeEach(() => {
    mocks.get.mockReset().mockResolvedValue(record);
    mocks.categories.mockReset().mockResolvedValue([{ id: 'gas', name: 'Gasolina' }]);
    mocks.actuals.mockReset().mockResolvedValue([]);
    mocks.availability.mockReset().mockResolvedValue({
      can_record: true,
      reason: null,
      closed_retaceo_id: null,
      closed_retaceo_code: null
    });
    mocks.update.mockReset().mockResolvedValue(record);
    mocks.record.mockReset();
  });

  it('keeps fixed classes separate and sends categorized, dated other expenses', async () => {
    const { container } = render(RetaceoDraftEditor, { retaceoId: 'ret' });
    await screen.findByRole('heading', { name: 'Costos y comprobantes' });
    await fireEvent.click(screen.getByRole('button', { name: '+ Agregar otro gasto' }));
    await fireEvent.input(screen.getByLabelText('Concepto'), {
      target: { value: 'Gasolina del viaje' }
    });
    await fireEvent.change(screen.getByLabelText('Categoría del otro gasto'), {
      target: { value: 'gas' }
    });
    await fireEvent.input(screen.getByLabelText('Fecha del gasto'), {
      target: { value: '2026-10-27' }
    });
    await fireEvent.input(screen.getByLabelText(/Monto real/), { target: { value: '25' } });
    await fireEvent.input(screen.getByLabelText('Descripción o referencia'), {
      target: { value: 'Recibo GAS-25' }
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Distribuir según FOB' }));
    expect(screen.queryByLabelText('Clasificación')).not.toBeInTheDocument();
    saveRetaceoPreview('editar-retaceo', container);
    await fireEvent.submit(container.querySelector('form')!);
    await waitFor(() => expect(mocks.update).toHaveBeenCalled());
    expect(mocks.update.mock.calls[0]![1]).toMatchObject({
      total_freight: '10',
      total_dai: '0',
      total_expenses: '25.000000',
      costs: expect.arrayContaining([
        expect.objectContaining({
          classification: 'expense',
          expense_type_id: 'gas',
          incurred_on: '2026-10-27',
          amount: '25',
          allocations: [{ purchase_detail_id: 'line', amount: '25.000000' }]
        })
      ])
    });
  });

  it('retrying reference data preserves captured financial amounts', async () => {
    mocks.categories.mockRejectedValueOnce(new Error('Catálogo temporalmente no disponible'));
    render(RetaceoDraftEditor, { retaceoId: 'ret' });
    await screen.findByText('Catálogo temporalmente no disponible');
    const fob = screen.getByRole('spinbutton', { name: /FOB total/ });
    await fireEvent.input(fob, { target: { value: '125' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar categorías y bitácora' }));
    await waitFor(() =>
      expect(screen.queryByText('Catálogo temporalmente no disponible')).not.toBeInTheDocument()
    );
    expect(fob).toHaveValue(125);
  });

  it('identifies attachments as optional and allows a draft without files', async () => {
    const { container } = render(RetaceoDraftEditor, { retaceoId: 'ret' });
    await screen.findByText('Sin comprobantes adjuntos. Puedes calcular el retaceo sin archivos.');
    expect(screen.getByRole('heading', { name: /Comprobantes \(opcional\)/ })).toBeInTheDocument();
    expect(screen.queryByText(/Se requiere al menos uno para calcular/)).not.toBeInTheDocument();
    await fireEvent.submit(container.querySelector('form')!);
    await waitFor(() => expect(mocks.update).toHaveBeenCalled());
  });

  it.each(['12', '0.5'])(
    'preserves fixed expense identity and its document through 10 → 0 → %s',
    async (value) => {
      mocks.get.mockResolvedValue({
        ...record,
        costs: record.costs!.map((cost) => ({
          ...cost,
          documents: [
            {
              id: 'attachment',
              document_id: 'document',
              retaceo_cost_id: cost.id,
              file_name: 'Flete.pdf',
              file_type: 'application/pdf',
              uploaded_at: '2026-10-27T12:00:00Z',
              created_at: null,
              updated_at: null
            }
          ]
        }))
      });
      const { container } = render(RetaceoDraftEditor, { retaceoId: 'ret' });
      await screen.findByText('Flete.pdf');
      const field = screen.getByRole('spinbutton', { name: /Flete total/ });
      await fireEvent.input(field, { target: { value: '0' } });
      expect(screen.getByText('Flete.pdf')).toBeInTheDocument();
      await fireEvent.input(field, { target: { value } });
      expect(screen.getByText('Flete.pdf')).toBeInTheDocument();
      await fireEvent.submit(container.querySelector('form')!);
      await waitFor(() => expect(mocks.update).toHaveBeenCalled());
      expect(mocks.update.mock.calls[0]![1].costs).toEqual(
        expect.arrayContaining([
          expect.objectContaining({ id: 'cost', classification: 'freight', amount: value })
        ])
      );
    }
  );

  it('associates validation messages with fixed fields and other expense controls', async () => {
    const { container } = render(RetaceoDraftEditor, { retaceoId: 'ret' });
    await screen.findByRole('heading', { name: 'Costos y comprobantes' });
    await fireEvent.click(screen.getByRole('button', { name: '+ Agregar otro gasto' }));
    const dai = screen.getByRole('spinbutton', { name: /DAI total/ });
    await fireEvent.input(dai, { target: { value: '' } });
    await fireEvent.submit(container.querySelector('form')!);
    const category = screen.getByRole('combobox', { name: /Categoría del otro gasto/ });
    const date = screen.getByLabelText(/^Fecha del gasto/);
    const description = screen.getByLabelText(/^Descripción o referencia/);
    for (const field of [dai, category, date, description]) {
      expect(field).toHaveAttribute('aria-invalid', 'true');
      const descriptions = field.getAttribute('aria-describedby')!.split(' ');
      expect(
        descriptions.some((id) => document.getElementById(id)?.getAttribute('role') === 'alert')
      ).toBe(true);
    }
    expect(mocks.update).not.toHaveBeenCalled();
    saveRetaceoPreview('errores-retaceo', container);
  });

  it('offers actual expense recording during shipment wait and excludes freight categories', async () => {
    const order = { id: 'order', currency: 'USD', status: 'sent' } as PurchaseOrder;
    const { container } = render(PurchaseOrderActualExpenses, { order });
    const toggle = screen.getByRole('button', { name: 'Ver / registrar bitácora' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('button', { name: 'Registrar gasto real' })).not.toBeInTheDocument();
    await fireEvent.click(toggle);
    await screen.findByText('Todavía no hay gastos reales registrados');
    expect(screen.getByText('Opcional')).toBeInTheDocument();
    expect(
      screen.getByText(/puedes continuar con la recepción y el retaceo sin llenar/)
    ).toBeInTheDocument();
    expect(mocks.record).not.toHaveBeenCalled();
    expect(screen.queryByRole('option', { name: 'Flete' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Registrar gasto real' })).toBeEnabled();
    await fireEvent.input(screen.getByLabelText('Descripción'), { target: { value: 'Gasolina' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Ocultar bitácora' }));
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await fireEvent.click(toggle);
    expect(screen.getByLabelText('Descripción')).toHaveValue('Gasolina');
    saveRetaceoPreview('bitacora-gastos', container);
  });

  it('does not claim an empty log when its request failed', async () => {
    mocks.actuals.mockRejectedValueOnce(new Error('No se pudo consultar la bitácora'));
    render(PurchaseOrderActualExpenses, {
      order: { id: 'order', currency: 'USD', status: 'sent' } as PurchaseOrder
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Ver / registrar bitácora' }));
    await screen.findByRole('alert');
    expect(screen.queryByText('Todavía no hay gastos reales registrados')).not.toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar carga' }));
    await screen.findByText('Todavía no hay gastos reales registrados');
    await fireEvent.click(screen.getByRole('button', { name: 'Registrar primer gasto' }));
    expect(screen.getByLabelText('Tipo de gasto')).toHaveFocus();
  });

  it('locks the received order after retaceo closure and preserves its unassigned spending', async () => {
    mocks.availability.mockResolvedValue({
      can_record: false,
      reason:
        'RET-00021 está cerrado. Ya no se pueden registrar otros gastos reales para esta orden.',
      closed_retaceo_id: 'ret',
      closed_retaceo_code: 'RET-00021'
    });
    mocks.actuals.mockResolvedValue([
      {
        id: 'late-expense',
        expense_type_id: 'gas',
        amount: '33',
        allocated_amount: '0',
        unallocated_amount: '33',
        incurred_on: '2026-10-27',
        reference: '333',
        description: 'Gasto registrado sin asignar'
      }
    ]);
    render(PurchaseOrderActualExpenses, {
      order: { id: 'order', currency: 'USD', status: 'received' } as PurchaseOrder
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Ver / registrar bitácora' }));
    await screen.findByText(/RET-00021 está cerrado/);
    expect(screen.queryByRole('button', { name: 'Registrar gasto real' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Consultar RET-00021' })).toHaveAttribute(
      'href',
      '/retaceos/ret'
    );
    expect(screen.getByText(/Sin incorporar al costo: \$33.00/)).toBeInTheDocument();
    expect(screen.getByText('Gasolina · 333')).toBeInTheDocument();
    expect(mocks.record).not.toHaveBeenCalled();
  });

  it('refreshes the closure restriction when a stale open form is rejected by the server', async () => {
    mocks.record.mockRejectedValue(new Error('El retaceo ya está cerrado'));
    const { container } = render(PurchaseOrderActualExpenses, {
      order: { id: 'order', currency: 'USD', status: 'received' } as PurchaseOrder
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Ver / registrar bitácora' }));
    await screen.findByRole('button', { name: 'Registrar gasto real' });
    mocks.availability.mockResolvedValue({
      can_record: false,
      reason: 'RET-00021 está cerrado.',
      closed_retaceo_id: 'ret',
      closed_retaceo_code: 'RET-00021'
    });
    await fireEvent.submit(container.querySelector('form')!);
    await screen.findByText('RET-00021 está cerrado.');
    expect(screen.queryByRole('button', { name: 'Registrar gasto real' })).not.toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('El retaceo ya está cerrado');
  });

  it('identifies a historical correction as value only instead of a new receipt', async () => {
    mocks.average.mockResolvedValue({
      currency: 'USD',
      mode: 'preview',
      value_only: true,
      lines: [
        {
          product_id: 4,
          inventory_item_id: 'item',
          base_unit_id: 2,
          previous_quantity: '8',
          previous_value: '0',
          previous_average: '0',
          incoming_quantity: '0',
          incoming_value: '80',
          resulting_quantity: '8',
          resulting_value: '80',
          resulting_average: '10'
        }
      ]
    });
    const { container } = render(RetaceoAveragePanel, {
      retaceoId: 'ret',
      contextKey: 'company',
      productLabels: new Map([[4, 'Azúcar Glass Premium 10kg']]),
      unitLabels: new Map([[2, 'cj']])
    });
    await screen.findByText(/Regularización de una recepción ya registrada/);
    expect(screen.getAllByText('Ajuste de valor')).toHaveLength(2);
    expect(screen.queryByText('Entrada del retaceo')).not.toBeInTheDocument();
    saveRetaceoPreview('comparacion-correccion', container);
  });
});
