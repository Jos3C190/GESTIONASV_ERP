import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';

const { salesReceivablesApi } = vi.hoisted(() => ({
  salesReceivablesApi: {
    credit: vi.fn(),
    addNote: vi.fn(),
    block: vi.fn(),
    unblock: vi.fn(),
    statementPdf: vi.fn(),
    sendStatement: vi.fn()
  }
}));
vi.mock('#lib/api/sales-receivables.ts', () => ({ salesReceivablesApi }));

import type { CreditStatus } from '#lib/types/sales-receivables.ts';
import CreditPanel from './CreditPanel.svelte';

function status(overrides: Partial<CreditStatus> = {}): CreditStatus {
  return {
    customer: {
      id: 'cust-1',
      code: 'CLI-1',
      name: 'Cafetería El Trigal',
      credit_days: 15,
      credit_limit: '500.00',
      email: 'compras@eltrigal.example',
      credit_blocked: false,
      credit_block_reason: null,
      credit_blocked_at: null
    },
    credit_limit: '500.00',
    open_balance: '427.18',
    pending_orders: '100.00',
    available: '-27.18',
    overdue_beyond_grace: '0.00',
    grace_days: 5,
    notes: [],
    ...overrides
  };
}

beforeEach(() => {
  for (const fn of Object.values(salesReceivablesApi)) fn.mockReset();
});

it('muestra el cupo agotado, agrega una nota y bloquea con motivo', async () => {
  salesReceivablesApi.credit.mockResolvedValue(status());
  salesReceivablesApi.addNote.mockResolvedValue(
    status({
      notes: [
        {
          id: 'n-1',
          note: 'Prometió pagar el viernes',
          next_action_on: null,
          created_by: 'cobros',
          created_at: '2026-11-25T16:00:00Z'
        }
      ]
    })
  );
  salesReceivablesApi.block.mockResolvedValue(
    status({
      customer: {
        ...status().customer,
        credit_blocked: true,
        credit_block_reason: 'Cheque rechazado',
        credit_blocked_at: '2026-11-25T16:00:00Z'
      }
    })
  );
  render(CreditPanel, { customerId: 'cust-1', canCollect: true, canControlCredit: true });

  expect(await screen.findByText('-$27.18')).toBeInTheDocument();
  expect(screen.getByText(/más de 5 días/)).toBeInTheDocument();
  await fireEvent.input(screen.getByLabelText('Nota de cobro'), {
    target: { value: 'Prometió pagar el viernes' }
  });
  await fireEvent.click(screen.getByRole('button', { name: 'Agregar nota' }));
  expect(salesReceivablesApi.addNote).toHaveBeenCalledWith(
    'cust-1',
    'Prometió pagar el viernes',
    null
  );
  expect(await screen.findByText('Prometió pagar el viernes')).toBeInTheDocument();

  await fireEvent.click(screen.getByRole('button', { name: 'Bloquear crédito' }));
  await fireEvent.input(screen.getByLabelText('Motivo del bloqueo'), {
    target: { value: 'Cheque rechazado' }
  });
  await fireEvent.click(screen.getByRole('button', { name: 'Bloquear' }));
  expect(salesReceivablesApi.block).toHaveBeenCalledWith('cust-1', 'Cheque rechazado');
  expect(await screen.findByText(/Crédito bloqueado/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Desbloquear crédito' })).toBeInTheDocument();
});

it('envía el estado de cuenta al correo del cliente', async () => {
  salesReceivablesApi.credit.mockResolvedValue(status());
  salesReceivablesApi.sendStatement.mockResolvedValue({ sent_to: 'compras@eltrigal.example' });
  render(CreditPanel, { customerId: 'cust-1', canCollect: true, canControlCredit: false });

  await fireEvent.click(await screen.findByRole('button', { name: 'Enviar por correo' }));
  expect(screen.getByLabelText('Correo del cliente')).toHaveValue('compras@eltrigal.example');
  await fireEvent.click(screen.getByRole('button', { name: 'Enviar' }));
  expect(salesReceivablesApi.sendStatement).toHaveBeenCalledWith(
    'cust-1',
    'compras@eltrigal.example'
  );
  expect(await screen.findByText(/Se envió el estado de cuenta/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Bloquear crédito' })).not.toBeInTheDocument();
});
