import { describe, expect, it } from 'vitest';
import {
  availableCapacityGroupParents,
  buildCapacityGroupTree,
  capacityGroupDraftToInput,
  emptyCapacityGroupDraft,
  validateCapacityGroupDraft
} from './capacity-groups.logic';
import type { WarehouseCapacityGroup } from './capacity-groups.types';

function group(
  id: string,
  parentId: string | null = null,
  overrides: Partial<WarehouseCapacityGroup> = {}
): WarehouseCapacityGroup {
  return {
    id,
    warehouseId: 'warehouse-1',
    parentId,
    code: id.toUpperCase(),
    name: `Grupo ${id}`,
    groupType: 'structural',
    certifiedMaxWeightKg: null,
    operationalMaxWeightKg: null,
    certifiedUsableVolumeM3: null,
    operationalUsableVolumeM3: null,
    capacityProfile: 'general_mixed',
    capacityEnforcementMode: 'disabled',
    capacityStatus: 'not_configured',
    storageEligible: true,
    usableLengthM: null,
    usableWidthM: null,
    usableHeightM: null,
    isActive: true,
    directLocationCount: 0,
    subtreeLocationCount: 0,
    createdAt: '2026-08-19T00:00:00Z',
    updatedAt: null,
    ...overrides
  };
}

describe('capacity group hierarchy', () => {
  it('projects parents before children at the proper depth', () => {
    const rows = buildCapacityGroupTree([
      group('level', 'bay'),
      group('rack'),
      group('bay', 'rack')
    ]);

    expect(rows.map((row) => [row.group.id, row.depth])).toEqual([
      ['rack', 0],
      ['bay', 1],
      ['level', 2]
    ]);
  });

  it('excludes the edited group, descendants and inactive groups as parents', () => {
    const groups = [
      group('rack'),
      group('bay', 'rack'),
      group('level', 'bay'),
      group('other'),
      group('inactive', null, { isActive: false }),
      group('active-below-inactive', 'inactive')
    ];

    expect(availableCapacityGroupParents(groups, 'bay').map((item) => item.id)).toEqual([
      'other',
      'rack'
    ]);
  });
});

describe('capacity group physical limits', () => {
  it('preserves unknown measurements as null instead of zero', () => {
    const input = capacityGroupDraftToInput({
      ...emptyCapacityGroupDraft(),
      code: 'RACK-A',
      name: 'Rack A'
    });

    expect(input.certified_max_weight_kg).toBeNull();
    expect(input.operational_max_weight_kg).toBeNull();
    expect(input.certified_usable_volume_m3).toBeNull();
    expect(input.usable_length_m).toBeNull();
  });

  it('rejects an operational limit above its certified limit', () => {
    const errors = validateCapacityGroupDraft(
      {
        ...emptyCapacityGroupDraft(),
        code: 'RACK-A',
        name: 'Rack A',
        certified_max_weight_kg: '1000',
        operational_max_weight_kg: '1200'
      },
      [],
      null
    );

    expect(errors.operational_max_weight_kg).toContain('certificado');
  });

  it('requires complete weight and volume limits when enforcement blocks excesses', () => {
    const errors = validateCapacityGroupDraft(
      {
        ...emptyCapacityGroupDraft(),
        code: 'RACK-A',
        name: 'Rack A',
        capacity_enforcement_mode: 'enforce',
        certified_max_weight_kg: '1000',
        operational_max_weight_kg: '900'
      },
      [],
      null
    );

    expect(errors.capacity_enforcement_mode).toContain('cuatro límites');
  });

  it('rejects a root structure limit above the warehouse', () => {
    const errors = validateCapacityGroupDraft(
      {
        ...emptyCapacityGroupDraft(),
        code: 'RACK-A',
        name: 'Rack A',
        certified_max_weight_kg: '1200',
        operational_max_weight_kg: '900'
      },
      [],
      null,
      {
        code: 'BOD-01',
        certifiedMaxWeightKg: 1000,
        operationalMaxWeightKg: 900,
        certifiedUsableVolumeM3: 100,
        operationalUsableVolumeM3: 90
      }
    );

    expect(errors.certified_max_weight_kg).toContain('almacén BOD-01');
  });
});
