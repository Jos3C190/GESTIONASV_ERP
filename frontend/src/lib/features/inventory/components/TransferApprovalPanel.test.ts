import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeTransfer } from '../../../../../tests/unit/fixtures/inventory-transfer';
import type { InventoryTransfer } from '../transfer-documents';
import TransferApprovalPanel from './TransferApprovalPanel.svelte';

afterEach(cleanup);

const pending = (patch: Partial<InventoryTransfer> = {}) =>
  makeTransfer({
    route_type: 'branch_to_branch',
    origin_is_central: false,
    origin_branch_name: 'Sucursal Norte',
    status: 'pending_approval',
    requires_approval: true,
    approval_round: 3,
    created_by_id: 'user-author',
    submitted_by_id: 'user-author',
    submitted_by_name: 'Ana Autora',
    submitted_at: '2026-10-20T12:00:00Z',
    ...patch
  });

function mount(
  transfer: InventoryTransfer,
  props: Partial<{
    canMove: boolean;
    canApprove: boolean;
    currentUserId: string | null;
    isSuperuser: boolean;
    canAccessOrigin: boolean;
    routeEnabled: boolean;
    busy: boolean;
  }> = {}
) {
  const handlers = {
    onSubmit: vi.fn(),
    onWithdraw: vi.fn(),
    onApprove: vi.fn(),
    onReject: vi.fn()
  };
  render(TransferApprovalPanel, {
    transfer,
    canMove: true,
    canApprove: false,
    currentUserId: 'user-other',
    formatDate: (value: string | null | undefined) => (value ? '20 oct 2026' : 'Sin fecha'),
    ...props,
    ...handlers
  });
  return handlers;
}

describe('TransferApprovalPanel', () => {
  it('pide enviar a aprobación una preparación que lo necesita', async () => {
    const handlers = mount(
      makeTransfer({
        route_type: 'branch_to_central',
        origin_is_central: false,
        origin_branch_name: 'Sucursal Norte',
        requires_approval: true
      })
    );
    expect(
      screen.getByText(
        'Este traslado sale de Sucursal Norte y necesita aprobación antes de despacharse.'
      )
    ).toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: 'Enviar a aprobación' }));
    expect(handlers.onSubmit).toHaveBeenCalledTimes(1);
  });

  it('no deja enviar sin permiso de movimiento ni con la ruta apagada', () => {
    mount(makeTransfer({ route_type: 'branch_to_central', requires_approval: true }), {
      canMove: false
    });
    expect(screen.getByRole('button', { name: 'Enviar a aprobación' })).toBeDisabled();
    cleanup();
    mount(makeTransfer({ route_type: 'branch_to_central', requires_approval: true }), {
      routeEnabled: false
    });
    expect(screen.getByRole('button', { name: 'Enviar a aprobación' })).toBeDisabled();
    expect(screen.getByText(/Esta ruta está desactivada/)).toBeInTheDocument();
  });

  it('con la ruta apagada solo muestra el aviso de ruta desactivada, no el de aprobación', () => {
    mount(makeTransfer({ route_type: 'branch_to_central', requires_approval: true }), {
      routeEnabled: false
    });
    expect(screen.getByText(/Esta ruta está desactivada/)).toBeInTheDocument();
    expect(screen.queryByText(/necesita aprobación antes de despacharse/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Enviar a aprobación' })).toHaveAttribute(
      'aria-describedby',
      'transfer-route-disabled-note'
    );
  });

  it('no duplica la puntuación final del motivo de rechazo', () => {
    mount(
      makeTransfer({
        route_type: 'branch_to_branch',
        requires_approval: true,
        rejected_by_name: 'Luis Jefe',
        rejected_at: '2026-10-21T09:00:00Z',
        rejection_reason: 'Falta el sello del encargado.  '
      })
    );
    expect(
      screen.getByText(
        'Rechazado por Luis Jefe el 20 oct 2026: Falta el sello del encargado. Corrige la preparación y vuelve a enviarla.'
      )
    ).toBeInTheDocument();
  });

  it('muestra quién rechazó, cuándo y por qué', () => {
    mount(
      makeTransfer({
        route_type: 'branch_to_branch',
        requires_approval: true,
        rejected_by_name: 'Luis Jefe',
        rejected_at: '2026-10-21T09:00:00Z',
        rejection_reason: 'Falta el sello del encargado'
      })
    );
    expect(
      screen.getByText(
        'Rechazado por Luis Jefe el 20 oct 2026: Falta el sello del encargado. Corrige la preparación y vuelve a enviarla.'
      )
    ).toBeInTheDocument();
  });

  it('a quien no decide le muestra el envío y le ofrece retirar la solicitud', async () => {
    const handlers = mount(pending());
    expect(
      screen.getByText('Enviado por Ana Autora el 20 oct 2026. Esperando aprobación.')
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Aprobar traslado' })).not.toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: 'Retirar solicitud' }));
    expect(handlers.onWithdraw).toHaveBeenCalledTimes(1);
  });

  it('a un aprobador independiente le ofrece aprobar y rechazar', async () => {
    const handlers = mount(pending(), { canApprove: true });
    expect(screen.queryByRole('button', { name: 'Retirar solicitud' })).not.toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: 'Aprobar traslado' }));
    expect(handlers.onApprove).toHaveBeenCalledTimes(1);
  });

  it('explica por qué un aprobador no puede aprobar lo que él mismo preparó o envió', () => {
    mount(pending(), { canApprove: true, currentUserId: 'user-author' });
    expect(
      screen.getByText('No puedes aprobar un traslado que tú preparaste, editaste o enviaste.')
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Aprobar traslado' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Rechazar' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retirar solicitud' })).toBeInTheDocument();
    cleanup();
    // Quien solo envió, sin haberlo creado, tampoco decide.
    mount(pending({ created_by_id: 'user-creator', submitted_by_id: 'user-sender' }), {
      canApprove: true,
      currentUserId: 'user-sender'
    });
    expect(screen.queryByRole('button', { name: 'Aprobar traslado' })).not.toBeInTheDocument();
  });

  it('quien editó la preparación tampoco decide sobre ella', () => {
    mount(pending({ last_edited_by_id: 'user-editor' }), {
      canApprove: true,
      currentUserId: 'user-editor'
    });
    expect(
      screen.getByText('No puedes aprobar un traslado que tú preparaste, editaste o enviaste.')
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Aprobar traslado' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Rechazar' })).not.toBeInTheDocument();
    cleanup();
    mount(pending({ last_edited_by_id: 'user-editor' }), {
      canApprove: true,
      currentUserId: 'user-editor',
      isSuperuser: true
    });
    expect(screen.getByRole('button', { name: 'Aprobar traslado' })).toBeEnabled();
  });

  it('sin acceso a la sucursal de origen no ofrece decidir y lo explica', () => {
    mount(pending(), { canApprove: true, canAccessOrigin: false });
    expect(
      screen.getByText('No tienes acceso a la sucursal de origen para decidir este traslado.')
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Aprobar traslado' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Rechazar' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retirar solicitud' })).toBeInTheDocument();
  });

  it('el superusuario puede decidir sobre lo suyo', () => {
    mount(pending(), { canApprove: true, currentUserId: 'user-author', isSuperuser: true });
    expect(screen.getByRole('button', { name: 'Aprobar traslado' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Rechazar' })).toBeEnabled();
  });

  it('el superusuario que envió el traslado también puede retirar su solicitud', async () => {
    const handlers = mount(pending(), {
      canApprove: true,
      currentUserId: 'user-author',
      isSuperuser: true
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Retirar solicitud' }));
    expect(handlers.onWithdraw).toHaveBeenCalledTimes(1);
    cleanup();
    // Un aprobador que no lo envió no ve retirar.
    mount(pending(), { canApprove: true, currentUserId: 'user-other', isSuperuser: true });
    expect(screen.queryByRole('button', { name: 'Retirar solicitud' })).not.toBeInTheDocument();
  });

  it('con la ruta apagada deja rechazar pero no aprobar', () => {
    mount(pending(), { canApprove: true, routeEnabled: false });
    expect(screen.getByRole('button', { name: 'Aprobar traslado' })).toBeDisabled();
    const note = document.getElementById('transfer-route-disabled-note');
    expect(note).toHaveTextContent(/no se puede aprobar/);
    expect(screen.getByRole('button', { name: 'Aprobar traslado' })).toHaveAttribute(
      'aria-describedby',
      'transfer-route-disabled-note'
    );
    expect(screen.getByRole('button', { name: 'Rechazar' })).toBeEnabled();
    expect(screen.getByText(/no se puede aprobar/)).toBeInTheDocument();
  });

  it('exige un motivo de al menos cinco caracteres para rechazar y conserva el foco', async () => {
    const handlers = mount(pending(), { canApprove: true });
    await fireEvent.click(screen.getByRole('button', { name: 'Rechazar' }));

    const reason = await screen.findByLabelText('Motivo del rechazo');
    expect(reason).toHaveFocus();

    await fireEvent.input(reason, { target: { value: '  no ' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar rechazo' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Indica el motivo del rechazo (mínimo 5 caracteres).'
    );
    expect(reason).toHaveAttribute('aria-invalid', 'true');
    expect(handlers.onReject).not.toHaveBeenCalled();

    await fireEvent.input(reason, { target: { value: '  Falta el sello  ' } });
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar rechazo' }));
    expect(handlers.onReject).toHaveBeenCalledWith('Falta el sello');
  });

  it('cierra el formulario de rechazo con Volver o Escape y devuelve el foco', async () => {
    mount(pending(), { canApprove: true });
    await fireEvent.click(screen.getByRole('button', { name: 'Rechazar' }));
    await fireEvent.click(await screen.findByRole('button', { name: 'Volver' }));
    expect(screen.queryByLabelText('Motivo del rechazo')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Rechazar' })).toHaveFocus();

    await fireEvent.click(screen.getByRole('button', { name: 'Rechazar' }));
    await fireEvent.keyDown(await screen.findByLabelText('Motivo del rechazo'), { key: 'Escape' });
    expect(screen.queryByLabelText('Motivo del rechazo')).not.toBeInTheDocument();
  });

  it('confirma quién aprobó y cuándo', () => {
    mount(
      makeTransfer({
        route_type: 'branch_to_branch',
        requires_approval: true,
        status: 'approved',
        approved_by_name: 'Luis Jefe',
        approved_at: '2026-10-21T09:00:00Z'
      })
    );
    expect(screen.getByText('Aprobado por Luis Jefe el 20 oct 2026.')).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});
