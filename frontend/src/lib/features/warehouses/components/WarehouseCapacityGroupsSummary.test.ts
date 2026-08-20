import { render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import WarehouseCapacityGroupsSummary from './WarehouseCapacityGroupsSummary.svelte';
import type { WarehouseCapacityGroup } from '../capacity-groups.types';

const serviceMocks = vi.hoisted(() => ({
  listCapacityGroups: vi.fn(),
  getCapacityConfigurationDiagnostics: vi.fn()
}));

vi.mock('../capacity-groups.service', () => serviceMocks);

const group = (overrides: Partial<WarehouseCapacityGroup> = {}): WarehouseCapacityGroup => ({
  id: 'group-1',
  warehouseId: 'warehouse-1',
  parentId: null,
  code: 'RACK-A',
  name: 'Rack A',
  groupType: 'rack',
  certifiedMaxWeightKg: 1000,
  operationalMaxWeightKg: 900,
  certifiedUsableVolumeM3: 20,
  operationalUsableVolumeM3: 18,
  capacityProfile: 'rack',
  capacityEnforcementMode: 'enforce',
  capacityStatus: 'available',
  storageEligible: true,
  usableLengthM: 8,
  usableWidthM: 2,
  usableHeightM: 2.4,
  isActive: true,
  directLocationCount: 2,
  subtreeLocationCount: 2,
  createdAt: '2026-08-20T00:00:00Z',
  updatedAt: null,
  ...overrides
});

describe('WarehouseCapacityGroupsSummary', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    serviceMocks.listCapacityGroups.mockResolvedValue([
      group(),
      group({ id: 'group-2', code: 'RACK-B', name: 'Rack B', isActive: false })
    ]);
    serviceMocks.getCapacityConfigurationDiagnostics.mockResolvedValue({
      warehouseId: 'warehouse-1',
      issues: [
        {
          severity: 'warning',
          code: 'nominal_capacity_overallocated',
          scopeType: 'capacity_group',
          scopeId: 'group-1',
          parentScopeType: 'warehouse',
          parentScopeId: 'warehouse-1',
          metric: 'weight',
          limitKind: 'certified',
          childLimit: 1000,
          parentLimit: 900,
          allocatedChildrenTotal: 1000,
          allocationRatioPct: 111.1
        }
      ]
    });
  });

  it('muestra conteos y avisos sin incluir la jerarquía completa', async () => {
    render(WarehouseCapacityGroupsSummary, {
      props: { warehouseId: 'warehouse-1' }
    });

    expect(await screen.findByText('Estructuras y límites compartidos')).toBeVisible();
    expect(screen.getByText('1 activas')).toBeVisible();
    expect(screen.getByText('1 inactivas')).toBeVisible();
    expect(screen.getByText('Revisar antes de cambiar límites')).toBeVisible();
    expect(screen.queryByText('Rack A')).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Ver ubicaciones' })).not.toBeInTheDocument();
  });

  it('muestra el acceso a ubicaciones solo con el permiso correspondiente', async () => {
    render(WarehouseCapacityGroupsSummary, {
      props: { warehouseId: 'warehouse-1', canViewLocations: true }
    });

    expect(await screen.findByRole('link', { name: 'Ver ubicaciones' })).toHaveAttribute(
      'href',
      '/warehouses/warehouse-1/locations'
    );
    expect(screen.getByRole('link', { name: 'Ver estructuras y límites' })).toHaveAttribute(
      'href',
      '/warehouses/warehouse-1/structures'
    );
  });
});
