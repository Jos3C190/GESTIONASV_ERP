import { describe, expect, it } from 'vitest';
import type {
  AssignmentCheck,
  TransferDemandRecord,
  TransferDiscrepancy
} from './transfer-documents';
import {
  allocateDemandQuantity,
  assignmentFitness,
  businessToday,
  clearTransferAttempt,
  compareQuantities,
  DAMAGE_TYPE_OPTIONS,
  damageTypeLabel,
  demandProgressLabel,
  discrepancyKindLabel,
  discrepancyResolutionLabel,
  discrepancySummary,
  formatQuantity,
  getOrCreateTransferAttempt,
  isDiscrepancyActive,
  isFrozenWhenRouteOff,
  isOnRoad,
  isReceivable,
  isRouteEnabled,
  pendingReceptionQuantity,
  substitutionCodeLabel,
  SUBSTITUTION_CODE_OPTIONS,
  quantityFromScaled,
  quantityString,
  remainingAssignment,
  scaledQuantity,
  TRANSFER_STATUS_OPTIONS,
  transferRouteLabel,
  transferStatusLabel,
  type TransferAttempt
} from './transfer-operations';

const demand: TransferDemandRecord = {
  purchase_request_detail_id: 'detail-1',
  purchase_request_id: 'request-1',
  request_code: 'SCR-00001',
  request_status: 'approved',
  branch_id: 'branch-1',
  branch_name: 'Sucursal Roosevelt',
  request_date: '2026-10-19T12:00:00Z',
  required_date: '2026-10-22T12:00:00Z',
  product_id: 1,
  inventory_item_id: 'item-1',
  product_name: 'Café',
  sku: 'PRD-CAF-001',
  unit_id: 1,
  unit_name: 'Caja',
  unit_symbol: 'cj',
  quantity_requested: '10',
  quantity_assigned: '8',
  quantity_dispatched: '6',
  quantity_in_transit: '2',
  quantity_received: '4',
  quantity_pending: '2',
  quantity_adjusted_out: '0'
};

describe('transfer-operations', () => {
  it('parses and formats quantities without binary floating-point rounding', () => {
    expect(scaledQuantity('12.345678')).toBe(12_345_678n);
    expect(scaledQuantity('1.0000001')).toBeNull();
    expect(scaledQuantity('-1')).toBeNull();
    expect(scaledQuantity('1e3')).toBeNull();
    expect(quantityString('12.340000')).toBe('12.34');
    expect(quantityString('0')).toBeNull();
    expect(quantityFromScaled(12_345_600n)).toBe('12.3456');
    expect(compareQuantities('0.3', '0.300001')).toBe(-1);
    expect(formatQuantity('1234.000001')).toBe('1,234.000001');
  });

  it('assigns up to the unassigned demand and exposes only requested-minus-assigned as pending', () => {
    expect(allocateDemandQuantity('1.25', '2', 0n)).toBe(1_250_000n);
    expect(allocateDemandQuantity('1', '2', 1_500_000n)).toBe(500_000n);
    expect(allocateDemandQuantity('1', '2', 2_500_000n)).toBe(0n);
    expect(remainingAssignment(demand)).toBe('2');
    const progress = demandProgressLabel(demand);
    expect(progress).toContain('Pendiente de asignar 2');
    expect(progress).toContain('En tránsito 2');
    expect(progress).toContain('Recibido 4');
  });

  it('reuses a retry key for the same context and body, and isolates changed requests', () => {
    const values = new Map<string, string>();
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key)
    };
    const memory = new Map<string, TransferAttempt>();
    let nextKey = 0;
    const createKey = () => `attempt-${++nextKey}`;

    const first = getOrCreateTransferAttempt(storage, memory, 'company-a:all:all', 'dispatch:transfer-1', '{"vehicle":"v1"}', createKey);
    const retry = getOrCreateTransferAttempt(storage, memory, 'company-a:all:all', 'dispatch:transfer-1', '{"vehicle":"v1"}', createKey);
    const changedBody = getOrCreateTransferAttempt(storage, memory, 'company-a:all:all', 'dispatch:transfer-1', '{"vehicle":"v2"}', createKey);
    const changedContext = getOrCreateTransferAttempt(storage, memory, 'company-b:all:all', 'dispatch:transfer-1', '{"vehicle":"v1"}', createKey);

    expect(retry.idempotencyKey).toBe(first.idempotencyKey);
    expect(changedBody.idempotencyKey).not.toBe(first.idempotencyKey);
    expect(changedContext.idempotencyKey).not.toBe(first.idempotencyKey);
    expect(nextKey).toBe(3);
  });

  it('keeps an in-memory retry key when browser storage is unavailable and clears it after confirmation', () => {
    const memory = new Map<string, TransferAttempt>();
    let nextKey = 0;
    const createKey = () => `attempt-${++nextKey}`;

    const first = getOrCreateTransferAttempt(null, memory, 'company-a:branch-1:scoped', 'receive:transfer-1', 'line-1:8', createKey);
    const retry = getOrCreateTransferAttempt(null, memory, 'company-a:branch-1:scoped', 'receive:transfer-1', 'line-1:8', createKey);
    clearTransferAttempt(null, memory, 'company-a:branch-1:scoped', 'receive:transfer-1');
    const next = getOrCreateTransferAttempt(null, memory, 'company-a:branch-1:scoped', 'receive:transfer-1', 'line-1:8', createKey);

    expect(retry.idempotencyKey).toBe(first.idempotencyKey);
    expect(next.idempotencyKey).not.toBe(first.idempotencyKey);
    expect(nextKey).toBe(2);
  });
  it('nombra los estados de aprobación y las tres rutas', () => {
    expect(transferStatusLabel('pending_approval')).toBe('Pendiente de aprobación');
    expect(transferStatusLabel('approved')).toBe('Aprobado');
    expect(transferRouteLabel('central_distribution')).toBe('Distribución desde matriz');
    expect(transferRouteLabel('branch_to_branch')).toBe('Entre sucursales');
    expect(transferRouteLabel('branch_to_central')).toBe('Retorno a matriz');
    const values = TRANSFER_STATUS_OPTIONS.map((option) => option.value);
    expect(values).toContain('pending_approval');
    expect(values).toContain('approved');
    expect(new Set(values).size).toBe(values.length);
  });

  it('sabe si las reglas permiten trabajar una ruta y qué estados congela', () => {
    const rules = { allow_branch_to_branch: true, allow_branch_to_central: false };
    expect(isRouteEnabled('central_distribution', { ...rules, allow_branch_to_branch: false })).toBe(true);
    expect(isRouteEnabled('branch_to_branch', rules)).toBe(true);
    expect(isRouteEnabled('branch_to_central', rules)).toBe(false);
    expect(isRouteEnabled('branch_to_central', null)).toBe(true);
    expect(isFrozenWhenRouteOff('pending_approval')).toBe(true);
    expect(isFrozenWhenRouteOff('approved')).toBe(true);
    expect(isFrozenWhenRouteOff('in_transit')).toBe(false);
    expect(isFrozenWhenRouteOff('incident')).toBe(false);
  });
});

function discrepancy(patch: Partial<TransferDiscrepancy>): TransferDiscrepancy {
  return {
    id: 'd-1',
    transfer_detail_id: 'line-1',
    line_number: 1,
    product_name: 'Producto',
    sku: 'SKU',
    base_unit_symbol: 'u',
    kind: 'damage',
    status: 'open',
    source: 'receipt',
    quantity: '1',
    damage_type: 'broken',
    notes: 'Caja rota',
    evidence_reference: null,
    location_id: null,
    location_code: null,
    handling_unit_id: null,
    handling_unit_code: null,
    receipt_id: null,
    incident_id: null,
    opened_by_id: 'u-1',
    opened_by_name: null,
    opened_at: '2026-10-20T12:00:00Z',
    claim_reference: null,
    claimed_by_id: null,
    claimed_by_name: null,
    claimed_at: null,
    resolution: null,
    resolution_notes: null,
    resolved_by_id: null,
    resolved_by_name: null,
    resolved_at: null,
    origin_count_required: false,
    origin_counted_by_id: null,
    origin_counted_by_name: null,
    origin_counted_at: null,
    origin_count_notes: null,
    adjustment: null,
    ...patch
  };
}

describe('recepción parcial y discrepancias', () => {
  it('nombra los estados nuevos y los ofrece en el filtro', () => {
    expect(transferStatusLabel('partially_received')).toBe('Recepción parcial');
    expect(transferStatusLabel('discrepancy')).toBe('Con discrepancia');
    const options = Object.fromEntries(
      TRANSFER_STATUS_OPTIONS.map((item) => [item.value, item.label])
    );
    expect(options.partially_received).toBe('Con recepción parcial');
    expect(options.discrepancy).toBe('Con discrepancia');
  });

  it('sabe cuándo el vehículo está en ruta y cuándo se puede recibir', () => {
    for (const status of ['in_transit', 'partially_received', 'incident'])
      expect(isOnRoad(status)).toBe(true);
    for (const status of ['approved', 'discrepancy', 'received', 'closed_with_adjustment'])
      expect(isOnRoad(status)).toBe(false);
    expect(isReceivable('in_transit')).toBe(true);
    expect(isReceivable('partially_received')).toBe(true);
    expect(isReceivable('incident')).toBe(false);
    expect(isReceivable('discrepancy')).toBe(false);
  });

  it('usa lo pendiente de recepción y, sin él, lo que sigue en tránsito', () => {
    expect(
      pendingReceptionQuantity({ quantity_in_transit: '5', quantity_pending_reception: '2' })
    ).toBe(2_000_000n);
    expect(pendingReceptionQuantity({ quantity_in_transit: '5' })).toBe(5_000_000n);
  });

  it('nombra los tipos de avería, de diferencia y de sustitución', () => {
    expect(DAMAGE_TYPE_OPTIONS).toHaveLength(8);
    expect(damageTypeLabel('temperature')).toBe('Cadena de frío rota');
    expect(damageTypeLabel('tampered')).toBe('Empaque abierto o sello violado');
    expect(discrepancyKindLabel('shortage')).toBe('Faltante');
    expect(discrepancyKindLabel('damage')).toBe('Avería');
    expect(discrepancyKindLabel('surplus')).toBe('Sobrante');
    expect(discrepancyResolutionLabel('shortage', 'found')).toBe('Llegó la mercadería');
    expect(discrepancyResolutionLabel('damage', 'released')).toBe('Liberada a cuarentena');
    expect(SUBSTITUTION_CODE_OPTIONS.map((item) => item.value)).toEqual([
      'vehicle_unfit',
      'vehicle_unavailable',
      'driver_unfit',
      'driver_unavailable',
      'load_change',
      'other'
    ]);
    expect(substitutionCodeLabel('load_change')).toBe('Cambió la carga');
  });

  it('resume el cierre por tipo y resolución', () => {
    expect(
      discrepancySummary([
        discrepancy({ id: 'a', kind: 'damage', status: 'in_claim' }),
        discrepancy({ id: 'b', kind: 'surplus', status: 'resolved', resolution: 'regularized' })
      ])
    ).toBe('1 avería en reclamo · 1 sobrante regularizado');
    expect(
      discrepancySummary([
        discrepancy({ id: 'a', kind: 'damage', status: 'resolved', resolution: 'written_off' }),
        discrepancy({ id: 'b', kind: 'damage', status: 'resolved', resolution: 'written_off' }),
        discrepancy({ id: 'c', kind: 'shortage', status: 'open' }),
        discrepancy({ id: 'd', kind: 'shortage', status: 'resolved', resolution: 'written_off' })
      ])
    ).toBe('2 averías dadas de baja · 1 faltante por resolver · 1 faltante dado de baja');
    expect(discrepancySummary([])).toBe('');
  });

  it('distingue lo que aún se atiende de lo ya resuelto o anulado', () => {
    expect(isDiscrepancyActive({ status: 'open' })).toBe(true);
    expect(isDiscrepancyActive({ status: 'in_claim' })).toBe(true);
    expect(isDiscrepancyActive({ status: 'resolved' })).toBe(false);
    expect(isDiscrepancyActive({ status: 'cancelled' })).toBe(false);
  });

  it('resume la aptitud de un transporte planificado', () => {
    const base: AssignmentCheck = {
      vehicle_id: 'v',
      driver_id: 'd',
      vehicle_issues: [],
      driver_issues: [],
      planning_blocked: false,
      warnings: 0,
      conflicts: [],
      load_kg: null,
      load_missing_weight: 0
    };
    expect(assignmentFitness(null)).toBeNull();
    expect(assignmentFitness(base)).toBe('ok');
    expect(assignmentFitness({ ...base, warnings: 1 })).toBe('warning');
    expect(assignmentFitness({ ...base, planning_blocked: true })).toBe('blocked');
  });

  it('da la fecha de hoy en el calendario de la empresa', () => {
    expect(businessToday(new Date('2026-10-21T03:30:00Z'))).toBe('2026-10-20');
  });
});
