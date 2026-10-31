import { describe, expect, it } from 'vitest';
import type { TransferDemandRecord } from './transfer-documents';
import {
  allocateDemandQuantity,
  clearTransferAttempt,
  compareQuantities,
  demandProgressLabel,
  formatQuantity,
  getOrCreateTransferAttempt,
  quantityFromScaled,
  quantityString,
  remainingAssignment,
  scaledQuantity,
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
});
