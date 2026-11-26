import { apiFetch } from '#lib/api/client.ts';
import type {
  DenominationLine,
  DepositShift,
  MovementKind,
  PointOfSaleOption,
  PosDeposit,
  PosDepositInput,
  PosMe,
  PosMovement,
  PosPerson,
  PosRegister,
  PosRegisterInput,
  PosShift,
  PosShiftDetail,
  PosShiftPage,
  ShiftStatus,
  SupervisorApproval
} from '#lib/types/pos.ts';

function query(params: Record<string, string | string[] | number | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (Array.isArray(value)) value.forEach((item) => search.append(key, item));
    else if (value !== null && value !== undefined && value !== '') search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

function post<T>(path: string, body: unknown, method = 'POST'): Promise<T> {
  return apiFetch<T>(path, { method, body: JSON.stringify(body) });
}

export interface ShiftQuery {
  branchId?: string | null;
  statuses?: ShiftStatus[];
  from?: string | null;
  to?: string | null;
  limit?: number;
  offset?: number;
}

/** Punto de venta (`pos:*`): cajas, turnos, efectivo, cierre ciego y depósitos. */
export const posApi = {
  me() {
    return apiFetch<PosMe>('/pos/me');
  },
  setPin(password: string, pin: string) {
    return post<void>('/pos/me/pin', { password, pin }, 'PUT');
  },
  supervisors(branchId: string) {
    return apiFetch<PosPerson[]>(`/pos/branches/${branchId}/supervisors`);
  },
  pointOfSaleOptions() {
    return apiFetch<PointOfSaleOption[]>('/pos/point-of-sale-options');
  },
  registers(branchId: string | null) {
    return apiFetch<PosRegister[]>(`/pos/registers${query({ branch_id: branchId })}`);
  },
  createRegister(pointOfSaleId: string, input: PosRegisterInput) {
    return post<PosRegister>('/pos/registers', { point_of_sale_id: pointOfSaleId, ...input });
  },
  updateRegister(id: string, version: number, input: PosRegisterInput) {
    return post<PosRegister>(
      `/pos/registers/${id}`,
      { ...input, expected_version: version },
      'PUT'
    );
  },
  openShift(
    registerId: string,
    denominations: DenominationLine[],
    notes: string | null,
    idempotencyKey: string
  ) {
    return post<PosShift>('/pos/shifts', {
      register_id: registerId,
      denominations,
      notes,
      idempotency_key: idempotencyKey
    });
  },
  shifts(params: ShiftQuery = {}) {
    return apiFetch<PosShiftPage>(
      `/pos/shifts${query({
        branch_id: params.branchId,
        status: params.statuses,
        from: params.from,
        to: params.to,
        limit: params.limit,
        offset: params.offset
      })}`
    );
  },
  shift(id: string) {
    return apiFetch<PosShiftDetail>(`/pos/shifts/${id}`);
  },
  addMovement(
    shiftId: string,
    input: {
      kind: MovementKind;
      amount: string;
      reason: string;
      reference: string | null;
      approval: SupervisorApproval | null;
      idempotency_key: string;
    }
  ) {
    return post<PosMovement>(`/pos/shifts/${shiftId}/movements`, input);
  },
  count(
    shiftId: string,
    input: {
      expected_version: number;
      denominations: DenominationLine[];
      declared_card: string;
      declared_transfer: string;
      notes: string | null;
    }
  ) {
    return post<PosShift>(`/pos/shifts/${shiftId}/count`, input);
  },
  recount(shiftId: string, version: number, reason: string) {
    return post<PosShift>(`/pos/shifts/${shiftId}/recount`, {
      expected_version: version,
      reason
    });
  },
  approve(shiftId: string, version: number, retainedFloat: string, notes: string | null) {
    return post<PosShift>(`/pos/shifts/${shiftId}/approve`, {
      expected_version: version,
      retained_float: retainedFloat,
      notes
    });
  },
  depositCandidates(branchId: string) {
    return apiFetch<DepositShift[]>(`/pos/deposits/candidates${query({ branch_id: branchId })}`);
  },
  deposits(branchId: string | null) {
    return apiFetch<PosDeposit[]>(`/pos/deposits${query({ branch_id: branchId })}`);
  },
  createDeposit(input: PosDepositInput) {
    return post<PosDeposit>('/pos/deposits', input);
  }
};
