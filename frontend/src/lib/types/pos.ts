/** Punto de venta: cajas, turnos, efectivo, arqueo y depósitos (V6a). Montos como texto decimal. */

export type ShiftStatus = 'open' | 'counted' | 'recount' | 'closed';
export type MovementKind = 'cash_in' | 'cash_out' | 'safe_drop';
export type DenominationForm = 'coin' | 'bill';

export interface PosPerson {
  id: string;
  name: string;
}

export interface PosRegister {
  id: string;
  branch_id: string;
  branch_name: string;
  establishment_code: string;
  point_of_sale_id: string;
  point_of_sale_code: string;
  code: string;
  name: string;
  opening_float: string;
  cash_out_approval_threshold: string;
  cash_drawer_limit: string | null;
  is_active: boolean;
  version: number;
  created_at: string;
  updated_at: string;
  unclosed_shift_id: string | null;
  unclosed_shift_cashier: string | null;
  has_shifts: boolean;
}

export interface PosRegisterInput {
  code: string;
  name: string;
  opening_float: string;
  cash_out_approval_threshold: string;
  cash_drawer_limit: string | null;
  is_active: boolean;
}

export interface PointOfSaleOption {
  id: string;
  code: string;
  name: string;
  establishment_code: string;
  branch_id: string;
  branch_name: string;
  available: boolean;
  unavailable_reason: string | null;
}

export interface DenominationLine {
  form: DenominationForm;
  denomination: string;
  quantity: number;
}

export interface DenominationCountOut extends DenominationLine {
  amount: string;
}

export interface SupervisorApproval {
  supervisor_id: string;
  pin: string;
}

export interface PosShift {
  id: string;
  number: number;
  code: string;
  branch_id: string;
  branch_name: string;
  register_id: string;
  register_code: string;
  register_name: string;
  cashier: PosPerson;
  status: ShiftStatus;
  opening_float: string;
  opened_at: string;
  counted_at: string | null;
  recount_reason: string | null;
  closed_at: string | null;
  approved_by: PosPerson | null;
  approval_notes: string | null;
  counted_cash: string | null;
  declared_card: string | null;
  declared_transfer: string | null;
  expected_cash: string | null;
  cash_difference: string | null;
  expected_card: string | null;
  expected_transfer: string | null;
  retained_float: string | null;
  cash_to_deposit: string | null;
  deposit_id: string | null;
  deposit_number: number | null;
  version: number;
  amounts_visible: boolean;
}

export interface PosMovement {
  id: string;
  kind: MovementKind;
  amount: string;
  reason: string;
  reference: string | null;
  authorized_by: PosPerson | null;
  created_by: PosPerson;
  created_at: string;
}

export interface PosCount {
  id: string;
  kind: 'opening' | 'closing';
  sequence: number;
  cash_total: string;
  card_total: string | null;
  transfer_total: string | null;
  notes: string | null;
  counted_by: PosPerson;
  counted_at: string;
  denominations: DenominationCountOut[];
}

export interface PosShiftTotals {
  opening_float: string;
  cash_in: string;
  cash_out: string;
  safe_drops: string;
  cash_sales: string;
  cash_refunds: string;
  card_sales: string;
  card_refunds: string;
  transfer_sales: string;
  transfer_refunds: string;
  expected_cash: string;
  expected_card: string;
  expected_transfer: string;
}

export interface PosShiftDetail {
  shift: PosShift;
  register_detail: PosRegister;
  movements: PosMovement[];
  counts: PosCount[];
  totals: PosShiftTotals | null;
  drawer_limit_reached: boolean;
}

export interface PosShiftPage {
  items: PosShift[];
  total: number;
  limit: number;
  offset: number;
}

export interface PosMe {
  user: PosPerson;
  shift: PosShift | null;
  has_pin: boolean;
  can_supervise: boolean;
}

export interface DepositShift {
  shift_id: string;
  shift_number: number;
  shift_code: string;
  register_code: string;
  cashier_name: string;
  closed_at: string | null;
  amount: string;
}

export interface PosDeposit {
  id: string;
  number: number;
  code: string;
  branch_id: string;
  branch_name: string;
  deposited_on: string;
  bank_name: string;
  account_reference: string;
  slip_number: string;
  expected_amount: string;
  deposited_amount: string;
  difference: string;
  notes: string | null;
  created_by_name: string;
  created_at: string;
  shifts: DepositShift[];
}

export interface PosDepositInput {
  branch_id: string;
  shift_ids: string[];
  deposited_on: string;
  bank_name: string;
  account_reference: string;
  slip_number: string;
  deposited_amount: string;
  notes: string | null;
  idempotency_key: string;
}
