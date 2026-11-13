import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { makeTransfer } from '../../../../../tests/unit/fixtures/inventory-transfer';
import type { AssignmentCheck, InventoryTransfer } from '../transfer-documents';

const apiMock = vi.hoisted(() => ({ transferAssignmentCheck: vi.fn() }));
vi.mock('$lib/features/inventory/transfer-documents', () => ({ inventoryTransfersApi: apiMock }));

import TransferApprovalPanel from './TransferApprovalPanel.svelte';

const transport = {
  vehicle: { id: 'iv1', code: 'FL-001', name: 'Hiace', status: 'active', plate: 'C 123' },
  driver: { id: 'd1', name: 'Carlos Martínez', employee_code: 'EMP-1' }
} satisfies Partial<InventoryTransfer>;

function fit(patch: Partial<AssignmentCheck> = {}): AssignmentCheck {
  return {
    vehicle_id: 'iv1',
    driver_id: 'd1',
    vehicle_issues: [],
    driver_issues: [],
    planning_blocked: false,
    warnings: 0,
    conflicts: [],
    load_kg: null,
    load_missing_weight: 0,
    ...patch
  };
}

beforeEach(() => {
  apiMock.transferAssignmentCheck.mockResolvedValue(fit());
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const pending = (patch: Partial<InventoryTransfer> = {}) =>
  makeTransfer({
    ...transport,
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
        ...transport,
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
    mount(makeTransfer({ ...transport, route_type: 'branch_to_central', requires_approval: true }), {
      canMove: false
    });
    expect(screen.getByRole('button', { name: 'Enviar a aprobación' })).toBeDisabled();
    cleanup();
    mount(makeTransfer({ ...transport, route_type: 'branch_to_central', requires_approval: true }), {
      routeEnabled: false
    });
    expect(screen.getByRole('button', { name: 'Enviar a aprobación' })).toBeDisabled();
    expect(screen.getByText(/Esta ruta está desactivada/)).toBeInTheDocument();
  });

  it('con la ruta apagada solo muestra el aviso de ruta desactivada, no el de aprobación', () => {
    mount(makeTransfer({ ...transport, route_type: 'branch_to_central', requires_approval: true }), {
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

  describe('transporte asignado', () => {
    it('muestra el vehículo, el conductor y su aptitud en vivo', async () => {
      mount(pending());
      expect(screen.getByRole('heading', { name: 'Transporte asignado' })).toBeInTheDocument();
      expect(screen.getByText(/FL-001 · C 123/)).toBeInTheDocument();
      expect(screen.getByText(/Carlos Martínez/)).toBeInTheDocument();
      expect(await screen.findByText('Apto')).toBeInTheDocument();
      expect(apiMock.transferAssignmentCheck).toHaveBeenCalledWith('transfer-a');
    });

    it('lista advertencias y los conflictos de planificación', async () => {
      apiMock.transferAssignmentCheck.mockResolvedValue(
        fit({
          warnings: 1,
          vehicle_issues: [
            {
              code: 'inspection_required',
              severity: 'warning',
              message: 'Al despachar: requiere inspección.',
              overridable: false
            }
          ],
          conflicts: [
            {
              transfer_id: 'other',
              code: 'TR-9',
              status: 'approved',
              same_vehicle: true,
              same_driver: false,
              message: 'También está asignado a TR-9 (aprobado).'
            }
          ]
        })
      );
      mount(pending(), { canApprove: true });
      expect(await screen.findByText('Con advertencias')).toBeInTheDocument();
      expect(screen.getByText('Al despachar: requiere inspección.')).toBeInTheDocument();
      expect(screen.getByText('También está asignado a TR-9 (aprobado).')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Aprobar traslado' })).toBeEnabled();
    });

    it('deshabilita aprobar cuando el transporte no es apto y lo explica', async () => {
      apiMock.transferAssignmentCheck.mockResolvedValue(
        fit({
          planning_blocked: true,
          vehicle_issues: [
            {
              code: 'vehicle_not_active',
              severity: 'blocking',
              message: 'El vehículo no está activo.',
              overridable: false
            }
          ]
        })
      );
      mount(pending(), { canApprove: true });
      expect(await screen.findByText('No apto')).toBeInTheDocument();
      expect(screen.getByText('El vehículo no está activo.')).toBeInTheDocument();
      const approve = screen.getByRole('button', { name: 'Aprobar traslado' });
      expect(approve).toBeDisabled();
      expect(approve).toHaveAttribute('aria-describedby', 'transfer-decision-note');
      expect(document.getElementById('transfer-decision-note')).toHaveTextContent(
        /no sea apto/
      );
      // Rejecting stays possible so the author can fix it.
      expect(screen.getByRole('button', { name: 'Rechazar' })).toBeEnabled();
    });

    it('sin vehículo o sin conductor no deja enviar ni aprobar y explica por qué', () => {
      mount(
        makeTransfer({
          route_type: 'branch_to_branch',
          requires_approval: true,
          vehicle: transport.vehicle,
          driver: null
        })
      );
      const send = screen.getByRole('button', { name: 'Enviar a aprobación' });
      expect(send).toBeDisabled();
      expect(send).toHaveAttribute('aria-describedby', 'transfer-transport-note');
      expect(document.getElementById('transfer-transport-note')).toHaveTextContent(
        'Elige vehículo y conductor antes de enviar el traslado a aprobación.'
      );
      expect(screen.getAllByText('Sin asignar')).toHaveLength(1);
      expect(apiMock.transferAssignmentCheck).not.toHaveBeenCalled();
      cleanup();
      mount(pending({ vehicle: null, driver: null }), { canApprove: true });
      expect(screen.getByRole('button', { name: 'Aprobar traslado' })).toBeDisabled();
      expect(screen.getAllByText('Sin asignar')).toHaveLength(2);
    });

    it('deshabilita enviar cuando la revisión del transporte lo bloquea', async () => {
      apiMock.transferAssignmentCheck.mockResolvedValue(fit({ planning_blocked: true }));
      mount(
        makeTransfer({ ...transport, route_type: 'branch_to_branch', requires_approval: true })
      );
      await waitFor(() =>
        expect(screen.getByRole('button', { name: 'Enviar a aprobación' })).toBeDisabled()
      );
      expect(document.getElementById('transfer-transport-note')).toHaveTextContent(
        /no es apto para planificar/
      );
    });

    it('si no se puede revisar el transporte, no impide decidir: el servidor lo valida', async () => {
      apiMock.transferAssignmentCheck.mockRejectedValue(new Error('sin red'));
      mount(pending(), { canApprove: true });
      expect(await screen.findByText(/No se pudo revisar el transporte/)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Aprobar traslado' })).toBeEnabled();
    });

    it('un traslado aprobado muestra lo aprobado sin volver a consultar', () => {
      mount(
        makeTransfer({
          route_type: 'branch_to_branch',
          requires_approval: true,
          status: 'approved',
          approved_by_name: 'Luis Jefe',
          approved_at: '2026-10-21T09:00:00Z',
          vehicle: transport.vehicle,
          driver: transport.driver,
          approved_vehicle: transport.vehicle,
          approved_driver: transport.driver
        })
      );
      expect(screen.getByText(/FL-001 · C 123/)).toBeInTheDocument();
      expect(apiMock.transferAssignmentCheck).not.toHaveBeenCalled();
    });
  });
});
