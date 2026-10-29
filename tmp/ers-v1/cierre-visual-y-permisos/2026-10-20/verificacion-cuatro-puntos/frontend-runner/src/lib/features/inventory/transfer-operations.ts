import type { TransferDecimal, TransferDemandRecord } from './transfer-documents';

const SCALE = 1_000_000n;

export interface TransferAttempt {
  fingerprint: string;
  idempotencyKey: string;
  contextKey: string;
}

export interface TransferAttemptStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

function attemptStorageKey(contextKey: string, actionName: string): string {
  return `b04-transfer-attempt:${contextKey}:${actionName}`;
}

export function getOrCreateTransferAttempt(
  storage: TransferAttemptStorage | null,
  memory: Map<string, TransferAttempt>,
  contextKey: string,
  actionName: string,
  fingerprint: string,
  createIdempotencyKey: () => string
): TransferAttempt {
  const key = attemptStorageKey(contextKey, actionName);
  if (storage) {
    try {
      const raw = storage.getItem(key);
      if (raw) {
        const saved = JSON.parse(raw) as TransferAttempt;
        if (saved.contextKey === contextKey && saved.fingerprint === fingerprint && saved.idempotencyKey) {
          memory.set(key, saved);
          return saved;
        }
      }
    } catch {
      // Fall back to an in-memory retry record if browser storage is unavailable or malformed.
    }
  }
  const remembered = memory.get(key);
  if (remembered?.contextKey === contextKey && remembered.fingerprint === fingerprint) return remembered;

  const attempt = { contextKey, fingerprint, idempotencyKey: createIdempotencyKey() };
  memory.set(key, attempt);
  if (storage) {
    try {
      storage.setItem(key, JSON.stringify(attempt));
    } catch {
      // The request can still use this key and retry in this mounted session.
    }
  }
  return attempt;
}

export function clearTransferAttempt(
  storage: TransferAttemptStorage | null,
  memory: Map<string, TransferAttempt>,
  contextKey: string,
  actionName: string
): void {
  const key = attemptStorageKey(contextKey, actionName);
  memory.delete(key);
  if (storage) {
    try {
      storage.removeItem(key);
    } catch {
      // Clearing a retry record is best-effort after the server confirms the command.
    }
  }
}

export function scaledQuantity(raw: TransferDecimal | null | undefined): bigint | null {
  if (raw == null) return null;
  const value = String(raw).trim();
  const match = /^(\d+)(?:\.(\d{0,6}))?$/.exec(value);
  if (!match) return null;
  const fraction = (match[2] ?? '').padEnd(6, '0');
  return BigInt(match[1] ?? '0') * SCALE + BigInt(fraction || '0');
}

export function quantityString(raw: string): string | null {
  const value = raw.trim();
  const parsed = scaledQuantity(value);
  if (parsed == null || parsed <= 0n) return null;
  const whole = parsed / SCALE;
  const fraction = String(parsed % SCALE).padStart(6, '0').replace(/0+$/, '');
  return fraction ? `${whole}.${fraction}` : String(whole);
}

export function quantityFromScaled(value: bigint): string {
  if (value <= 0n) return '0';
  const whole = value / SCALE;
  const fraction = String(value % SCALE).padStart(6, '0').replace(/0+$/, '');
  return fraction ? `${whole}.${fraction}` : String(whole);
}

export function allocateDemandQuantity(
  plannedQuantity: string,
  pendingQuantity: TransferDecimal,
  allocatedElsewhere: bigint
): bigint {
  const planned = scaledQuantity(plannedQuantity);
  const pending = scaledQuantity(pendingQuantity);
  if (planned == null || pending == null || planned <= 0n) return 0n;
  const remaining = pending > allocatedElsewhere ? pending - allocatedElsewhere : 0n;
  return planned < remaining ? planned : remaining;
}

export function compareQuantities(left: TransferDecimal, right: TransferDecimal): number {
  const a = scaledQuantity(left);
  const b = scaledQuantity(right);
  if (a == null || b == null) return Number.NaN;
  return a < b ? -1 : a > b ? 1 : 0;
}

export function remainingAssignment(demand: TransferDemandRecord): string {
  // The API contract explicitly defines quantity_pending as requested minus assigned.
  return String(demand.quantity_pending);
}

export function formatQuantity(raw: TransferDecimal | null | undefined): string {
  if (raw == null || scaledQuantity(raw) == null) return '—';
  return new Intl.NumberFormat('es-SV', { maximumFractionDigits: 6 }).format(Number(raw));
}

export function transferStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    preparation: 'En preparación',
    in_transit: 'En tránsito',
    received: 'Recibido',
    closed_with_adjustment: 'Cerrado con ajuste',
    incident: 'Con incidencia',
    cancelled: 'Cancelado'
  };
  return labels[status] ?? 'Estado desconocido';
}

export function demandProgressLabel(demand: TransferDemandRecord): string {
  return `Solicitado ${formatQuantity(demand.quantity_requested)} · Asignado ${formatQuantity(
    demand.quantity_assigned
  )} · Despachado ${formatQuantity(demand.quantity_dispatched)} · En tránsito ${formatQuantity(
    demand.quantity_in_transit
  )} · Recibido ${formatQuantity(demand.quantity_received)} · Pendiente de asignar ${formatQuantity(
    demand.quantity_pending
  )}`;
}
