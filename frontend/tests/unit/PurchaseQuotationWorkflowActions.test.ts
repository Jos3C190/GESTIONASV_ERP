import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PurchaseQuotationWorkflowActions from '$lib/features/purchase-quotations/components/PurchaseQuotationWorkflowActions.svelte';
import type { PurchaseQuotation } from '$lib/types/purchase-quotation';

const mocks = vi.hoisted(() => ({
  send: vi.fn(),
  evaluate: vi.fn(),
  select: vi.fn(),
  reject: vi.fn(),
  cancel: vi.fn(),
  hasPermission: vi.fn()
}));

vi.mock('$lib/api/purchase-quotations', () => ({
  purchaseQuotationsApi: {
    send: mocks.send,
    evaluate: mocks.evaluate,
    select: mocks.select,
    reject: mocks.reject,
    cancel: mocks.cancel
  }
}));

vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: {
    hasPermission: mocks.hasPermission
  }
}));

const baseQuotation: PurchaseQuotation = {
  id: '11111111-1111-1111-1111-111111111111',
  company_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  code: 'CQ-0001',
  supplier_id: 25,
  quotation_date: '2026-09-13T12:00:00-06:00',
  currency: 'USD',
  created_by_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  request_links: [],
  details: [],
  expenses: [],
  valid_until: null,
  payment_terms: null,
  delivery_days: null,
  subtotal: '0.000000',
  discount: '0.000000',
  tax: '0.000000',
  total: '0.000000',
  status: 'draft',
  notes: null,
  created_at: null,
  updated_at: null
};

describe('PurchaseQuotationWorkflowActions', () => {
  beforeEach(() => {
    mocks.send.mockReset();
    mocks.evaluate.mockReset();
    mocks.select.mockReset();
    mocks.reject.mockReset();
    mocks.cancel.mockReset();
    mocks.hasPermission.mockReset();
    mocks.hasPermission.mockImplementation(
      (code: string) =>
        code === 'purchase_quotations:manage' || code === 'purchase_quotations:select'
    );
  });

  it('sends a draft and returns the updated quotation to the detail', async () => {
    const updated = { ...baseQuotation, status: 'requested' } as const;
    const onupdated = vi.fn();
    mocks.send.mockResolvedValue(updated);

    render(PurchaseQuotationWorkflowActions, {
      props: {
        quotation: baseQuotation,
        onupdated
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Enviar al proveedor' }));

    expect(mocks.send).toHaveBeenCalledWith(baseQuotation.id);
    expect(onupdated).toHaveBeenCalledWith(updated);
  });

  it('shows response capture and cancellation for requested quotations', () => {
    render(PurchaseQuotationWorkflowActions, {
      props: {
        quotation: { ...baseQuotation, status: 'requested' },
        onupdated: vi.fn()
      }
    });

    expect(screen.getByRole('link', { name: 'Registrar respuesta' })).toHaveAttribute(
      'href',
      `/purchase-quotations/${baseQuotation.id}/response`
    );
    expect(screen.getByRole('button', { name: 'Cancelar cotización' })).toBeInTheDocument();
  });

  it('separates selection permission from manage permission', () => {
    mocks.hasPermission.mockImplementation((code: string) => code === 'purchase_quotations:select');

    render(PurchaseQuotationWorkflowActions, {
      props: {
        quotation: { ...baseQuotation, status: 'under_evaluation' },
        onupdated: vi.fn()
      }
    });

    expect(screen.getByRole('button', { name: 'Seleccionar oferta' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Rechazar oferta' })).not.toBeInTheDocument();
  });

  it('surfaces transition errors without changing the quotation', async () => {
    const onupdated = vi.fn();
    mocks.cancel.mockRejectedValue(new Error('Transición no permitida'));

    render(PurchaseQuotationWorkflowActions, {
      props: {
        quotation: baseQuotation,
        onupdated
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Cancelar cotización' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Transición no permitida');
    expect(onupdated).not.toHaveBeenCalled();
  });
});
