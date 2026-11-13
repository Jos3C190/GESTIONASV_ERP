import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { HttpError } from '../../src/lib/api/client';
import TransferOperationsPage from '../../src/lib/features/inventory/components/TransferOperationsPage.svelte';
import type {
  InventoryTransfer,
  TransferRouteOptions
} from '../../src/lib/features/inventory/transfer-documents';
import { makeLine, makeTransfer } from './fixtures/inventory-transfer';

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  list: vi.fn(),
  submit: vi.fn(),
  withdraw: vi.fn(),
  approve: vi.fn(),
  reject: vi.fn(),
  cancel: vi.fn(),
  dispatch: vi.fn(),
  dispatchOptions: vi.fn(),
  dispatchCheck: vi.fn(),
  transferAssignmentCheck: vi.fn(),
  assignmentOptions: vi.fn(),
  assignmentCheck: vi.fn(),
  update: vi.fn(),
  routeOptions: vi.fn(),
  pendingApprovalCount: vi.fn(),
  listLocations: vi.fn(),
  listTransferUnits: vi.fn(),
  listDemand: vi.fn(),
  listVehicles: vi.fn(),
  permissions: new Set<string>(),
  user: { id: 'user-approver', is_superuser: false } as { id: string; is_superuser: boolean },
  accessAllBranches: true,
  branches: [] as Array<{ id: string }>
}));
vi.mock('$lib/stores/company.svelte', () => ({ company: { id: 'company-1' } }));
vi.mock('$lib/stores/branch.svelte', () => ({
  branch: {
    id: null,
    ready: true,
    get accessAllBranches() {
      return mocks.accessAllBranches;
    },
    get branches() {
      return mocks.branches;
    }
  }
}));
vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: { hasPermission: (code: string) => mocks.permissions.has(code) }
}));
vi.mock('$lib/stores/session.svelte', () => ({
  session: {
    get user() {
      return mocks.user;
    }
  }
}));
vi.mock('$lib/features/locations/services', () => ({ listLocations: mocks.listLocations }));
vi.mock('$lib/features/inventory/services', () => ({
  inventoryApi: { listTransferUnits: mocks.listTransferUnits }
}));
vi.mock('$lib/features/inventory/transfer-documents', () => ({
  inventoryTransfersApi: {
    get: mocks.get,
    list: mocks.list,
    submit: mocks.submit,
    withdraw: mocks.withdraw,
    approve: mocks.approve,
    reject: mocks.reject,
    cancel: mocks.cancel,
    dispatch: mocks.dispatch,
    dispatchOptions: mocks.dispatchOptions,
    dispatchCheck: mocks.dispatchCheck,
    transferAssignmentCheck: mocks.transferAssignmentCheck,
    assignmentOptions: mocks.assignmentOptions,
    assignmentCheck: mocks.assignmentCheck,
    update: mocks.update,
    routeOptions: mocks.routeOptions,
    pendingApprovalCount: mocks.pendingApprovalCount,
    listDemand: mocks.listDemand,
    listVehicles: mocks.listVehicles
  }
}));

const policy = {
  allow_branch_to_branch: true,
  allow_branch_to_central: true,
  require_approval: true
};
const northBranchWarehouse = {
  id: 'wh-north',
  code: 'BOD-N',
  name: 'Bodega Norte',
  branch_id: 'branch-north',
  branch_name: 'Sucursal Norte',
  is_central: false
};
const centralWarehouse = {
  id: 'wh-central',
  code: 'BOD-C',
  name: 'Bodega Central',
  branch_id: 'branch-matrix',
  branch_name: 'Casa matriz',
  is_central: true
};

function routeOptions(patch: Partial<TransferRouteOptions> = {}): TransferRouteOptions {
  return { policy, origins: [], destinations: [], ...patch };
}

const branchTransfer = (patch: Partial<InventoryTransfer> = {}) =>
  makeTransfer({
    vehicle: { id: 'vehicle-1', code: 'FL-001', name: 'Hiace', status: 'active', plate: 'C 123' },
    driver: { id: 'driver-1', name: 'Carlos Martínez', employee_code: 'EMP-1' },
    route_type: 'branch_to_branch',
    origin_is_central: false,
    origin_branch_name: 'Sucursal Norte',
    destination_branch_name: 'Sucursal Sur',
    created_by_id: 'user-author',
    status: 'pending_approval',
    requires_approval: true,
    approval_round: 3,
    submitted_by_id: 'user-author',
    submitted_by_name: 'Ana Autora',
    submitted_at: '2026-10-20T12:00:00Z',
    ...patch
  });

function openAs(transfer: InventoryTransfer) {
  mocks.get.mockResolvedValue(transfer);
  mocks.list.mockResolvedValue([transfer]);
}

async function openDocument() {
  render(TransferOperationsPage);
  await fireEvent.click(await screen.findByRole('button', { name: 'Documentos' }));
  await fireEvent.click(await screen.findByRole('button', { name: /TR-DEMO-A/ }));
}

beforeEach(() => {
  mocks.permissions = new Set(['inventory:read', 'inventory:move']);
  mocks.user = { id: 'user-approver', is_superuser: false };
  mocks.accessAllBranches = true;
  mocks.branches = [];
  for (const mock of [
    mocks.get,
    mocks.list,
    mocks.submit,
    mocks.withdraw,
    mocks.approve,
    mocks.reject,
    mocks.cancel,
    mocks.dispatch,
    mocks.dispatchOptions,
    mocks.dispatchCheck,
    mocks.transferAssignmentCheck,
    mocks.assignmentOptions,
    mocks.assignmentCheck,
    mocks.update,
    mocks.routeOptions,
    mocks.pendingApprovalCount,
    mocks.listLocations,
    mocks.listTransferUnits,
    mocks.listDemand,
    mocks.listVehicles
  ])
    mock.mockReset();
  mocks.transferAssignmentCheck.mockResolvedValue({
    vehicle_id: 'vehicle-1',
    driver_id: 'driver-1',
    vehicle_issues: [],
    driver_issues: [],
    planning_blocked: false,
    warnings: 0,
    conflicts: [],
    load_kg: null,
    load_missing_weight: 0
  });
  mocks.assignmentOptions.mockResolvedValue({
    origin_branch_id: 'branch-matrix',
    origin_branch_name: 'Casa matriz',
    vehicles: [],
    drivers: []
  });
  mocks.assignmentCheck.mockResolvedValue({
    vehicle_id: 'vehicle-1',
    driver_id: 'driver-1',
    vehicle_issues: [],
    driver_issues: [],
    planning_blocked: false,
    warnings: 0,
    conflicts: [],
    load_kg: null,
    load_missing_weight: 0
  });
  mocks.routeOptions.mockResolvedValue(routeOptions());
  mocks.pendingApprovalCount.mockResolvedValue(0);
  mocks.list.mockResolvedValue([]);
  mocks.listLocations.mockResolvedValue({ items: [], meta: { pages: 1 } });
  mocks.listTransferUnits.mockResolvedValue([]);
  mocks.listDemand.mockResolvedValue([]);
  mocks.listVehicles.mockResolvedValue([]);
  mocks.dispatchOptions.mockResolvedValue({
    origin_branch_id: 'branch-north',
    origin_branch_name: 'Sucursal Norte',
    vehicles: [],
    drivers: []
  });
  sessionStorage.clear();
});

describe('aprobación de traslados en la página', () => {
  it('aprueba con la ronda que vio la persona, tras confirmar que se revalidan las existencias', async () => {
    mocks.permissions.add('inventory:transfer_approve');
    const approved = branchTransfer({
      status: 'approved',
      approved_by_name: 'Luis Jefe',
      approved_at: '2026-10-21T09:00:00Z'
    });
    openAs(branchTransfer());
    mocks.approve.mockResolvedValue(approved);
    await openDocument();

    await fireEvent.click(await screen.findByRole('button', { name: 'Aprobar traslado' }));
    expect(
      await screen.findByText(/Se revalidarán las existencias de TR-DEMO-A/)
    ).toBeInTheDocument();
    mocks.get.mockResolvedValue(approved);
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar acción' }));

    await waitFor(() =>
      expect(mocks.approve).toHaveBeenCalledWith('transfer-a', expect.any(String), 3)
    );
    expect(
      await screen.findByText('TR-DEMO-A fue aprobado. Ya puedes despacharlo.')
    ).toBeInTheDocument();
    expect(await screen.findByText(/Aprobado por Luis Jefe/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Confirmar despacho' })).toBeInTheDocument();
  });

  it('rechaza con un motivo válido y manda la misma ronda', async () => {
    mocks.permissions.add('inventory:transfer_approve');
    const rejected = branchTransfer({
      status: 'preparation',
      rejected_by_name: 'Luis Jefe',
      rejected_at: '2026-10-21T09:00:00Z',
      rejection_reason: 'Falta el sello del encargado'
    });
    openAs(branchTransfer());
    mocks.reject.mockResolvedValue(rejected);
    await openDocument();

    await fireEvent.click(await screen.findByRole('button', { name: 'Rechazar' }));
    await fireEvent.input(await screen.findByLabelText('Motivo del rechazo'), {
      target: { value: 'no' }
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar rechazo' }));
    expect(mocks.reject).not.toHaveBeenCalled();

    await fireEvent.input(screen.getByLabelText('Motivo del rechazo'), {
      target: { value: 'Falta el sello del encargado' }
    });
    mocks.get.mockResolvedValue(rejected);
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar rechazo' }));

    await waitFor(() =>
      expect(mocks.reject).toHaveBeenCalledWith(
        'transfer-a',
        expect.any(String),
        3,
        'Falta el sello del encargado'
      )
    );
    expect(await screen.findByText(/Rechazado por Luis Jefe/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Enviar a aprobación' })).toBeInTheDocument();
  });

  it('no deja aprobar al autor, pero sí retirar la solicitud', async () => {
    mocks.permissions.add('inventory:transfer_approve');
    mocks.user = { id: 'user-author', is_superuser: false };
    const back = branchTransfer({ status: 'preparation', submitted_by_id: null });
    openAs(branchTransfer());
    mocks.withdraw.mockResolvedValue(back);
    await openDocument();

    expect(
      await screen.findByText(
        'No puedes aprobar un traslado que tú preparaste, editaste o enviaste.'
      )
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Aprobar traslado' })).not.toBeInTheDocument();

    mocks.get.mockResolvedValue(back);
    await fireEvent.click(screen.getByRole('button', { name: 'Retirar solicitud' }));
    await waitFor(() =>
      expect(mocks.withdraw).toHaveBeenCalledWith('transfer-a', expect.any(String))
    );
    expect(await screen.findByText(/TR-DEMO-A volvió a preparación/)).toBeInTheDocument();
  });

  it('no ofrece decidir a quien no cubre la sucursal de origen', async () => {
    mocks.permissions.add('inventory:transfer_approve');
    mocks.accessAllBranches = false;
    mocks.branches = [{ id: 'branch-south' }];
    openAs(branchTransfer({ origin_branch_id: 'branch-north' }));
    await openDocument();

    expect(
      await screen.findByText(
        'No tienes acceso a la sucursal de origen para decidir este traslado.'
      )
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Aprobar traslado' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Rechazar' })).not.toBeInTheDocument();
  });

  it('ofrece decidir a quien cubre la sucursal de origen aunque no vea todas', async () => {
    mocks.permissions.add('inventory:transfer_approve');
    mocks.accessAllBranches = false;
    mocks.branches = [{ id: 'branch-north' }];
    openAs(branchTransfer({ origin_branch_id: 'branch-north' }));
    await openDocument();
    expect(await screen.findByRole('button', { name: 'Aprobar traslado' })).toBeEnabled();
  });

  it('no deja decidir a quien editó la preparación', async () => {
    mocks.permissions.add('inventory:transfer_approve');
    mocks.user = { id: 'user-editor', is_superuser: false };
    openAs(
      branchTransfer({ last_edited_by_id: 'user-editor', last_edited_by_name: 'Eva Editora' })
    );
    await openDocument();
    expect(
      await screen.findByText(
        'No puedes aprobar un traslado que tú preparaste, editaste o enviaste.'
      )
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Aprobar traslado' })).not.toBeInTheDocument();
  });

  it('si la empresa ya no exige aprobación, relee el documento y las reglas', async () => {
    mocks.permissions.add('inventory:transfer_approve');
    openAs(branchTransfer());
    mocks.approve.mockRejectedValue(
      new HttpError(
        'transfer_approval_not_applicable',
        'Esta empresa no exige aprobación para esta ruta; puedes despachar directamente.',
        422
      )
    );
    await openDocument();
    await fireEvent.click(await screen.findByRole('button', { name: 'Aprobar traslado' }));
    const readsBefore = mocks.get.mock.calls.length;
    const rulesBefore = mocks.routeOptions.mock.calls.length;
    mocks.routeOptions.mockResolvedValue(
      routeOptions({ policy: { ...policy, require_approval: false } })
    );
    await fireEvent.click(await screen.findByRole('button', { name: 'Confirmar acción' }));

    expect(await screen.findByText(/no exige aprobación para esta ruta/)).toBeInTheDocument();
    await waitFor(() => expect(mocks.get.mock.calls.length).toBeGreaterThan(readsBefore));
    await waitFor(() => expect(mocks.routeOptions.mock.calls.length).toBeGreaterThan(rulesBefore));
  });

  it('si la ruta se apagó mientras tanto, relee el documento y muestra la ruta desactivada', async () => {
    mocks.permissions.add('inventory:transfer_approve');
    openAs(branchTransfer());
    mocks.approve.mockRejectedValue(
      new HttpError(
        'transfer_route_disabled',
        'Los traslados entre sucursales no están habilitados en esta empresa.',
        409
      )
    );
    await openDocument();
    await fireEvent.click(await screen.findByRole('button', { name: 'Aprobar traslado' }));
    mocks.routeOptions.mockResolvedValue(
      routeOptions({ policy: { ...policy, allow_branch_to_branch: false } })
    );
    await fireEvent.click(await screen.findByRole('button', { name: 'Confirmar acción' }));

    expect(await screen.findByText(/Esta ruta está desactivada/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Aprobar traslado' })).toBeDisabled();
  });

  it('el superusuario ve aprobar aunque haya preparado el traslado', async () => {
    mocks.permissions.add('inventory:transfer_approve');
    mocks.user = { id: 'user-author', is_superuser: true };
    openAs(branchTransfer());
    await openDocument();
    expect(await screen.findByRole('button', { name: 'Aprobar traslado' })).toBeEnabled();
  });

  it('una preparación que requiere aprobación ofrece enviarla y no despacharla', async () => {
    const preparing = branchTransfer({ status: 'preparation', submitted_by_id: null });
    const sent = branchTransfer();
    openAs(preparing);
    mocks.submit.mockResolvedValue(sent);
    await openDocument();

    expect(
      await screen.findByText(
        'Este traslado sale de Sucursal Norte y necesita aprobación antes de despacharse.'
      )
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Confirmar despacho' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Editar preparación' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Cancelar preparación' })).toBeEnabled();

    mocks.get.mockResolvedValue(sent);
    await fireEvent.click(screen.getByRole('button', { name: 'Enviar a aprobación' }));
    await waitFor(() =>
      expect(mocks.submit).toHaveBeenCalledWith('transfer-a', expect.any(String))
    );
    expect(await screen.findByText('TR-DEMO-A quedó pendiente de aprobación.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cancelar traslado' })).toBeEnabled();
  });

  it('un traslado aprobado se despacha y se puede cancelar como traslado', async () => {
    openAs(
      branchTransfer({
        status: 'approved',
        approved_by_name: 'Luis Jefe',
        approved_at: '2026-10-21T09:00:00Z'
      })
    );
    await openDocument();

    expect(await screen.findByText(/Aprobado por Luis Jefe/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Confirmar despacho' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cancelar traslado' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Editar preparación' })).not.toBeInTheDocument();
    await waitFor(() => expect(mocks.dispatchOptions).toHaveBeenCalledWith('transfer-a'));
  });

  it('la distribución desde la central conserva el despacho directo sin aprobación', async () => {
    openAs(makeTransfer({ status: 'preparation' }));
    await openDocument();

    expect(await screen.findByRole('button', { name: 'Confirmar despacho' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Enviar a aprobación' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cancelar preparación' })).toBeInTheDocument();
  });

  it('si la solicitud cambió mientras tanto, avisa y vuelve a leer el documento', async () => {
    mocks.permissions.add('inventory:transfer_approve');
    openAs(branchTransfer());
    mocks.approve.mockRejectedValue(
      new HttpError(
        'transfer_approval_stale',
        'La solicitud cambió desde que la abriste; actualiza el documento antes de decidir.',
        409
      )
    );
    await openDocument();
    await fireEvent.click(await screen.findByRole('button', { name: 'Aprobar traslado' }));
    const readsBefore = mocks.get.mock.calls.length;
    await fireEvent.click(await screen.findByRole('button', { name: 'Confirmar acción' }));

    expect(await screen.findByText(/La solicitud cambió desde que la abriste/)).toBeInTheDocument();
    await waitFor(() => expect(mocks.get.mock.calls.length).toBeGreaterThan(readsBefore));
  });

  it('con la ruta apagada no se aprueba, pero se puede rechazar', async () => {
    mocks.permissions.add('inventory:transfer_approve');
    mocks.routeOptions.mockResolvedValue(
      routeOptions({ policy: { ...policy, allow_branch_to_branch: false } })
    );
    openAs(branchTransfer());
    await openDocument();

    expect(await screen.findByRole('button', { name: 'Aprobar traslado' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Rechazar' })).toBeEnabled();
    expect(screen.getByText(/Esta ruta está desactivada/)).toBeInTheDocument();
  });
});

describe('edición de una preparación', () => {
  it('espera los destinos de la bodega antes de consultar la demanda', async () => {
    let originCalls = 0;
    mocks.routeOptions.mockImplementation(async (origin?: string) => {
      if (!origin) return routeOptions({ origins: [centralWarehouse] });
      originCalls += 1;
      // La primera lectura aún no conoce destinos; la de la edición sí.
      return routeOptions({
        origins: [centralWarehouse],
        destinations:
          originCalls > 1 ? [{ ...northBranchWarehouse, route_type: 'central_distribution' }] : []
      });
    });
    openAs(makeTransfer({ status: 'preparation', origin_warehouse_id: 'wh-central' }));
    await openDocument();
    expect(mocks.listDemand).not.toHaveBeenCalled();

    await fireEvent.click(await screen.findByRole('button', { name: 'Editar preparación' }));

    await waitFor(() => expect(mocks.listDemand).toHaveBeenCalledWith('branch-north'));
    // La bodega de origen se ve como texto, no como un selector deshabilitado.
    expect(document.getElementById('preparation-origin-label')).toHaveTextContent(
      'Bodega de origen'
    );
    expect(document.querySelector('#transfer-origin')).toBeNull();
  });

  it('al editar conserva el vehículo y el conductor guardados en lugar de borrarlos', async () => {
    const saved = makeTransfer({
      status: 'preparation',
      origin_warehouse_id: 'wh-central',
      destination_warehouse_id: 'wh-north',
      vehicle: { id: 'vehicle-1', code: 'FL-001', name: 'Hiace', status: 'active', plate: 'C 123' },
      driver: { id: 'driver-1', name: 'Carlos Martínez', employee_code: 'EMP-1' },
      lines: [
        makeLine({
          id: 'line-1',
          source_handling_unit_id: 'hu-1',
          quantity_planned: '2',
          excess_reason: 'Reposición'
        })
      ]
    });
    mocks.routeOptions.mockImplementation(async (origin?: string) =>
      routeOptions({
        origins: [centralWarehouse],
        destinations: origin
          ? [{ ...northBranchWarehouse, route_type: 'central_distribution' }]
          : []
      })
    );
    mocks.listTransferUnits.mockResolvedValue([
      {
        id: 'hu-1',
        code: 'HU-1',
        product_id: 1,
        inventory_item_id: 'item-1',
        base_unit_id: 1,
        base_unit_symbol: 'u',
        product_name: 'Producto de prueba',
        product_sku: 'SKU-DEMO',
        quantity_base: '10',
        lot_code: null,
        receipt_lot_code: null
      }
    ]);
    mocks.assignmentOptions.mockResolvedValue({
      origin_branch_id: 'branch-matrix',
      origin_branch_name: 'Casa matriz',
      vehicles: [],
      drivers: []
    });
    mocks.update.mockResolvedValue(saved);
    openAs(saved);
    await openDocument();
    await fireEvent.click(await screen.findByRole('button', { name: 'Editar preparación' }));

    await waitFor(() =>
      expect(mocks.assignmentOptions).toHaveBeenCalledWith('wh-central', 'transfer-a')
    );
    await waitFor(() =>
      expect(mocks.assignmentCheck).toHaveBeenCalledWith(
        expect.objectContaining({ vehicle_id: 'vehicle-1', driver_id: 'driver-1' })
      )
    );
    const save = await screen.findByRole('button', { name: 'Guardar cambios' });
    await waitFor(() => expect(save).toBeEnabled());
    await fireEvent.click(save);
    await waitFor(() => expect(mocks.update).toHaveBeenCalledTimes(1));
    expect(mocks.update).toHaveBeenCalledWith(
      'transfer-a',
      expect.objectContaining({ vehicle_id: 'vehicle-1', driver_id: 'driver-1' })
    );
  });
});

describe('bandeja del aprobador', () => {
  it('avisa cuántos traslados esperan y abre Documentos filtrado por Por aprobar', async () => {
    mocks.permissions.add('inventory:transfer_approve');
    mocks.pendingApprovalCount.mockResolvedValue(2);
    mocks.list.mockResolvedValue([branchTransfer()]);
    render(TransferOperationsPage);

    const pill = await screen.findByRole('button', { name: 'Tienes 2 traslados por aprobar' });
    // La pestaña conserva su nombre exacto.
    expect(screen.getByRole('button', { name: 'Documentos' })).toBeInTheDocument();
    await fireEvent.click(pill);

    await waitFor(() =>
      expect(mocks.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ awaitingMyApproval: true, status: undefined })
      )
    );
    expect(await screen.findByRole('button', { name: 'Por aprobar (2)' })).toHaveAttribute(
      'aria-pressed',
      'true'
    );
    expect(screen.getByLabelText('Estado')).toBeDisabled();

    await fireEvent.click(screen.getByRole('button', { name: 'Todos' }));
    await waitFor(() =>
      expect(mocks.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ awaitingMyApproval: undefined })
      )
    );
  });

  it('usa el singular y no aparece sin traslados pendientes ni sin el permiso', async () => {
    mocks.permissions.add('inventory:transfer_approve');
    mocks.pendingApprovalCount.mockResolvedValue(1);
    const view = render(TransferOperationsPage);
    expect(
      await screen.findByRole('button', { name: 'Tienes 1 traslado por aprobar' })
    ).toBeInTheDocument();
    view.unmount();

    mocks.pendingApprovalCount.mockResolvedValue(0);
    render(TransferOperationsPage);
    await screen.findByRole('button', { name: 'Documentos' });
    expect(screen.queryByRole('button', { name: /por aprobar/ })).not.toBeInTheDocument();
  });

  it('no consulta el contador a quien no puede aprobar y tolera que falle', async () => {
    render(TransferOperationsPage);
    await screen.findByRole('button', { name: 'Documentos' });
    expect(mocks.pendingApprovalCount).not.toHaveBeenCalled();
  });

  it('un fallo del contador no rompe la página', async () => {
    mocks.permissions.add('inventory:transfer_approve');
    mocks.pendingApprovalCount.mockRejectedValue(new Error('sin red'));
    render(TransferOperationsPage);
    expect(await screen.findByRole('button', { name: 'Documentos' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /por aprobar/ })).not.toBeInTheDocument();
  });
});

describe('reglas y origen en la cabecera y el abastecimiento', () => {
  it('muestra el enlace a las reglas solo con el permiso de configurarlas', async () => {
    render(TransferOperationsPage);
    await screen.findByRole('button', { name: 'Documentos' });
    expect(screen.queryByRole('link', { name: 'Reglas de traslados' })).not.toBeInTheDocument();
  });

  it('muestra el enlace a las reglas a quien puede configurarlas', async () => {
    mocks.permissions.add('inventory:transfer_settings');
    render(TransferOperationsPage);
    expect(await screen.findByRole('link', { name: 'Reglas de traslados' })).toHaveAttribute(
      'href',
      '/transfers/settings'
    );
  });

  it('planifica desde la central con la demanda de las sucursales', async () => {
    mocks.routeOptions.mockImplementation(async (origin?: string) =>
      routeOptions({
        origins: [centralWarehouse, northBranchWarehouse],
        destinations: origin
          ? [{ ...northBranchWarehouse, route_type: 'central_distribution' }]
          : []
      })
    );
    render(TransferOperationsPage);

    expect(await screen.findByText('Planificar abastecimiento')).toBeInTheDocument();
    await waitFor(() => expect(mocks.listDemand).toHaveBeenCalledWith('branch-north'));
    expect(mocks.listTransferUnits).toHaveBeenCalledWith('wh-central', 'available');
    expect(screen.getByLabelText('Bodega de origen')).toBeInTheDocument();
  });

  it('desde una sucursal no consulta la demanda y cambia el título', async () => {
    mocks.routeOptions.mockImplementation(async (origin?: string) =>
      routeOptions({
        origins: [northBranchWarehouse],
        destinations: origin ? [{ ...centralWarehouse, route_type: 'branch_to_central' }] : []
      })
    );
    render(TransferOperationsPage);

    expect(await screen.findByText('Preparar traslado desde sucursal')).toBeInTheDocument();
    await waitFor(() =>
      expect(mocks.listTransferUnits).toHaveBeenCalledWith('wh-north', 'available')
    );
    expect(mocks.listDemand).not.toHaveBeenCalled();
    expect(screen.queryByText('Planificar abastecimiento')).not.toBeInTheDocument();
    expect(screen.queryByText('Sucursales solicitantes')).not.toBeInTheDocument();
  });

  it('avisa cuando no hay ninguna bodega de origen en el alcance', async () => {
    render(TransferOperationsPage);
    expect(
      await screen.findByText(/No hay una bodega de origen disponible en tu alcance/)
    ).toBeInTheDocument();
  });
});
