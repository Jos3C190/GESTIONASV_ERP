import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { DispatchCheck, InventoryTransfer } from '../transfer-documents';

const apiMock = vi.hoisted(() => ({ dispatchOptions: vi.fn(), dispatchCheck: vi.fn() }));
vi.mock('$lib/features/inventory/transfer-documents', () => ({ inventoryTransfersApi: apiMock }));

import TransferDispatchPanel from './TransferDispatchPanel.svelte';

const transfer = { id: 't1', vehicle: null } as unknown as InventoryTransfer;

function check(patch: Partial<DispatchCheck> = {}): DispatchCheck {
  return {
    vehicle_id: 'iv1',
    driver_id: 'd1',
    vehicle_issues: [
      {
        code: 'document_expired',
        severity: 'blocking',
        message: 'Póliza de seguro vencida.',
        overridable: true
      }
    ],
    driver_issues: [],
    blocked: true,
    hard_blocked: false,
    can_override: true,
    ...patch
  };
}

beforeEach(() => {
  apiMock.dispatchOptions.mockResolvedValue({
    origin_branch_id: 'b1',
    origin_branch_name: 'Roosevelt',
    vehicles: [
      {
        inventory_vehicle_id: 'iv1',
        fleet_vehicle_id: 'v1',
        code: 'FL-001',
        plate: 'C 123',
        kind: 'cargo_van',
        brand: 'Toyota',
        model: 'Hiace',
        compliance_state: 'blocked',
        available: true,
        unavailable_reason: null,
        driver_id: 'd1',
        driver_name: 'Carlos Martínez'
      }
    ],
    drivers: [
      {
        id: 'd1',
        name: 'Carlos Martínez',
        license_class: 'liviana',
        compliance_state: 'ok',
        current_vehicle_code: 'FL-001'
      }
    ]
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('transfer dispatch panel', () => {
  it('defaults to the assigned driver and requires a reason to override', async () => {
    apiMock.dispatchCheck.mockResolvedValue(check());
    const selection = { vehicleId: '', driverId: '', overrideReason: '', ready: false, label: '' };
    const { component } = render(TransferDispatchPanel, { transfer, disabled: false, selection });
    expect(await screen.findByText('Póliza de seguro vencida.')).toBeVisible();
    expect(apiMock.dispatchCheck).toHaveBeenCalledWith('t1', 'iv1', null);
    const reason = screen.getByRole('textbox');
    await fireEvent.input(reason, { target: { value: 'Póliza renovada, en trámite' } });
    expect(component).toBeTruthy();
  });

  it('never offers an exception for hard blocks', async () => {
    apiMock.dispatchCheck.mockResolvedValue(
      check({
        hard_blocked: true,
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
    render(TransferDispatchPanel, {
      transfer,
      disabled: false,
      selection: { vehicleId: '', driverId: '', overrideReason: '', ready: false, label: '' }
    });
    expect(
      await screen.findByText('El vehículo está en el traslado TR-9. (no admite excepción)')
    ).toBeVisible();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });
});
