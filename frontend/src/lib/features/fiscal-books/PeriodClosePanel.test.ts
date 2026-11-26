import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';

const { fiscalBooksApi } = vi.hoisted(() => ({
  fiscalBooksApi: { periodStatus: vi.fn(), closePeriod: vi.fn(), reopenPeriod: vi.fn() }
}));
vi.mock('#lib/api/fiscal-books.ts', () => ({ fiscalBooksApi }));

import { permissions } from '#lib/stores/permissions.svelte.ts';
import type { PeriodStatus } from '#lib/types/fiscal-books.ts';
import PeriodClosePanel from './PeriodClosePanel.svelte';

const OPEN: PeriodStatus = {
  period: '2026-10',
  label: 'octubre de 2026',
  closed: null,
  history: [],
  blockers: []
};
const CLOSE = {
  id: 'close-1',
  status: 'closed' as const,
  summary: { balance: '10.00' },
  closed_by: 'Ana Pérez',
  closed_at: '2026-11-10T16:00:00Z',
  reopen_reason: null,
  reopened_by: null,
  reopened_at: null
};

beforeEach(() => {
  for (const fn of Object.values(fiscalBooksApi)) fn.mockReset();
  permissions.set(['fiscal_books:read', 'fiscal_periods:manage'], false);
});

it('cierra el mes después de confirmar', async () => {
  fiscalBooksApi.periodStatus.mockResolvedValue(OPEN);
  fiscalBooksApi.closePeriod.mockResolvedValue({ ...OPEN, closed: CLOSE, history: [CLOSE] });
  render(PeriodClosePanel, { period: '2026-10' });

  await fireEvent.click(await screen.findByRole('button', { name: 'Cerrar período' }));
  expect(fiscalBooksApi.closePeriod).not.toHaveBeenCalled();
  await fireEvent.click(screen.getByRole('button', { name: 'Confirmar cierre' }));
  expect(fiscalBooksApi.closePeriod).toHaveBeenCalledWith('2026-10');
  expect(await screen.findByText('Se cerró octubre de 2026.')).toBeInTheDocument();
  expect(screen.getByText('Cerrado')).toBeInTheDocument();
  expect(screen.getByText(/por Ana Pérez/)).toBeInTheDocument();
});

it('muestra lo que impide cerrar y deshabilita el cierre', async () => {
  fiscalBooksApi.periodStatus.mockResolvedValue({
    ...OPEN,
    blockers: [
      '2 documento(s) del mes siguen sin sello de Hacienda (pendientes o en contingencia).'
    ]
  });
  render(PeriodClosePanel, { period: '2026-10' });
  expect(await screen.findByText(/siguen sin sello/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Cerrar período' })).toBeDisabled();
});

it('reabre con motivo de al menos 10 caracteres', async () => {
  fiscalBooksApi.periodStatus.mockResolvedValue({ ...OPEN, closed: CLOSE, history: [CLOSE] });
  fiscalBooksApi.reopenPeriod.mockResolvedValue({
    ...OPEN,
    history: [
      {
        ...CLOSE,
        status: 'reopened',
        reopen_reason: 'Cobro registrado tarde',
        reopened_by: 'Ana Pérez',
        reopened_at: '2026-11-12T16:00:00Z'
      }
    ]
  });
  render(PeriodClosePanel, { period: '2026-10' });

  await fireEvent.click(await screen.findByRole('button', { name: 'Reabrir período' }));
  const confirm = screen.getByRole('button', { name: 'Reabrir' });
  expect(confirm).toBeDisabled();
  await fireEvent.input(screen.getByLabelText('Motivo de la reapertura'), {
    target: { value: 'Cobro registrado tarde' }
  });
  await fireEvent.click(confirm);
  expect(fiscalBooksApi.reopenPeriod).toHaveBeenCalledWith('2026-10', 'Cobro registrado tarde');
  expect(await screen.findByText('Se reabrió octubre de 2026.')).toBeInTheDocument();
  expect(screen.getByText('Historial de cierres')).toBeInTheDocument();
});

it('sin permiso solo muestra el estado', async () => {
  permissions.set(['fiscal_books:read'], false);
  fiscalBooksApi.periodStatus.mockResolvedValue({ ...OPEN, closed: CLOSE, history: [CLOSE] });
  render(PeriodClosePanel, { period: '2026-10' });
  expect(await screen.findByText('Cerrado')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Reabrir período' })).not.toBeInTheDocument();
});
