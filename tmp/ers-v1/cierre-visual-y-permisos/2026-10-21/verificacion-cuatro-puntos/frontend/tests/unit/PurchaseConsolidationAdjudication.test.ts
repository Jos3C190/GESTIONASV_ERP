import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseConsolidationAdjudication from '$lib/features/purchase-requests/components/PurchaseConsolidationAdjudication.svelte';
import type { PurchaseConsolidationAwardBoard } from '$lib/types/purchase-consolidation';

const mocks = vi.hoisted(() => ({
  getAwardBoard: vi.fn(),
  award: vi.fn(),
  revokeAward: vi.fn(),
  getSupplier: vi.fn(),
  getUser: vi.fn(),
  getCurrentUser: vi.fn(),
  hasPermission: vi.fn()
}));

vi.mock('$lib/api/purchase-consolidations', () => ({
  purchaseConsolidationsApi: {
    getAwardBoard: mocks.getAwardBoard,
    award: mocks.award,
    revokeAward: mocks.revokeAward
  }
}));
vi.mock('$lib/api/suppliers', () => ({
  suppliersApi: { getSupplier: mocks.getSupplier }
}));
vi.mock('$lib/api/client', () => ({
  HttpError: class HttpError extends Error {},
  api: {
    auth: { me: mocks.getCurrentUser },
    users: { get: mocks.getUser }
  }
}));
vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: { hasPermission: mocks.hasPermission }
}));

const board: PurchaseConsolidationAwardBoard = {
  consolidation_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  consolidation_code: 'CD-00002',
  currencies: ['EUR', 'USD'],
  lines: [
    {
      id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
      product_id: 10,
      product_sku: 'PRD-10',
      product_name: 'Harina de prueba',
      unit_id: 1,
      unit_name: 'Kilogramo',
      demand_quantity: '10.000000',
      awarded_quantity: '0.000000',
      remaining_quantity: '10.000000',
      offers: [
        {
          quotation_id: 'cccccccc-cccc-cccc-cccc-cccccccccccc',
          quotation_code: 'COT-00025',
          quotation_version: 1,
          supplier_id: 25,
          quotation_status: 'under_evaluation',
          currency: 'USD',
          valid_until: '2026-10-23',
          delivery_days: 16,
          payment_terms: '30 días crédito',
          quotation_total: '45.2',
          quotation_expenses_total: '2.5',
          quotation_detail_id: 'dddddddd-dddd-dddd-dddd-dddddddddddd',
          requested_quantity: '10.000000',
          offered_quantity: '5.000000',
          available_quantity: '4.000000',
          awarded_quantity: '0.000000',
          remaining_offer_quantity: '4.000000',
          unit_price: '4.000000',
          discount: '1.000000',
          subtotal: '40.000000',
          tax_rate: '13.000000',
          tax_amount: '5.200000',
          line_total: '45.200000',
          line_delivery_days: 8,
          notes: 'Precio promocional',
          can_award: true,
          blocked_reason: null
        }
      ],
      decisions: []
    }
  ]
};

describe('PurchaseConsolidationAdjudication', () => {
  beforeEach(() => {
    mocks.getAwardBoard.mockReset().mockResolvedValue(board);
    mocks.award.mockReset();
    mocks.revokeAward.mockReset();
    mocks.getSupplier.mockReset().mockResolvedValue({ name: 'Proveedor de harina' });
    mocks.getUser.mockReset().mockResolvedValue({ username: 'compras' });
    mocks.getCurrentUser.mockReset().mockResolvedValue({
      id: 'ffffffff-ffff-ffff-ffff-ffffffffffff',
      username: 'superadmin'
    });
    mocks.hasPermission
      .mockReset()
      .mockImplementation(
        (code: string) =>
          code === 'purchase_requests:read' ||
          code === 'purchase_quotations:read' ||
          code === 'purchase_quotations:select' ||
          code === 'purchase_orders:manage'
      );
  });

  it('presents the comparison in original currencies and discloses unallocated RFQ costs', async () => {
    render(PurchaseConsolidationAdjudication, {
      props: { consolidationId: board.consolidation_id, status: 'frozen' }
    });

    expect(
      await screen.findByRole('heading', { name: 'Comparar y adjudicar por producto' })
    ).toBeInTheDocument();
    expect(await screen.findByText('Proveedor de harina')).toBeInTheDocument();
    expect(screen.getByText(/23 oct 2026/)).toBeInTheDocument();
    expect(
      screen.getByText(/no hace conversión ni ordena proveedores automáticamente/)
    ).toBeInTheDocument();
    expect(screen.getByText(/No están asignados a este producto/)).toBeInTheDocument();
    expect(screen.getAllByText('4 Kilogramo').length).toBeGreaterThan(0);
    expect(mocks.getAwardBoard).toHaveBeenCalledWith(board.consolidation_id);
  });

  it('sends a human-reviewed partial quantity and reason to the award endpoint', async () => {
    const afterAward: PurchaseConsolidationAwardBoard = {
      ...board,
      lines: [
        {
          ...board.lines[0]!,
          awarded_quantity: '2.500000',
          remaining_quantity: '7.500000',
          offers: [
            {
              ...board.lines[0]!.offers[0]!,
              awarded_quantity: '2.500000',
              remaining_offer_quantity: '1.500000'
            }
          ]
        }
      ]
    };
    mocks.award.mockResolvedValue(afterAward);
    render(PurchaseConsolidationAdjudication, {
      props: { consolidationId: board.consolidation_id, status: 'frozen' }
    });

    const quantity = await screen.findByLabelText(
      'Cantidad a adjudicar de Harina de prueba a Proveedor de harina'
    );
    await fireEvent.input(quantity, { target: { value: '2.5' } });
    await fireEvent.input(
      screen.getByLabelText('Motivo de adjudicación de Harina de prueba a Proveedor de harina'),
      {
        target: { value: 'Entrega confirmada y precio revisado' }
      }
    );
    await fireEvent.click(screen.getByRole('button', { name: 'Adjudicar cantidad' }));

    await waitFor(() =>
      expect(mocks.award).toHaveBeenCalledWith(board.consolidation_id, {
        consolidation_line_id: board.lines[0]!.id,
        quotation_id: board.lines[0]!.offers[0]!.quotation_id,
        quotation_detail_id: board.lines[0]!.offers[0]!.quotation_detail_id,
        quantity: '2.5',
        reason: 'Entrega confirmada y precio revisado'
      })
    );
    expect(await screen.findByRole('status')).toHaveTextContent(/Adjudicación registrada/);
    expect(await screen.findByText('7.5 Kilogramo')).toBeInTheDocument();
  });

  it('offers a purchase-order draft for active awarded quantities that are not ordered yet', async () => {
    const decision = {
      id: 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
      quotation_id: board.lines[0]!.offers[0]!.quotation_id,
      quotation_code: 'COT-00025',
      supplier_id: 25,
      quantity: '2.000000',
      reason: 'Entrega confirmada',
      decided_by_id: 'ffffffff-ffff-ffff-ffff-ffffffffffff',
      created_at: '2026-10-05T12:00:00Z',
      revoked_at: null,
      revoked_by_id: null,
      revocation_reason: null,
      ordered_quantity: '1.000000',
      remaining_to_order_quantity: '1.000000'
    };
    const secondDecision = {
      ...decision,
      id: '99999999-9999-9999-9999-999999999999',
      quotation_id: '88888888-8888-8888-8888-888888888888',
      quotation_code: 'COT-00026',
      quantity: '1.000000',
      remaining_to_order_quantity: '1.000000'
    };
    mocks.getAwardBoard.mockResolvedValue({
      ...board,
      lines: [
        {
          ...board.lines[0]!,
          awarded_quantity: '3.000000',
          remaining_quantity: '8.000000',
          decisions: [decision, secondDecision]
        }
      ]
    });
    render(PurchaseConsolidationAdjudication, {
      props: { consolidationId: board.consolidation_id, status: 'frozen' }
    });

    const link = await screen.findByRole('link', {
      name: /Crear orden · COT-00025 · Proveedor de harina/
    });
    expect(link).toHaveAttribute(
      'href',
      `/purchase-orders/new?quotation_id=${decision.quotation_id}&consolidation_id=${board.consolidation_id}`
    );
    const secondLink = screen.getByRole('link', {
      name: /Crear orden · COT-00026 · Proveedor de harina/
    });
    expect(secondLink).toHaveAttribute(
      'href',
      `/purchase-orders/new?quotation_id=${secondDecision.quotation_id}&consolidation_id=${board.consolidation_id}`
    );
    expect(screen.getAllByRole('link', { name: /Proveedor de harina/ })).toHaveLength(2);
  });

  it('reverses an award only after entering a reason', async () => {
    const activeDecision = {
      id: 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
      quotation_id: board.lines[0]!.offers[0]!.quotation_id,
      quotation_code: 'COT-00025',
      supplier_id: 25,
      quantity: '2.000000',
      reason: 'Elegida por plazo',
      decided_by_id: 'ffffffff-ffff-ffff-ffff-ffffffffffff',
      created_at: '2026-10-05T12:00:00Z',
      revoked_at: null,
      revoked_by_id: null,
      revocation_reason: null,
      ordered_quantity: '0.000000',
      remaining_to_order_quantity: '2.000000'
    };
    const withDecision = {
      ...board,
      lines: [
        {
          ...board.lines[0]!,
          awarded_quantity: '2',
          remaining_quantity: '8',
          decisions: [activeDecision]
        }
      ]
    };
    const afterRevoke = {
      ...withDecision,
      lines: [
        {
          ...withDecision.lines[0]!,
          awarded_quantity: '0',
          remaining_quantity: '10',
          decisions: [
            {
              ...activeDecision,
              revoked_at: '2026-10-05T13:00:00Z',
              revoked_by_id: 'ffffffff-ffff-ffff-ffff-ffffffffffff',
              revocation_reason: 'El proveedor no confirmó existencia'
            }
          ]
        }
      ]
    } satisfies PurchaseConsolidationAwardBoard;
    mocks.getAwardBoard.mockResolvedValue(withDecision);
    mocks.revokeAward.mockResolvedValue(afterRevoke);
    mocks.hasPermission.mockImplementation(
      (code: string) =>
        code === 'purchase_requests:read' ||
        code === 'purchase_quotations:read' ||
        code === 'purchase_quotations:select' ||
        code === 'users:read'
    );
    render(PurchaseConsolidationAdjudication, {
      props: { consolidationId: board.consolidation_id, status: 'frozen' }
    });

    await fireEvent.click(await screen.findByRole('button', { name: 'Revertir' }));
    expect(await screen.findByText(/Decidió superadmin · ID ffffffff/)).toBeInTheDocument();
    await fireEvent.input(
      screen.getByLabelText(
        'Motivo para revertir adjudicación de Harina de prueba a Proveedor de harina'
      ),
      {
        target: { value: 'El proveedor no confirmó existencia' }
      }
    );
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar' }));

    await waitFor(() =>
      expect(mocks.revokeAward).toHaveBeenCalledWith(
        board.consolidation_id,
        activeDecision.id,
        'El proveedor no confirmó existencia'
      )
    );
    expect(await screen.findByRole('status')).toHaveTextContent(/Se revirtió la adjudicación/);
  });

  it('explains when the current profile cannot read purchase quotations', async () => {
    mocks.hasPermission.mockReturnValue(false);
    render(PurchaseConsolidationAdjudication, {
      props: { consolidationId: board.consolidation_id, status: 'frozen' }
    });

    expect(
      await screen.findByText(/Tu perfil no tiene permiso para consultar/)
    ).toBeInTheDocument();
    expect(mocks.getAwardBoard).not.toHaveBeenCalled();
  });
});
