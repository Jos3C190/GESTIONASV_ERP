import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { makeTransfer } from '../../../../../tests/unit/fixtures/inventory-transfer';
import type { DispatchCheck, DispatchSelection, InventoryTransfer } from '../transfer-documents';

const apiMock = vi.hoisted(() => ({
  dispatchOptions: vi.fn(),
  dispatchCheck: vi.fn()
}));
vi.mock('$lib/features/inventory/transfer-documents', () => ({ inventoryTransfersApi: apiMock }));

import TransferDispatchPanel from './TransferDispatchPanel.svelte';
import Host from '../../../../../tests/unit/TransferDispatchPanelHost.svelte';

const vehicleRef = {
  id: 'iv1',
  code: 'FL-001',
  name: 'Hiace',
  status: 'active',
  plate: 'C 123'
};
const driverRef = { id: 'd1', name: 'Carlos Martínez', employee_code: 'EMP-1' };

function transferWith(patch: Partial<InventoryTransfer> = {}): InventoryTransfer {
  return makeTransfer({ id: 't1', ...patch });
}

function emptySelection(): DispatchSelection {
  return {
    vehicleId: '',
    driverId: '',
    overrideReason: '',
    substitutionCode: '',
    substitutionReason: '',
    ready: false,
    label: ''
  };
}

function check(patch: Partial<DispatchCheck> = {}): DispatchCheck {
  return {
    vehicle_id: 'iv1',
    driver_id: 'd1',
    vehicle_issues: [],
    driver_issues: [],
    blocked: false,
    hard_blocked: false,
    can_override: true,
    ...patch
  };
}

function blockedCheck(): DispatchCheck {
  return check({
    vehicle_issues: [
      {
        code: 'document_expired',
        severity: 'blocking',
        message: 'Póliza de seguro vencida.',
        overridable: true
      }
    ],
    blocked: true
  });
}

function vehicleOption(id: string, code: string, patch: Record<string, unknown> = {}) {
  const isSecond = id === 'iv2';
  return {
    inventory_vehicle_id: id,
    fleet_vehicle_id: `fleet-${id}`,
    code,
    plate: id === 'iv1' ? 'C 123' : 'C 456',
    kind: 'cargo_van',
    brand: 'Toyota',
    model: 'Hiace',
    compliance_state: 'ok',
    available: true,
    unavailable_reason: null,
    // Each vehicle has its own driver assigned in Fleet.
    driver_id: isSecond ? 'd2' : 'd1',
    driver_name: isSecond ? 'Rosa Pineda' : 'Carlos Martínez',
    ...patch
  };
}

beforeEach(() => {
  apiMock.dispatchOptions.mockResolvedValue({
    origin_branch_id: 'b1',
    origin_branch_name: 'Roosevelt',
    vehicles: [vehicleOption('iv1', 'FL-001'), vehicleOption('iv2', 'FL-002')],
    drivers: [
      {
        id: 'd1',
        name: 'Carlos Martínez',
        license_class: 'liviana',
        compliance_state: 'ok',
        current_vehicle_code: 'FL-001'
      },
      {
        id: 'd2',
        name: 'Rosa Pineda',
        license_class: 'liviana',
        compliance_state: 'ok',
        current_vehicle_code: null
      }
    ]
  });
  apiMock.dispatchCheck.mockResolvedValue(check());
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function mount(transfer: InventoryTransfer, selection = emptySelection()) {
  return render(TransferDispatchPanel, { transfer, disabled: false, selection });
}

describe('transfer dispatch panel', () => {
  it('preselecciona el vehículo y el conductor guardados y pide una excepción si hay impedimentos', async () => {
    apiMock.dispatchCheck.mockResolvedValue(blockedCheck());
    mount(transferWith({ vehicle: vehicleRef, driver: driverRef }));
    expect(await screen.findByText('Póliza de seguro vencida.')).toBeVisible();
    expect(apiMock.dispatchCheck).toHaveBeenCalledWith('t1', 'iv1', 'd1');
    expect(screen.getByLabelText('Vehículo de Roosevelt')).toHaveValue('iv1');
    expect(screen.getByLabelText('Conductor')).toHaveValue('d1');
    await fireEvent.input(screen.getByRole('textbox'), {
      target: { value: 'Póliza renovada, en trámite' }
    });
    expect(screen.getByRole('textbox')).toHaveValue('Póliza renovada, en trámite');
  });

  it('no salta al primer vehículo disponible cuando no hay uno guardado', async () => {
    mount(transferWith());
    await screen.findByLabelText('Vehículo de Roosevelt');
    await waitFor(() => expect(apiMock.dispatchOptions).toHaveBeenCalledWith('t1'));
    expect(screen.getByLabelText('Vehículo de Roosevelt')).toHaveValue('');
    expect(apiMock.dispatchCheck).not.toHaveBeenCalled();
  });

  it('mantiene el vehículo guardado aunque ya no esté disponible y explica por qué', async () => {
    apiMock.dispatchOptions.mockResolvedValue({
      origin_branch_id: 'b1',
      origin_branch_name: 'Roosevelt',
      vehicles: [
        vehicleOption('iv1', 'FL-001', {
          available: false,
          unavailable_reason: 'En mantenimiento'
        }),
        vehicleOption('iv2', 'FL-002')
      ],
      drivers: []
    });
    apiMock.dispatchCheck.mockResolvedValue(
      check({
        blocked: true,
        hard_blocked: true,
        can_override: false,
        vehicle_issues: [
          {
            code: 'vehicle_in_maintenance',
            severity: 'blocking',
            message: 'El vehículo está en mantenimiento.',
            overridable: false
          }
        ]
      })
    );
    mount(transferWith({ vehicle: vehicleRef, driver: driverRef }));
    expect(await screen.findByText(/El vehículo está en mantenimiento\./)).toBeVisible();
    expect(screen.getByLabelText('Vehículo de Roosevelt')).toHaveValue('iv1');
  });

  it('nunca ofrece una excepción para los impedimentos que no la admiten', async () => {
    apiMock.dispatchCheck.mockResolvedValue(
      check({
        hard_blocked: true,
        blocked: true,
        vehicle_issues: [
          {
            code: 'vehicle_on_road',
            severity: 'blocking',
            message: 'El vehículo está en el traslado TR-9.',
            overridable: false
          }
        ]
      })
    );
    mount(transferWith({ vehicle: vehicleRef, driver: driverRef }));
    expect(
      await screen.findByText('El vehículo está en el traslado TR-9. (no admite excepción)')
    ).toBeVisible();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });

  it('no pide motivo mientras el traslado aprobado sale con su mismo transporte', async () => {
    mount(
      transferWith({
        status: 'approved',
        vehicle: vehicleRef,
        driver: driverRef,
        approved_vehicle: vehicleRef,
        approved_driver: driverRef
      })
    );
    expect(await screen.findByText(/Aprobado con FL-001 · C 123 y Carlos Martínez/)).toBeVisible();
    await waitFor(() => expect(apiMock.dispatchCheck).toHaveBeenCalled());
    expect(screen.queryByLabelText('Motivo del cambio')).not.toBeInTheDocument();
  });

  it('exige código y motivo de al menos 10 caracteres al cambiar el vehículo aprobado', async () => {
    const dispatched: DispatchSelection[] = [];
    render(Host, {
      transfer: transferWith({
        status: 'approved',
        vehicle: vehicleRef,
        driver: driverRef,
        approved_vehicle: vehicleRef,
        approved_driver: driverRef
      }),
      onSelection: (value: DispatchSelection) => dispatched.push(value)
    });
    await waitFor(() => expect(apiMock.dispatchCheck).toHaveBeenCalledWith('t1', 'iv1', 'd1'));
    const last = () => dispatched[dispatched.length - 1]!;
    await waitFor(() => expect(last().ready).toBe(true));

    await fireEvent.change(screen.getByLabelText('Vehículo de Roosevelt'), {
      target: { value: 'iv2' }
    });
    expect(
      await screen.findByText(/Se aprobó con FL-001 · C 123 y Carlos Martínez\./)
    ).toBeVisible();
    expect(screen.getByText(/El cambio quedará registrado y auditado\./)).toBeVisible();
    await waitFor(() => expect(apiMock.dispatchCheck).toHaveBeenCalledWith('t1', 'iv2', 'd2'));
    // The approved transport was still fit at departure, and the panel says so.
    expect(await screen.findByText(/Lo aprobado todavía está apto/)).toBeVisible();
    await waitFor(() => expect(last().vehicleId).toBe('iv2'));
    expect(last().ready).toBe(false);

    await fireEvent.change(screen.getByLabelText('Motivo del cambio'), {
      target: { value: 'vehicle_unavailable' }
    });
    await fireEvent.input(screen.getByLabelText('Explica el cambio'), {
      target: { value: 'corto' }
    });
    expect(last().ready).toBe(false);
    await fireEvent.input(screen.getByLabelText('Explica el cambio'), {
      target: { value: 'El vehículo aprobado no arrancó' }
    });
    await waitFor(() => expect(last().ready).toBe(true));
    expect(last()).toMatchObject({
      vehicleId: 'iv2',
      driverId: 'd2',
      substitutionCode: 'vehicle_unavailable',
      substitutionReason: 'El vehículo aprobado no arrancó'
    });
  });

  it('avisa cuando lo aprobado ya no estaba apto según el despacho, no según la planificación', async () => {
    apiMock.dispatchCheck.mockImplementation(async (_id: string, vehicle: string) =>
      vehicle === 'iv1'
        ? check({
            blocked: true,
            hard_blocked: true,
            can_override: false,
            vehicle_issues: [
              {
                code: 'vehicle_in_maintenance',
                severity: 'blocking',
                message: 'El vehículo está en mantenimiento.',
                overridable: false
              }
            ]
          })
        : check({ vehicle_id: 'iv2' })
    );
    mount(
      transferWith({
        status: 'approved',
        vehicle: vehicleRef,
        driver: driverRef,
        approved_vehicle: vehicleRef,
        approved_driver: driverRef
      })
    );
    await waitFor(() => expect(apiMock.dispatchCheck).toHaveBeenCalledWith('t1', 'iv1', 'd1'));
    await fireEvent.change(await screen.findByLabelText('Vehículo de Roosevelt'), {
      target: { value: 'iv2' }
    });
    expect(await screen.findByText(/Lo aprobado ya no está apto/)).toBeVisible();
    expect(screen.queryByText(/Lo aprobado todavía está apto/)).not.toBeInTheDocument();
  });

  it('también detecta el cambio de conductor aprobado', async () => {
    mount(
      transferWith({
        status: 'approved',
        vehicle: vehicleRef,
        driver: driverRef,
        approved_vehicle: vehicleRef,
        approved_driver: driverRef
      })
    );
    await waitFor(() => expect(apiMock.dispatchCheck).toHaveBeenCalled());
    await fireEvent.change(await screen.findByLabelText('Conductor'), { target: { value: 'd2' } });
    expect(await screen.findByLabelText('Explica el cambio')).toBeVisible();
    await waitFor(() => expect(apiMock.dispatchCheck).toHaveBeenCalledWith('t1', 'iv1', 'd2'));
  });

  it('al cambiar de vehículo ofrece el conductor de Flota del nuevo y manda siempre un conductor explícito', async () => {
    const dispatched: DispatchSelection[] = [];
    render(Host, {
      transfer: transferWith({
        status: 'approved',
        vehicle: vehicleRef,
        driver: driverRef,
        approved_vehicle: vehicleRef,
        approved_driver: driverRef
      }),
      onSelection: (value: DispatchSelection) => dispatched.push(value)
    });
    const last = () => dispatched[dispatched.length - 1]!;
    await waitFor(() => expect(last().ready).toBe(true));
    expect(last().driverId).toBe('d1');

    await fireEvent.change(screen.getByLabelText('Vehículo de Roosevelt'), {
      target: { value: 'iv2' }
    });
    // The driver that was only the previous vehicle's moves to the new vehicle's own driver.
    await waitFor(() => expect(screen.getByLabelText('Conductor')).toHaveValue('d2'));
    await waitFor(() => expect(apiMock.dispatchCheck).toHaveBeenCalledWith('t1', 'iv2', 'd2'));
    expect(await screen.findByLabelText('Explica el cambio')).toBeVisible();
    await waitFor(() => expect(last()).toMatchObject({ vehicleId: 'iv2', driverId: 'd2' }));

    // Every driver stays pickable, including the Fleet driver of the chosen vehicle...
    const driver = screen.getByLabelText('Conductor');
    expect(driver).toHaveValue('d2');
    expect(screen.queryByRole('option', { name: /^Asignado:/ })).not.toBeInTheDocument();
    // ...and a driver chosen on purpose is kept, never replaced by a server default.
    await fireEvent.change(driver, { target: { value: 'd1' } });
    await waitFor(() => expect(last()).toMatchObject({ vehicleId: 'iv2', driverId: 'd1' }));
    await fireEvent.change(screen.getByLabelText('Motivo del cambio'), {
      target: { value: 'driver_unavailable' }
    });
    await fireEvent.input(screen.getByLabelText('Explica el cambio'), {
      target: { value: 'Rosa no pudo salir hoy' }
    });
    await waitFor(() => expect(last().ready).toBe(true));
    expect(last()).toMatchObject({
      driverId: 'd1',
      substitutionCode: 'driver_unavailable',
      substitutionReason: 'Rosa no pudo salir hoy'
    });
  });
});
