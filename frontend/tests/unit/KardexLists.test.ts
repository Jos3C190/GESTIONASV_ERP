import { fireEvent, render, within } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import PhysicalKardexList from '../../src/lib/features/inventory/components/PhysicalKardexList.svelte';
import KardexReconciliationList from '../../src/lib/features/inventory/components/KardexReconciliationList.svelte';
import ValuedKardexList from '../../src/lib/features/inventory/components/ValuedKardexList.svelte';
import type {
  PhysicalKardex,
  Reconciliation,
  ValuedKardex
} from '../../src/lib/features/inventory/kardex';

const physicalData: PhysicalKardex = {
  warehouse_id: 'warehouse-1',
  inventory_item_id: 'item-1',
  period_from: '2026-10-01',
  period_to: '2026-10-14',
  balance_basis: 'Corte físico aprobado',
  opening_known: true,
  opening_quantity: '4',
  incoming_quantity: '2',
  outgoing_quantity: '1',
  closing_known: true,
  closing_quantity: '5',
  items: [
    {
      id: 'line-1',
      movement_id: 'movement-1',
      movement_type: 'transfer',
      source_reference: 'TR-0001',
      posted_at: '2026-10-14T12:00:00Z',
      product_name: 'Chocolate',
      product_sku: 'CH-001',
      base_unit_symbol: 'cj',
      lot_code: 'LOT-1',
      receipt_lot_code: 'LOT-COM-00001-D1',
      receipt_lot_header_code: 'LOT-COM-00001',
      handling_unit_id: 'hu-1',
      handling_unit_code: 'HU-1',
      from_warehouse_id: 'warehouse-1',
      from_warehouse_external: false,
      from_warehouse_code: 'BOD-1',
      from_warehouse_name: 'Bodega Central',
      from_location_id: 'loc-1',
      from_location_code: 'A-01',
      from_stock_status: 'available',
      to_warehouse_id: null,
      to_warehouse_external: true,
      to_warehouse_code: null,
      to_warehouse_name: null,
      to_location_id: null,
      to_location_code: null,
      to_stock_status: null,
      quantity_base: '1',
      incoming_quantity: '0',
      outgoing_quantity: '1',
      net_quantity: '-1',
      balance_after: '5',
      is_internal: false
    }
  ],
  page: 1,
  page_size: 25,
  total: 1
};

const reconciliationData: Reconciliation = {
  valuation_enabled: true,
  currency: 'USD',
  items: [
    {
      inventory_item_id: 'item-1',
      product_name: 'Chocolate',
      sku: 'CH-001',
      base_unit_symbol: 'cj',
      physical_quantity: '5',
      valued_quantity: '5',
      quantity_difference: '0',
      inventory_value: '50',
      average_unit_cost: '10'
    }
  ],
  page: 1,
  page_size: 50,
  total: 1
};

const valuedData: ValuedKardex = {
  inventory_item_id: 'item-1',
  setting: {
    currency: 'USD',
    opened_at: '2026-10-01T06:00:00Z',
    opening_reference: 'CUT-001'
  },
  period_from: '2026-10-01',
  period_to: '2026-10-14',
  opening_known: true,
  opening_quantity: '4',
  opening_value: '40',
  closing_known: true,
  closing_quantity: '5',
  closing_value: '50',
  period_value_change: '10',
  entries: [
    {
      id: 'entry-1',
      sequence: 1,
      kind: 'receipt',
      quantity_base: '1',
      source_value: '10',
      original_entry_id: null,
      movement_line_id: 'line-1',
      purchase_detail_id: 'purchase-line-1',
      retaceo_id: 'retaceo-1',
      source_reference: 'COM-0001',
      operational_date: '2026-10-14',
      accounting_date: '2026-10-14',
      posted_at: '2026-10-14T12:00:00Z',
      posted_by: 'user-1',
      inventory_delta: '10',
      balance_quantity: '5',
      balance_value: '50',
      average_unit_cost: '10',
      cost_breakdown: [{ source_reference: 'FLETE-1', amount: '10' }]
    }
  ],
  page: 1,
  page_size: 25,
  total: 1
};

function findMobileList(container: HTMLElement): HTMLElement {
  const list = container.querySelector<HTMLElement>('[class*="xl:hidden"]');
  if (!list) throw new Error('No se encontró la lista adaptable para móvil.');
  return list;
}

describe('Kardex list presentations', () => {
  it('conserva la precisión del promedio histórico y distingue el costo de la entrada', () => {
    const data = {
      ...valuedData,
      entries: [
        {
          ...valuedData.entries[0]!,
          average_unit_cost: '13.333333',
          applied_unit_cost: '15.000000',
          document_reference: 'COM-00027',
          receipt_lot_code: 'LOT-COM-00027',
          operator: 'rodrigo'
        }
      ]
    };
    const { container } = render(ValuedKardexList, { data, loading: false, onPageChange: vi.fn() });
    const list = within(findMobileList(container));
    expect(list.getByText('USD 13.333333')).toBeInTheDocument();
    expect(list.getByText('USD 15.00')).toBeInTheDocument();
    expect(list.getByText('Registró: rodrigo')).toBeInTheDocument();
    expect(list.getByText('COM-00027')).toBeInTheDocument();
    expect(list.getByText('Lote: LOT-COM-00027')).toBeInTheDocument();
    expect(list.getByText('Promedio después del movimiento')).toBeInTheDocument();
  });
  it('muestra el recorrido físico en una tarjeta y abre el detalle', async () => {
    const onOpenDetail = vi.fn();
    const { container } = render(PhysicalKardexList, {
      props: { data: physicalData, page: 1, loading: false, onPageChange: vi.fn(), onOpenDetail }
    });

    const mobileList = findMobileList(container);
    expect(within(mobileList).getByText('Bodega Central → Punto externo')).toBeInTheDocument();
    expect(within(mobileList).getByText('Lote fabricante LOT-1')).toBeInTheDocument();
    expect(within(mobileList).getByText('Lote de recepción LOT-COM-00001-D1')).toBeInTheDocument();
    await fireEvent.click(within(mobileList).getByRole('button', { name: 'Ver detalle' }));
    expect(onOpenDetail).toHaveBeenCalledWith(physicalData.items[0]);
  });

  it('explica cuando el saldo físico no se puede reconstruir', () => {
    const data: PhysicalKardex = {
      ...physicalData,
      items: physicalData.items.map((row) => ({ ...row, balance_after: null }))
    };
    const { container } = render(PhysicalKardexList, {
      props: { data, page: 1, loading: false, onPageChange: vi.fn(), onOpenDetail: vi.fn() }
    });

    const mobileList = findMobileList(container);
    expect(within(mobileList).getByText('Saldo no reconstruible')).toBeInTheDocument();
  });

  it('muestra el resumen de conciliación y abre el Kardex del artículo', async () => {
    const onOpenKardex = vi.fn();
    const { container } = render(KardexReconciliationList, {
      props: { data: reconciliationData, page: 1, onPageChange: vi.fn(), onOpenKardex }
    });

    const mobileList = findMobileList(container);
    expect(within(mobileList).getByText('Cantidad física')).toBeInTheDocument();
    expect(within(mobileList).getByText('USD 50.00')).toBeInTheDocument();
    const historyButton = within(mobileList).getByRole('button', {
      name: 'Ver Kardex de Chocolate'
    });
    expect(historyButton).toHaveClass('whitespace-nowrap');
    expect(within(historyButton).getByText('de Chocolate')).toHaveClass('sr-only');
    await fireEvent.click(historyButton);
    expect(onOpenKardex).toHaveBeenCalledWith(reconciliationData.items[0]);
  });

  it('muestra las fechas y el desglose del valorado en la tarjeta móvil', () => {
    const { container } = render(ValuedKardexList, {
      props: { data: valuedData, loading: false, onPageChange: vi.fn(), canReadRetaceos: true }
    });

    const mobileList = findMobileList(container);
    expect(within(mobileList).getByText('COM-0001')).toBeInTheDocument();
    expect(within(mobileList).getByText('Fecha operativa: 14 oct 2026')).toBeInTheDocument();
    expect(within(mobileList).getByRole('link', { name: 'Ver retaceo aplicado' })).toHaveAttribute(
      'href',
      '/retaceos/retaceo-1'
    );
  });

  it('muestra cantidad cero como ajuste y separa la salida revaluada', () => {
    const data: ValuedKardex = {
      ...valuedData,
      entries: [
        {
          ...valuedData.entries[0]!,
          kind: 'cost_adjustment',
          quantity_base: '0',
          cost_breakdown: [
            {
              event_id: 'issue-1',
              kind: 'issue',
              source_reference: 'VEN-0001',
              cost_delta: '12.000000'
            }
          ]
        },
        {
          ...valuedData.entries[0]!,
          id: 'issue-entry',
          kind: 'issue',
          quantity_base: '6',
          retaceo_id: null,
          cost_breakdown: []
        }
      ]
    };
    const { container } = render(ValuedKardexList, {
      props: { data, loading: false, onPageChange: vi.fn() }
    });

    const mobileList = findMobileList(container);
    expect(within(mobileList).getByText('Sin movimiento físico')).toBeInTheDocument();
    expect(within(mobileList).getByText('Salida 6')).toBeInTheDocument();
    expect(within(mobileList).getByText(/Efecto en salidas: USD 12\.00/)).toBeInTheDocument();
  });

  it('distingue crédito, costo retirado y diferencia y respeta el permiso del enlace', () => {
    const data: ValuedKardex = {
      ...valuedData,
      entries: [
        {
          ...valuedData.entries[0]!,
          kind: 'supplier_credit',
          quantity_base: '0',
          inventory_delta: '0',
          cost_breakdown: [
            {
              event_id: 'return-1',
              kind: 'supplier_credit',
              credit_net: '100.000000',
              inventory_cost: '75.000000',
              cost_difference: '25.000000'
            }
          ]
        }
      ]
    };
    const { container } = render(ValuedKardexList, {
      props: { data, loading: false, onPageChange: vi.fn() }
    });

    const mobileList = findMobileList(container);
    expect(within(mobileList).getByText('Sin movimiento físico')).toBeInTheDocument();
    expect(within(mobileList).queryByRole('link', { name: 'Ver retaceo aplicado' })).toBeNull();
    expect(within(mobileList).getByText(/Crédito del proveedor: USD 100\.00/)).toBeInTheDocument();
    expect(within(mobileList).getByText(/costo retirado: USD 75\.00/)).toBeInTheDocument();
    expect(within(mobileList).getByText(/diferencia: USD 25\.00/)).toBeInTheDocument();
  });
});
