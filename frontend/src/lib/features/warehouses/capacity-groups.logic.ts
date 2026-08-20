import type {
  CapacityGroupFieldErrors,
  CapacityGroupTreeRow,
  WarehouseCapacityGroup,
  WarehouseCapacityGroupDraft,
  WarehouseCapacityGroupInput
} from './capacity-groups.types';

const compareGroups = (left: WarehouseCapacityGroup, right: WarehouseCapacityGroup) =>
  left.code.localeCompare(right.code, 'es', { numeric: true, sensitivity: 'base' }) ||
  left.name.localeCompare(right.name, 'es', { sensitivity: 'base' });

export function buildCapacityGroupTree(groups: WarehouseCapacityGroup[]): CapacityGroupTreeRow[] {
  const byId = new Map(groups.map((group) => [group.id, group]));
  const children = new Map<string, WarehouseCapacityGroup[]>();
  const roots: WarehouseCapacityGroup[] = [];
  const orphanIds = new Set<string>();

  for (const group of groups) {
    if (group.parentId && group.parentId !== group.id && byId.has(group.parentId)) {
      const siblings = children.get(group.parentId) ?? [];
      siblings.push(group);
      children.set(group.parentId, siblings);
    } else {
      roots.push(group);
      if (group.parentId) orphanIds.add(group.id);
    }
  }

  roots.sort(compareGroups);
  for (const siblings of children.values()) siblings.sort(compareGroups);

  const rows: CapacityGroupTreeRow[] = [];
  const visited = new Set<string>();
  const visit = (group: WarehouseCapacityGroup, depth: number, inheritedOrphan = false) => {
    if (visited.has(group.id)) return;
    visited.add(group.id);
    const directChildren = children.get(group.id) ?? [];
    const orphaned = inheritedOrphan || orphanIds.has(group.id);
    rows.push({ group, depth, childCount: directChildren.length, orphaned });
    for (const child of directChildren) visit(child, depth + 1, orphaned);
  };

  for (const root of roots) visit(root, 0);

  // Datos históricos defectuosos (por ejemplo, un ciclo) no deben ocultar nodos.
  for (const remaining of [...groups].sort(compareGroups)) {
    if (!visited.has(remaining.id)) {
      orphanIds.add(remaining.id);
      visit(remaining, 0, true);
    }
  }

  return rows;
}

export function getCapacityGroupDescendantIds(
  groups: WarehouseCapacityGroup[],
  groupId: string
): Set<string> {
  const children = new Map<string, string[]>();
  for (const group of groups) {
    if (!group.parentId) continue;
    children.set(group.parentId, [...(children.get(group.parentId) ?? []), group.id]);
  }

  const descendants = new Set<string>();
  const pending = [...(children.get(groupId) ?? [])];
  while (pending.length > 0) {
    const current = pending.pop();
    if (!current || current === groupId || descendants.has(current)) continue;
    descendants.add(current);
    pending.push(...(children.get(current) ?? []));
  }
  return descendants;
}

export function capacityGroupPath(groups: WarehouseCapacityGroup[], groupId: string): string {
  const byId = new Map(groups.map((group) => [group.id, group]));
  const path: string[] = [];
  const visited = new Set<string>();
  let current = byId.get(groupId);
  while (current && !visited.has(current.id)) {
    visited.add(current.id);
    path.unshift(current.code);
    current = current.parentId ? byId.get(current.parentId) : undefined;
  }
  return path.join(' / ');
}

export function availableCapacityGroupParents(
  groups: WarehouseCapacityGroup[],
  editedGroupId: string | null
): WarehouseCapacityGroup[] {
  const excluded = editedGroupId
    ? getCapacityGroupDescendantIds(groups, editedGroupId)
    : new Set<string>();
  if (editedGroupId) excluded.add(editedGroupId);
  return groups
    .filter((group) => !excluded.has(group.id) && hasUsableActiveAncestry(groups, group.id))
    .sort(compareGroups);
}

function hasUsableActiveAncestry(groups: WarehouseCapacityGroup[], groupId: string): boolean {
  const byId = new Map(groups.map((group) => [group.id, group]));
  const visited = new Set<string>();
  let current = byId.get(groupId);
  while (current) {
    if (!current.isActive || visited.has(current.id)) return false;
    visited.add(current.id);
    if (!current.parentId) return true;
    current = byId.get(current.parentId);
    if (!current) return false;
  }
  return false;
}

export function emptyCapacityGroupDraft(): WarehouseCapacityGroupDraft {
  return {
    parent_id: '',
    code: '',
    name: '',
    group_type: 'structural',
    certified_max_weight_kg: '',
    operational_max_weight_kg: '',
    certified_usable_volume_m3: '',
    operational_usable_volume_m3: '',
    capacity_profile: 'general_mixed',
    capacity_enforcement_mode: 'observe',
    storage_eligible: true,
    usable_length_m: '',
    usable_width_m: '',
    usable_height_m: '',
    is_active: true
  };
}

export function capacityGroupToDraft(group: WarehouseCapacityGroup): WarehouseCapacityGroupDraft {
  const text = (value: number | null) => (value == null ? '' : String(value));
  return {
    parent_id: group.parentId ?? '',
    code: group.code,
    name: group.name,
    group_type: group.groupType,
    certified_max_weight_kg: text(group.certifiedMaxWeightKg),
    operational_max_weight_kg: text(group.operationalMaxWeightKg),
    certified_usable_volume_m3: text(group.certifiedUsableVolumeM3),
    operational_usable_volume_m3: text(group.operationalUsableVolumeM3),
    capacity_profile: group.capacityProfile,
    capacity_enforcement_mode: group.capacityEnforcementMode,
    storage_eligible: group.storageEligible,
    usable_length_m: text(group.usableLengthM),
    usable_width_m: text(group.usableWidthM),
    usable_height_m: text(group.usableHeightM),
    is_active: group.isActive
  };
}

const parseOptionalNumber = (value: string): number | null => {
  if (!value.trim()) return null;
  return Number(value);
};

const CAPACITY_FIELDS = [
  'certified_max_weight_kg',
  'operational_max_weight_kg',
  'certified_usable_volume_m3',
  'operational_usable_volume_m3',
  'usable_length_m',
  'usable_width_m',
  'usable_height_m'
] as const;

export function validateCapacityGroupDraft(
  draft: WarehouseCapacityGroupDraft,
  groups: WarehouseCapacityGroup[],
  editedGroupId: string | null,
  warehouseLimits?: {
    code: string;
    certifiedMaxWeightKg: number | null;
    operationalMaxWeightKg: number | null;
    certifiedUsableVolumeM3: number | null;
    operationalUsableVolumeM3: number | null;
  }
): CapacityGroupFieldErrors {
  const errors: CapacityGroupFieldErrors = {};
  const code = draft.code.trim();
  const name = draft.name.trim();

  if (!code) errors.code = 'Ingrese un código.';
  else if (code.length > 64) errors.code = 'Use 64 caracteres o menos.';
  else if (
    groups.some(
      (group) =>
        group.id !== editedGroupId &&
        group.code.trim().toLocaleUpperCase('es') === code.toLocaleUpperCase('es')
    )
  ) {
    errors.code = 'Ya existe un grupo con este código.';
  }
  if (name.length < 2) errors.name = 'Ingrese un nombre de al menos 2 caracteres.';
  else if (name.length > 160) errors.name = 'Use 160 caracteres o menos.';

  const parsed = Object.fromEntries(
    CAPACITY_FIELDS.map((field) => [field, parseOptionalNumber(draft[field])])
  ) as Record<(typeof CAPACITY_FIELDS)[number], number | null>;
  for (const field of CAPACITY_FIELDS) {
    const value = parsed[field];
    if (value !== null && (!Number.isFinite(value) || value <= 0)) {
      errors[field] = 'Ingrese un valor mayor que cero.';
    }
  }

  if (parsed.operational_max_weight_kg !== null && parsed.certified_max_weight_kg === null) {
    errors.certified_max_weight_kg = 'El límite operativo requiere uno certificado.';
  } else if (
    parsed.operational_max_weight_kg !== null &&
    parsed.certified_max_weight_kg !== null &&
    parsed.operational_max_weight_kg > parsed.certified_max_weight_kg
  ) {
    errors.operational_max_weight_kg = 'No puede superar el límite certificado.';
  }

  if (parsed.operational_usable_volume_m3 !== null && parsed.certified_usable_volume_m3 === null) {
    errors.certified_usable_volume_m3 = 'El límite operativo requiere uno certificado.';
  } else if (
    parsed.operational_usable_volume_m3 !== null &&
    parsed.certified_usable_volume_m3 !== null &&
    parsed.operational_usable_volume_m3 > parsed.certified_usable_volume_m3
  ) {
    errors.operational_usable_volume_m3 = 'No puede superar el límite certificado.';
  }

  const dimensions = [parsed.usable_length_m, parsed.usable_width_m, parsed.usable_height_m];
  if (dimensions.some((value) => value !== null) && !dimensions.every((value) => value !== null)) {
    const message = 'Registre largo, ancho y alto juntos.';
    if (parsed.usable_length_m === null) errors.usable_length_m = message;
    if (parsed.usable_width_m === null) errors.usable_width_m = message;
    if (parsed.usable_height_m === null) errors.usable_height_m = message;
  }

  if (!draft.storage_eligible && draft.capacity_enforcement_mode !== 'disabled') {
    errors.capacity_enforcement_mode =
      'Un espacio no almacenable debe tener el control desactivado.';
  }
  if (
    draft.capacity_enforcement_mode === 'enforce' &&
    [
      parsed.certified_max_weight_kg,
      parsed.operational_max_weight_kg,
      parsed.certified_usable_volume_m3,
      parsed.operational_usable_volume_m3
    ].some((value) => value === null)
  ) {
    errors.capacity_enforcement_mode =
      'Para bloquear excesos debe completar los cuatro límites de peso y volumen.';
  }

  if (draft.parent_id) {
    const parent = groups.find((group) => group.id === draft.parent_id);
    const descendants = editedGroupId
      ? getCapacityGroupDescendantIds(groups, editedGroupId)
      : new Set<string>();
    if (!parent || !hasUsableActiveAncestry(groups, draft.parent_id)) {
      errors.parent_id = 'Seleccione un grupo padre con toda su jerarquía activa.';
    } else if (draft.parent_id === editedGroupId || descendants.has(draft.parent_id)) {
      errors.parent_id = 'Un grupo no puede depender de sí mismo ni de sus descendientes.';
    } else {
      const comparisons = [
        ['certified_max_weight_kg', parent.certifiedMaxWeightKg, 'peso certificado'],
        ['operational_max_weight_kg', parent.operationalMaxWeightKg, 'peso operativo'],
        ['certified_usable_volume_m3', parent.certifiedUsableVolumeM3, 'volumen certificado'],
        ['operational_usable_volume_m3', parent.operationalUsableVolumeM3, 'volumen operativo']
      ] as const;
      for (const [field, parentValue, label] of comparisons) {
        const value = parsed[field];
        if (value != null && parentValue != null && value > parentValue) {
          errors[field] = `No puede superar el ${label} de ${parent.code}.`;
        }
      }
    }
  } else if (warehouseLimits) {
    const comparisons = [
      ['certified_max_weight_kg', warehouseLimits.certifiedMaxWeightKg, 'peso certificado'],
      ['operational_max_weight_kg', warehouseLimits.operationalMaxWeightKg, 'peso operativo'],
      [
        'certified_usable_volume_m3',
        warehouseLimits.certifiedUsableVolumeM3,
        'volumen certificado'
      ],
      [
        'operational_usable_volume_m3',
        warehouseLimits.operationalUsableVolumeM3,
        'volumen operativo'
      ]
    ] as const;
    for (const [field, parentValue, label] of comparisons) {
      const value = parsed[field];
      if (value != null && parentValue != null && value > parentValue) {
        errors[field] = `No puede superar el ${label} del almacén ${warehouseLimits.code}.`;
      }
    }
  }
  if (editedGroupId) {
    const directChildren = groups.filter((group) => group.parentId === editedGroupId);
    const childComparisons = [
      ['certified_max_weight_kg', 'certifiedMaxWeightKg'],
      ['operational_max_weight_kg', 'operationalMaxWeightKg'],
      ['certified_usable_volume_m3', 'certifiedUsableVolumeM3'],
      ['operational_usable_volume_m3', 'operationalUsableVolumeM3']
    ] as const;
    if (
      directChildren.some((child) =>
        childComparisons.some(([draftField, childField]) => {
          const proposed = parsed[draftField];
          const childValue = child[childField];
          return proposed != null && childValue != null && childValue > proposed;
        })
      )
    ) {
      errors.form = 'El nuevo límite dejaría una subestructura por encima de su contenedor.';
    }
  }
  return errors;
}

export function capacityGroupDraftToInput(
  draft: WarehouseCapacityGroupDraft
): WarehouseCapacityGroupInput {
  return {
    parent_id: draft.parent_id || null,
    code: draft.code.trim(),
    name: draft.name.trim(),
    group_type: draft.group_type,
    certified_max_weight_kg: parseOptionalNumber(draft.certified_max_weight_kg),
    operational_max_weight_kg: parseOptionalNumber(draft.operational_max_weight_kg),
    certified_usable_volume_m3: parseOptionalNumber(draft.certified_usable_volume_m3),
    operational_usable_volume_m3: parseOptionalNumber(draft.operational_usable_volume_m3),
    capacity_profile: draft.capacity_profile,
    capacity_enforcement_mode: draft.capacity_enforcement_mode,
    storage_eligible: draft.storage_eligible,
    usable_length_m: parseOptionalNumber(draft.usable_length_m),
    usable_width_m: parseOptionalNumber(draft.usable_width_m),
    usable_height_m: parseOptionalNumber(draft.usable_height_m),
    is_active: draft.is_active
  };
}
