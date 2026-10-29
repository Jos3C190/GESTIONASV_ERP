import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ValuationOpening from '$lib/features/inventory/components/ValuationOpening.svelte';
import { valuationApi, type ValuationOverview } from '$lib/features/inventory/valuation';

vi.mock('$lib/api/client', () => ({ apiFetch: vi.fn() }));

const empty: ValuationOverview = {
  setting: null,
  snapshot_fingerprint: 'approved-snapshot',
  physical_stock: [],
  items: [],
  balances: []
};

describe('valuation opening approval', () => {
  beforeEach(() => vi.restoreAllMocks());

  it('explains invalid currency and document and prevents approval', async () => {
    const open = vi.spyOn(valuationApi, 'open');
    render(ValuationOpening, { data: empty, onapproved: vi.fn(), onrefresh: vi.fn() });
    await fireEvent.input(screen.getByLabelText(/Moneda/), { target: { value: 'US' } });
    await fireEvent.input(screen.getByLabelText(/Documento de corte/), { target: { value: 'AB' } });
    await fireEvent.click(screen.getByRole('checkbox'));
    expect(screen.getByText(/tres letras de una moneda/)).toBeInTheDocument();
    expect(screen.getByText(/Identifica el documento/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Aprobar saldo inicial' })).toBeDisabled();
    await fireEvent.submit(screen.getByRole('form'));
    expect(open).not.toHaveBeenCalled();
  });

  it('requires fresh confirmation after refreshing the count', async () => {
    let resolve!: (data: ValuationOverview) => void;
    vi.spyOn(valuationApi, 'overview').mockImplementation(
      () =>
        new Promise((done) => {
          resolve = done;
        })
    );
    const onrefresh = vi.fn();
    render(ValuationOpening, { data: empty, onapproved: vi.fn(), onrefresh });
    const checkbox = screen.getByRole('checkbox');
    await fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();
    await fireEvent.click(screen.getByRole('button', { name: 'Actualizar conteo' }));
    expect(checkbox).toBeDisabled();
    expect(checkbox).not.toBeChecked();
    resolve(empty);
    await waitFor(() => expect(onrefresh).toHaveBeenCalledWith(empty));
    expect(checkbox).toBeEnabled();
    expect(checkbox).not.toBeChecked();
  });

  it('submits the documented zero opening only with explicit approval', async () => {
    const open = vi.spyOn(valuationApi, 'open').mockResolvedValue({
      company_id: 'company',
      currency: 'USD',
      opened_at: '2026-10-13',
      opened_by: 'actor',
      opening_reference: 'Acta 001'
    });
    const onapproved = vi.fn().mockResolvedValue(undefined);
    render(ValuationOpening, { data: empty, onapproved, onrefresh: vi.fn() });
    await fireEvent.input(screen.getByLabelText(/Documento de corte/), {
      target: { value: 'Acta 001' }
    });
    await fireEvent.click(screen.getByRole('checkbox'));
    await fireEvent.click(screen.getByRole('button', { name: 'Aprobar saldo inicial' }));
    await waitFor(() => expect(onapproved).toHaveBeenCalledOnce());
    expect(open).toHaveBeenCalledWith({
      currency: 'USD',
      reference: 'Acta 001',
      snapshot_fingerprint: empty.snapshot_fingerprint,
      approved: true,
      lines: []
    });
  });
});
