export interface PutawaySourceUnit {
  id: string;
  code: string;
  pending_quantity_base: string | number;
}

export interface PutawayDestinationPlan {
  destination_location_id: string;
  quantity_base: string;
}

export interface PutawayAllocation {
  handling_unit_id: string;
  destination_location_id: string;
  quantity_base: string;
}

const SCALE = 1_000_000n;

function toMicrounits(value: string | number): bigint | null {
  if (typeof value === 'number' && (!Number.isFinite(value) || value < 0)) return null;
  const raw = String(value).trim();
  const match = /^(\d{1,18})(?:\.(\d{1,6}))?$/.exec(raw);
  if (!match) return null;
  const wholeDigits = match[1];
  if (wholeDigits === undefined) return null;
  const whole = BigInt(wholeDigits);
  const fraction = BigInt((match[2] ?? '').padEnd(6, '0') || '0');
  return whole * SCALE + fraction;
}

function fromMicrounits(value: bigint): string {
  const whole = value / SCALE;
  const fraction = String(value % SCALE)
    .padStart(6, '0')
    .replace(/0+$/, '');
  return fraction ? `${whole}.${fraction}` : String(whole);
}

/**
 * Expands a product-level plan into HU-level movements without exceeding the
 * pending quantity of any source unit. The same source HU may appear more than
 * once when a single physical unit is split across destinations.
 */
export function buildPutawayAllocations(
  sourceUnits: readonly PutawaySourceUnit[],
  destinationPlan: readonly PutawayDestinationPlan[]
): { allocations: PutawayAllocation[]; error: null } | { allocations: null; error: string } {
  const sources = sourceUnits
    .map((unit) => ({
      id: unit.id,
      code: unit.code,
      remaining: toMicrounits(unit.pending_quantity_base)
    }))
    .sort((left, right) => left.code.localeCompare(right.code, 'es-SV'));

  if (sources.some((source) => source.remaining == null)) {
    return { allocations: null, error: 'Una unidad pendiente tiene una cantidad inválida.' };
  }

  const pendingTotal = sources.reduce((total, source) => total + (source.remaining ?? 0n), 0n);
  const allocations: PutawayAllocation[] = [];

  for (const destination of destinationPlan) {
    const locationId = destination.destination_location_id.trim();
    const requested = toMicrounits(destination.quantity_base);
    if (!locationId) {
      return { allocations: null, error: 'Seleccione una ubicación para cada cantidad.' };
    }
    if (requested == null || requested <= 0n) {
      return {
        allocations: null,
        error: 'Cada cantidad a ubicar debe ser mayor que cero y tener hasta seis decimales.'
      };
    }

    let remaining = requested;
    for (const source of sources) {
      if (remaining === 0n) break;
      const available = source.remaining ?? 0n;
      if (available <= 0n) continue;
      const assigned = available < remaining ? available : remaining;
      allocations.push({
        handling_unit_id: source.id,
        destination_location_id: locationId,
        quantity_base: fromMicrounits(assigned)
      });
      source.remaining = available - assigned;
      remaining -= assigned;
    }
    if (remaining > 0n) {
      return {
        allocations: null,
        error: `La cantidad del plan supera las ${fromMicrounits(pendingTotal)} unidades base pendientes.`
      };
    }
  }

  if (allocations.length === 0) {
    return { allocations: null, error: 'Agregue al menos una ubicación y una cantidad.' };
  }

  return { allocations, error: null };
}

export function sumBaseQuantities(values: readonly (string | number)[]): string | null {
  let total = 0n;
  for (const value of values) {
    const parsed = toMicrounits(value);
    if (parsed == null) return null;
    total += parsed;
  }
  return fromMicrounits(total);
}

export function subtractBaseQuantities(
  left: string | number,
  right: string | number
): string | null {
  const leftValue = toMicrounits(left);
  const rightValue = toMicrounits(right);
  if (leftValue == null || rightValue == null || rightValue > leftValue) return null;
  return fromMicrounits(leftValue - rightValue);
}
