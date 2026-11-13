import type {
  AssignmentCheck,
  DamageType,
  DiscrepancyKind,
  DiscrepancyResolution,
  DiscrepancyStatus,
  FitnessState,
  SubstitutionCode,
  TransferDecimal,
  TransferDemandRecord,
  TransferDiscrepancy,
  TransferLine,
  TransferRouteType,
  TransferStatus
} from './transfer-documents';

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
    pending_approval: 'Pendiente de aprobación',
    approved: 'Aprobado',
    in_transit: 'En tránsito',
    partially_received: 'Recepción parcial',
    discrepancy: 'Con discrepancia',
    received: 'Recibido',
    closed_with_adjustment: 'Cerrado con ajuste',
    incident: 'Con incidencia',
    cancelled: 'Cancelado'
  };
  return labels[status] ?? 'Estado desconocido';
}

/** Options of the status filter, in the order a transfer goes through them. */
export const TRANSFER_STATUS_OPTIONS: Array<{ value: TransferStatus | ''; label: string }> = [
  { value: '', label: 'Todos los estados' },
  { value: 'preparation', label: 'En preparación' },
  { value: 'pending_approval', label: 'Pendientes de aprobación' },
  { value: 'approved', label: 'Aprobados' },
  { value: 'in_transit', label: 'En tránsito' },
  { value: 'partially_received', label: 'Con recepción parcial' },
  { value: 'discrepancy', label: 'Con discrepancia' },
  { value: 'received', label: 'Recibidos' },
  { value: 'closed_with_adjustment', label: 'Cerrado con ajuste' },
  { value: 'incident', label: 'Con incidencia' },
  { value: 'cancelled', label: 'Cancelados' }
];

export function transferRouteLabel(route: string): string {
  const labels: Record<string, string> = {
    central_distribution: 'Distribución desde matriz',
    branch_to_branch: 'Entre sucursales',
    branch_to_central: 'Retorno a matriz'
  };
  return labels[route] ?? 'Ruta desconocida';
}

/** Whether the company's rules currently allow working on a transfer of this route. */
export function isRouteEnabled(
  route: TransferRouteType,
  policy: { allow_branch_to_branch: boolean; allow_branch_to_central: boolean } | null
): boolean {
  if (!policy || route === 'central_distribution') return true;
  return route === 'branch_to_branch' ? policy.allow_branch_to_branch : policy.allow_branch_to_central;
}

/** Statuses a rule change freezes: nothing moves them forward while the route is off. */
export function isFrozenWhenRouteOff(status: TransferStatus): boolean {
  return status === 'preparation' || status === 'pending_approval' || status === 'approved';
}

/** The vehicle and the driver are busy and the GPS is watched while a transfer is in these. */
const ON_ROAD: readonly string[] = ['in_transit', 'partially_received', 'incident'];

export function isOnRoad(status: string): boolean {
  return ON_ROAD.includes(status);
}

/** Part of the load may still arrive: the destination can register quantities. */
export function isReceivable(status: string): boolean {
  return status === 'in_transit' || status === 'partially_received';
}

/** What is still on its way and not declared missing; older payloads fall back to in transit. */
export function pendingReceptionQuantity(
  line: Pick<TransferLine, 'quantity_in_transit'> & { quantity_pending_reception?: TransferDecimal }
): bigint {
  return scaledQuantity(line.quantity_pending_reception ?? line.quantity_in_transit) ?? 0n;
}

export const FITNESS_LABEL: Record<FitnessState, string> = {
  ok: 'Apto',
  warning: 'Con advertencias',
  blocked: 'No apto'
};

/** The overall fitness of a transport judgement made ahead of departure. */
export function assignmentFitness(check: AssignmentCheck | null): FitnessState | null {
  if (!check) return null;
  if (check.planning_blocked) return 'blocked';
  const hasIssues = check.vehicle_issues.length > 0 || check.driver_issues.length > 0;
  return hasIssues || check.warnings > 0 || check.conflicts.length > 0 ? 'warning' : 'ok';
}

export const DAMAGE_TYPE_OPTIONS: Array<{ value: DamageType; label: string }> = [
  { value: 'broken', label: 'Rotura' },
  { value: 'crushed', label: 'Golpe o aplastamiento' },
  { value: 'wet', label: 'Humedad o mojado' },
  { value: 'contaminated', label: 'Derrame o contaminación' },
  { value: 'packaging', label: 'Empaque dañado' },
  { value: 'tampered', label: 'Empaque abierto o sello violado' },
  { value: 'temperature', label: 'Cadena de frío rota' },
  { value: 'other', label: 'Otro' }
];

export function damageTypeLabel(type: string | null | undefined): string {
  return DAMAGE_TYPE_OPTIONS.find((option) => option.value === type)?.label ?? 'Otro';
}

export function discrepancyKindLabel(kind: DiscrepancyKind): string {
  return { shortage: 'Faltante', damage: 'Avería', surplus: 'Sobrante' }[kind] ?? 'Diferencia';
}

export function discrepancyStatusLabel(status: DiscrepancyStatus): string {
  const labels: Record<DiscrepancyStatus, string> = {
    open: 'Abierta',
    in_claim: 'En reclamo',
    resolved: 'Resuelta',
    cancelled: 'Anulada'
  };
  return labels[status] ?? 'Estado desconocido';
}

export function discrepancyResolutionLabel(
  kind: DiscrepancyKind,
  resolution: DiscrepancyResolution | null
): string {
  switch (resolution) {
    case 'written_off':
      return kind === 'damage' ? 'Dada de baja' : 'Dado de baja';
    case 'found':
      return 'Llegó la mercadería';
    case 'released':
      return 'Liberada a cuarentena';
    case 'regularized':
      return 'Regularizado con ajuste';
    case 'dismissed':
      return 'Descartado';
    default:
      return 'Sin resolver';
  }
}

export const SUBSTITUTION_CODE_OPTIONS: Array<{ value: SubstitutionCode; label: string }> = [
  { value: 'vehicle_unfit', label: 'El vehículo aprobado ya no está apto' },
  { value: 'vehicle_unavailable', label: 'El vehículo aprobado no está disponible' },
  { value: 'driver_unfit', label: 'El conductor aprobado ya no está apto' },
  { value: 'driver_unavailable', label: 'El conductor aprobado no está disponible' },
  { value: 'load_change', label: 'Cambió la carga' },
  { value: 'other', label: 'Otro motivo' }
];

export function substitutionCodeLabel(code: string | null | undefined): string {
  return SUBSTITUTION_CODE_OPTIONS.find((option) => option.value === code)?.label ?? 'Otro motivo';
}

/** A difference somebody still has to act on (a claim stays active until it is resolved). */
export function isDiscrepancyActive(discrepancy: Pick<TransferDiscrepancy, 'status'>): boolean {
  return discrepancy.status === 'open' || discrepancy.status === 'in_claim';
}

const KIND_NOUN: Record<DiscrepancyKind, [string, string]> = {
  shortage: ['faltante', 'faltantes'],
  damage: ['avería', 'averías'],
  surplus: ['sobrante', 'sobrantes']
};

/** "dado de baja", "liberadas", … agreeing in gender and number with the noun. */
function resolvedPhrase(kind: DiscrepancyKind, count: number, resolution: string): string {
  const ending = `${kind === 'damage' ? 'a' : 'o'}${count === 1 ? '' : 's'}`;
  switch (resolution) {
    case 'written_off':
      return `dad${ending} de baja`;
    case 'released':
      return `liberad${ending}`;
    case 'regularized':
      return `regularizad${ending}`;
    case 'found':
      return `encontrad${ending}`;
    case 'dismissed':
      return `descartad${ending}`;
    default:
      return `resuelt${ending}`;
  }
}

/** "1 avería en reclamo · 1 sobrante regularizado": what became of each difference. */
export function discrepancySummary(discrepancies: TransferDiscrepancy[]): string {
  const groups = new Map<string, { kind: DiscrepancyKind; state: string; count: number }>();
  for (const item of discrepancies) {
    const state =
      item.status === 'open' || item.status === 'in_claim'
        ? item.status
        : (item.resolution ?? item.status);
    const key = `${item.kind}:${state}`;
    const group = groups.get(key) ?? { kind: item.kind, state, count: 0 };
    group.count += 1;
    groups.set(key, group);
  }
  return [...groups.values()]
    .map(({ kind, state, count }) => {
      const noun = KIND_NOUN[kind][count === 1 ? 0 : 1];
      const phrase =
        state === 'open'
          ? 'por resolver'
          : state === 'in_claim'
            ? 'en reclamo'
            : resolvedPhrase(kind, count, state);
      return `${count} ${noun} ${phrase}`;
    })
    .join(' · ');
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

/** What a person asks of one difference of a transfer, gathered by the discrepancy panel. */
export interface DiscrepancyAdjustmentForm {
  operationalDate: string;
  accountingDate: string;
  reason: string;
  documentReference: string;
  notes: string;
  /** Surplus only: how the extra units are packed when they enter stock. */
  packaging: 'source' | 'definition' | 'measures';
  packagingId: string;
  weightKg: string;
  volumeM3: string;
  /** Surplus only, and only for people who can see costs. */
  costMode: 'none' | 'unit' | 'total';
  cost: string;
}

export type DiscrepancyRequest =
  | { action: 'claim'; discrepancy: TransferDiscrepancy; claimReference: string }
  | { action: 'release'; discrepancy: TransferDiscrepancy; notes: string; locationId: string }
  | {
      action: 'found' | 'dismiss' | 'origin-count';
      discrepancy: TransferDiscrepancy;
      notes: string;
    }
  | { action: 'adjust'; discrepancy: TransferDiscrepancy; form: DiscrepancyAdjustmentForm };

/** Today in the company's calendar, as `YYYY-MM-DD`. */
export function businessToday(now: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/El_Salvador',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).format(now);
}

const FRIENDLY_ERRORS: Record<string, string> = {
  transfer_discrepancy_has_adjustment:
    'Esta diferencia ya tiene un ajuste en curso. Termínalo o cancélalo desde el ajuste antes de resolverla de otra forma.',
  transfer_assignment_units_invalid:
    'Alguna unidad del borrador ya no está disponible para calcular la carga. Actualiza los saldos y revisa las cantidades.'
};

/** The message of a failed request; some codes get wording that says what to do next. */
export function transferErrorMessage(cause: unknown, fallback: string): string {
  const code = cause && typeof cause === 'object' ? (cause as { code?: unknown }).code : undefined;
  if (typeof code === 'string' && FRIENDLY_ERRORS[code]) return FRIENDLY_ERRORS[code];
  return cause instanceof Error ? cause.message : fallback;
}
