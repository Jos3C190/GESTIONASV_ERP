import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { AssignmentCheck, AssignmentOptions } from '../transfer-documents';

const apiMock = vi.hoisted(() => ({
  assignmentOptions: vi.fn(),
  assignmentCheck: vi.fn(),
  dispatchOptions: vi.fn(),
  dispatchCheck: vi.fn()
}));
vi.mock('$lib/features/inventory/transfer-documents', () => ({ inventoryTransfersApi: apiMock }));

import TransferAssignmentPicker from './TransferAssignmentPicker.svelte';

function option(id: string, code: string, patch: Record<string, unknown> = {}) {
  return {
    inventory_vehicle_id: id,
    fleet_vehicle_id: `fleet-${id}`,
    code,
    plate: `P-${code}`,
    kind: 'cargo_van',
    brand: 'Toyota',
    model: 'Hiace',
    compliance_state: 'ok' as const,
    available: true,
    unavailable_reason: null,
    driver_id: 'd1',
    driver_name: 'Carlos Martínez',
    ...patch
  };
}

const options: AssignmentOptions = {
  origin_branch_id: 'b1',
  origin_branch_name: 'Roosevelt',
  vehicles: [option('v1', 'FL-001'), option('v2', 'FL-002', { driver_id: null, driver_name: null })],
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
      compliance_state: 'warning',
      current_vehicle_code: null
    }
  ]
};

function verdict(patch: Partial<AssignmentCheck> = {}): AssignmentCheck {
  return {
    vehicle_id: 'v1',
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

const lines = [{ handling_unit_id: 'hu-1', quantity_base: '4' }];

beforeEach(() => {
  apiMock.assignmentOptions.mockResolvedValue(options);
  apiMock.assignmentCheck.mockResolvedValue(verdict());
  apiMock.dispatchOptions.mockResolvedValue(options);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function planning(props: Record<string, unknown> = {}) {
  return render(TransferAssignmentPicker, {
    mode: 'planning',
    originWarehouseId: 'wh-origin',
    draftLines: lines,
    vehicleId: '',
    driverId: '',
    debounceMs: 0,
    ...props
  });
}

describe('TransferAssignmentPicker en planificación', () => {
  it('consulta las opciones del origen y dice si el transporte es obligatorio', async () => {
    planning({ required: true, transferId: 'saved-1' });
    await waitFor(() =>
      expect(apiMock.assignmentOptions).toHaveBeenCalledWith('wh-origin', 'saved-1')
    );
    const vehicle = await screen.findByLabelText('Vehículo de Roosevelt');
    expect(screen.getByText('Obligatorio para enviar a aprobación')).toBeInTheDocument();
    expect(vehicle).toHaveAttribute('aria-describedby', 'transport-help');
    expect(screen.getByLabelText('Conductor')).toHaveAttribute('aria-describedby', 'transport-help');
    cleanup();
    planning({ required: false });
    expect(await screen.findByText('Opcional; se confirma al despachar')).toBeInTheDocument();
  });

  it('juzga el borrador con el peso de sus líneas y ofrece el conductor de Flota', async () => {
    apiMock.assignmentCheck.mockResolvedValue(
      verdict({
        warnings: 1,
        vehicle_issues: [
          {
            code: 'inspection_required',
            severity: 'warning',
            message: 'Al despachar: requiere inspección diaria.',
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
        ],
        load_kg: '120.5',
        load_missing_weight: 2
      })
    );
    planning({ transferId: 'saved-1' });
    const vehicle = await screen.findByLabelText('Vehículo de Roosevelt');
    await waitFor(() => expect(within(vehicle).getAllByRole('option').length).toBeGreaterThan(1));
    await fireEvent.change(vehicle, { target: { value: 'v1' } });

    expect(await screen.findByText('Con advertencias')).toBeInTheDocument();
    expect(screen.getByText('Al despachar: requiere inspección diaria.')).toBeInTheDocument();
    expect(screen.getByText('También está asignado a TR-9 (aprobado).')).toBeInTheDocument();
    expect(screen.getByText(/Carga estimada: 120[.,]5 kg · 2 productos sin peso registrado/)).toBeInTheDocument();
    expect(apiMock.assignmentCheck).toHaveBeenLastCalledWith({
      origin_warehouse_id: 'wh-origin',
      vehicle_id: 'v1',
      driver_id: 'd1',
      transfer_id: 'saved-1',
      lines
    });
    // The driver assigned in Fleet was offered when none was chosen yet.
    expect(screen.getByLabelText('Conductor')).toHaveValue('d1');
  });

  it('marca como no apto lo que no se puede planificar y lo explica', async () => {
    apiMock.assignmentCheck.mockResolvedValue(
      verdict({
        planning_blocked: true,
        driver_issues: [
          {
            code: 'driver_not_active',
            severity: 'blocking',
            message: 'El conductor no está activo.',
            overridable: false
          }
        ]
      })
    );
    planning({ vehicleId: 'v1', driverId: 'd2' });
    expect(await screen.findByText('No apto')).toBeInTheDocument();
    const list = screen.getByRole('list', { name: 'Impedimentos para planificar' });
    expect(within(list).getByText('El conductor no está activo.')).toBeInTheDocument();
  });

  it('con todo en orden dice que está apto', async () => {
    planning({ vehicleId: 'v1', driverId: 'd1' });
    expect(await screen.findByText('Apto')).toBeInTheDocument();
    expect(screen.getByText('Vehículo y conductor aptos para planificar.')).toBeInTheDocument();
  });

  it('descarta la respuesta vieja cuando la elección cambió mientras se esperaba', async () => {
    let releaseFirst: (value: AssignmentCheck) => void = () => {};
    apiMock.assignmentCheck
      .mockImplementationOnce(
        () =>
          new Promise<AssignmentCheck>((resolve) => {
            releaseFirst = resolve;
          })
      )
      .mockResolvedValue(verdict());
    planning({ vehicleId: 'v1', driverId: 'd1' });
    await waitFor(() => expect(apiMock.assignmentCheck).toHaveBeenCalledTimes(1));
    const vehicle = await screen.findByLabelText('Vehículo de Roosevelt');
    await waitFor(() => expect(within(vehicle).getAllByRole('option').length).toBeGreaterThan(1));
    await fireEvent.change(vehicle, { target: { value: 'v2' } });
    expect(await screen.findByText('Apto')).toBeInTheDocument();
    releaseFirst(verdict({ planning_blocked: true }));
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(screen.queryByText('No apto')).not.toBeInTheDocument();
    expect(screen.getByText('Apto')).toBeInTheDocument();
  });

  it('espera a que se deje de escribir antes de volver a juzgar el peso', async () => {
    const view = planning({ vehicleId: 'v1', driverId: 'd1', debounceMs: 60 });
    await waitFor(() => expect(apiMock.assignmentCheck).toHaveBeenCalledTimes(1));
    await view.rerender({ draftLines: [{ handling_unit_id: 'hu-1', quantity_base: '5' }] });
    await view.rerender({ draftLines: [{ handling_unit_id: 'hu-1', quantity_base: '6' }] });
    expect(apiMock.assignmentCheck).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(apiMock.assignmentCheck).toHaveBeenCalledTimes(2));
    expect(apiMock.assignmentCheck).toHaveBeenLastCalledWith(
      expect.objectContaining({ lines: [{ handling_unit_id: 'hu-1', quantity_base: '6' }] })
    );
  });

  it('no juzga sin vehículo y muestra el error si no se puede consultar', async () => {
    planning();
    await screen.findByLabelText('Vehículo de Roosevelt');
    expect(apiMock.assignmentCheck).not.toHaveBeenCalled();
    cleanup();
    apiMock.assignmentCheck.mockRejectedValue(new Error('Sin conexión con el servidor'));
    planning({ vehicleId: 'v1', driverId: 'd1' });
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo validar la selección.');
  });

  it('conserva un vehículo guardado que la lista ya no ofrece', async () => {
    apiMock.assignmentOptions.mockResolvedValue({ ...options, vehicles: [option('v2', 'FL-002')] });
    planning({ vehicleId: 'v1', driverId: 'd1', vehicleFallbackLabel: 'FL-001 · P-FL-001' });
    const vehicle = await screen.findByLabelText('Vehículo de Roosevelt');
    await waitFor(() => expect(vehicle).toHaveValue('v1'));
    expect(within(vehicle).getByRole('option', { name: 'FL-001 · P-FL-001' })).toBeInTheDocument();
  });
});

describe('TransferAssignmentPicker en despacho', () => {
  it('consulta las opciones y la validación del despacho, no las de planificación', async () => {
    apiMock.dispatchCheck.mockResolvedValue({
      vehicle_id: 'v1',
      driver_id: 'd1',
      vehicle_issues: [],
      driver_issues: [],
      blocked: false,
      hard_blocked: false,
      can_override: false
    });
    render(TransferAssignmentPicker, {
      mode: 'dispatch',
      transferId: 't1',
      vehicleId: 'v1',
      driverId: '',
      debounceMs: 0
    });
    await waitFor(() => expect(apiMock.dispatchOptions).toHaveBeenCalledWith('t1'));
    await waitFor(() => expect(apiMock.dispatchCheck).toHaveBeenCalledWith('t1', 'v1', null));
    expect(apiMock.assignmentOptions).not.toHaveBeenCalled();
    expect(await screen.findByText('Vehículo y conductor aptos para el despacho.')).toBeInTheDocument();
    expect(screen.queryByText(/Obligatorio|Opcional/)).not.toBeInTheDocument();
  });

  it('separa los vehículos no disponibles y no deja elegirlos', async () => {
    apiMock.dispatchOptions.mockResolvedValue({
      ...options,
      vehicles: [
        option('v1', 'FL-001'),
        option('v2', 'FL-002', { available: false, unavailable_reason: 'En mantenimiento' })
      ]
    });
    render(TransferAssignmentPicker, {
      mode: 'dispatch',
      transferId: 't1',
      vehicleId: '',
      driverId: '',
      debounceMs: 0
    });
    const vehicle = await screen.findByLabelText('Vehículo de Roosevelt');
    const unavailable = await within(vehicle).findByRole('option', { name: /FL-002.*En mantenimiento/ });
    expect(unavailable).toBeDisabled();
    expect(within(vehicle).getByRole('option', { name: /FL-001.*Apto/ })).toBeEnabled();
    expect(screen.getByLabelText('Conductor')).toBeInTheDocument();
  });
});
