import { fireEvent, render, screen, waitFor, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { posApi } = vi.hoisted(() => ({
  posApi: {
    me: vi.fn(),
    shift: vi.fn(),
    registers: vi.fn(),
    openShift: vi.fn(),
    addMovement: vi.fn(),
    count: vi.fn(),
    supervisors: vi.fn(),
    approve: vi.fn(),
    recount: vi.fn(),
    setPin: vi.fn()
  }
}));
vi.mock('#lib/api/pos.ts', () => ({ posApi }));
vi.mock('#lib/stores/branch.svelte.ts', () => ({
  branch: { id: 'b1', label: 'Centro', branches: [] }
}));
vi.mock('#lib/stores/company.svelte.ts', () => ({
  company: { id: 'c1', active: { id: 'c1', name: 'Panadería', commercial_name: 'Panadería' } }
}));

import { permissions } from '#lib/stores/permissions.svelte.ts';
import { session } from '#lib/stores/session.svelte.ts';
import type { PosRegister, PosShift, PosShiftDetail } from '#lib/types/pos.ts';
import PosWorkspace from './PosWorkspace.svelte';
import ShiftReview from './ShiftReview.svelte';
import { centsToAmount, countTotalCents, emptyCount, toCents } from './format.ts';
import { hasOnlyPosModules, isPosWorkspace } from './workspace.ts';

const CASHIER = [
  'pos:sell',
  'pos:shift_open',
  'pos:shift_close',
  'pos:cash_movements',
  'pos:reprint'
];
const SUPERVISOR = [...CASHIER, 'pos:supervise', 'pos:showcase', 'pos:reports', 'pos:deposits'];

function register(extra: Partial<PosRegister> = {}): PosRegister {
  return {
    id: 'r1',
    branch_id: 'b1',
    branch_name: 'Centro',
    establishment_code: 'M001',
    point_of_sale_id: 'p1',
    point_of_sale_code: 'P001',
    code: 'CAJA-01',
    name: 'Caja principal',
    opening_float: '50.00',
    cash_out_approval_threshold: '20.00',
    cash_drawer_limit: null,
    is_active: true,
    version: 1,
    created_at: '2026-11-26T14:00:00Z',
    updated_at: '2026-11-26T14:00:00Z',
    unclosed_shift_id: null,
    unclosed_shift_cashier: null,
    has_shifts: false,
    ...extra
  };
}

function shift(extra: Partial<PosShift> = {}): PosShift {
  return {
    id: 's1',
    number: 7,
    code: 'TUR-000007',
    branch_id: 'b1',
    branch_name: 'Centro',
    register_id: 'r1',
    register_code: 'CAJA-01',
    register_name: 'Caja principal',
    cashier: { id: 'u-cashier', name: 'Ana Pérez' },
    status: 'open',
    opening_float: '50.00',
    opened_at: '2026-11-26T14:00:00Z',
    counted_at: null,
    recount_reason: null,
    closed_at: null,
    approved_by: null,
    approval_notes: null,
    counted_cash: null,
    declared_card: null,
    declared_transfer: null,
    expected_cash: null,
    cash_difference: null,
    expected_card: null,
    expected_transfer: null,
    retained_float: null,
    cash_to_deposit: null,
    deposit_id: null,
    deposit_number: null,
    version: 1,
    amounts_visible: false,
    ...extra
  };
}

function detail(current: PosShift, totals: PosShiftDetail['totals'] = null): PosShiftDetail {
  return {
    shift: current,
    register_detail: register({ has_shifts: true }),
    movements: [],
    counts: [],
    totals,
    drawer_limit_reached: false
  };
}

beforeEach(() => {
  for (const fn of Object.values(posApi)) fn.mockReset();
  permissions.set(CASHIER, false);
});

describe('formato del arqueo', () => {
  it('suma por denominación en centavos y valida montos', () => {
    const lines = emptyCount().map((line) =>
      line.denomination === '20.00' && line.form === 'bill'
        ? { ...line, quantity: 2 }
        : line.denomination === '0.10'
          ? { ...line, quantity: 3 }
          : line
    );
    expect(centsToAmount(countTotalCents(lines))).toBe('40.30');
    expect(toCents('12,5')).toBe(1250);
    expect(toCents('1.005')).toBeNull();
    expect(centsToAmount(-150)).toBe('-1.50');
  });
});

describe('quién trabaja en la caja a pantalla completa', () => {
  it('el cajero sí; el supervisor entra a la caja con su menú; el administrador no', () => {
    permissions.set(CASHIER, false);
    expect(isPosWorkspace(permissions)).toBe(true);
    permissions.set(SUPERVISOR, false);
    expect(isPosWorkspace(permissions)).toBe(false);
    expect(hasOnlyPosModules(permissions)).toBe(true);
    permissions.set([...CASHIER, 'sales:read'], false);
    expect(isPosWorkspace(permissions)).toBe(false);
    expect(hasOnlyPosModules(permissions)).toBe(false);
    permissions.set([], true);
    expect(isPosWorkspace(permissions)).toBe(false);
  });
});

describe('caja del cajero', () => {
  it('abre el turno con el fondo contado y pide explicación si no coincide', async () => {
    posApi.me.mockResolvedValue({
      user: { id: 'u-cashier', name: 'Ana Pérez' },
      shift: null,
      has_pin: false,
      can_supervise: false
    });
    posApi.registers.mockResolvedValue([
      register(),
      register({
        id: 'r2',
        code: 'CAJA-02',
        unclosed_shift_id: 'x',
        unclosed_shift_cashier: 'Luis'
      })
    ]);
    posApi.openShift.mockResolvedValue(shift());
    render(PosWorkspace);

    expect(await screen.findByText('Abrir turno')).toBeInTheDocument();
    expect(screen.getByText('En uso por Luis')).toBeInTheDocument();
    const twenties = screen.getAllByRole('button', { name: 'Agregar un billete de $20' })[0]!;
    await fireEvent.click(twenties);
    await fireEvent.click(twenties);
    const open = screen.getByRole('button', { name: 'Abrir turno en CAJA-01' });
    expect(open).toBeDisabled();
    expect(screen.getByText(/explica la diferencia para abrir/i)).toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: 'Agregar un billete de $10' }));
    expect(screen.getByTestId('count-total')).toHaveTextContent('$50.00');
    expect(open).toBeEnabled();
    await fireEvent.click(open);
    await waitFor(() => expect(posApi.openShift).toHaveBeenCalledTimes(1));
    const [registerId, lines, notes, key] = posApi.openShift.mock.calls[0]!;
    expect(registerId).toBe('r1');
    expect(lines).toEqual([
      { form: 'bill', denomination: '20.00', quantity: 2 },
      { form: 'bill', denomination: '10.00', quantity: 1 }
    ]);
    expect(notes).toBeNull();
    expect(String(key)).toMatch(/^apertura-/);
  });

  it('pide supervisor para una salida sobre el tope y entrega el conteo sin mostrar el esperado', async () => {
    const current = shift();
    posApi.me.mockResolvedValue({
      user: { id: 'u-cashier', name: 'Ana Pérez' },
      shift: current,
      has_pin: false,
      can_supervise: false
    });
    posApi.shift.mockResolvedValue(detail(current));
    posApi.supervisors.mockResolvedValue([{ id: 'u-sup', name: 'Marta Ruiz' }]);
    posApi.addMovement.mockResolvedValue({
      id: 'm1',
      kind: 'cash_out',
      amount: '25.00',
      reason: 'Compra de bolsas',
      reference: null,
      authorized_by: { id: 'u-sup', name: 'Marta Ruiz' },
      created_by: { id: 'u-cashier', name: 'Ana Pérez' },
      created_at: '2026-11-26T15:00:00Z'
    });
    posApi.count.mockResolvedValue(shift({ status: 'counted', counted_cash: '50.00', version: 2 }));
    render(PosWorkspace);

    await fireEvent.click(await screen.findByRole('button', { name: /salida de efectivo/i }));
    const dialog = screen.getByRole('dialog');
    await fireEvent.input(within(dialog).getByPlaceholderText('0.00'), { target: { value: '25' } });
    await fireEvent.input(within(dialog).getByPlaceholderText('Compra de bolsas'), {
      target: { value: 'Compra de bolsas' }
    });
    expect(await within(dialog).findByText('Autorización del supervisor')).toBeInTheDocument();
    const save = within(dialog).getByRole('button', { name: 'Registrar' });
    expect(save).toBeDisabled();
    await fireEvent.input(within(dialog).getByLabelText('PIN del supervisor'), {
      target: { value: '482915' }
    });
    expect(save).toBeEnabled();
    await fireEvent.click(save);
    await waitFor(() => expect(posApi.addMovement).toHaveBeenCalledTimes(1));
    expect(posApi.addMovement.mock.calls[0]![1]).toMatchObject({
      kind: 'cash_out',
      amount: '25.00',
      approval: { supervisor_id: 'u-sup', pin: '482915' }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Contar y entregar turno' }));
    const countDialog = await screen.findByRole('dialog', { name: 'Contar y entregar el turno' });
    expect(within(countDialog).queryByText(/esperado/i)).not.toBeInTheDocument();
    await fireEvent.click(within(countDialog).getByRole('button', { name: 'Entregar conteo' }));
    await fireEvent.click(within(countDialog).getByRole('button', { name: 'Sí, entregar conteo' }));
    await waitFor(() => expect(posApi.count).toHaveBeenCalledTimes(1));
    expect(posApi.count.mock.calls[0]![1]).toMatchObject({
      expected_version: 1,
      declared_card: '0.00',
      declared_transfer: '0.00'
    });
  });
});

describe('revisión del supervisor', () => {
  const totals = {
    opening_float: '50.00',
    cash_in: '0.00',
    cash_out: '0.00',
    safe_drops: '0.00',
    cash_sales: '0.00',
    cash_refunds: '0.00',
    card_sales: '0.00',
    card_refunds: '0.00',
    transfer_sales: '0.00',
    transfer_refunds: '0.00',
    expected_cash: '50.00',
    expected_card: '0.00',
    expected_transfer: '0.00'
  };

  it('una diferencia exige explicación antes de aprobar', async () => {
    permissions.set(SUPERVISOR, false);
    session.setUser({ id: 'u-sup', username: 'marta', email: 'm@example.com' } as never);
    const counted = shift({
      status: 'counted',
      counted_cash: '48.50',
      declared_card: '0.00',
      declared_transfer: '0.00',
      expected_cash: '50.00',
      amounts_visible: true,
      version: 3
    });
    posApi.shift.mockResolvedValue(detail(counted, totals));
    posApi.approve.mockResolvedValue({ ...counted, status: 'closed' });
    render(ShiftReview, { shiftId: 's1', onclose: vi.fn(), onchanged: vi.fn() });

    expect(await screen.findByText('Faltante de $1.50')).toBeInTheDocument();
    const approve = screen.getByRole('button', { name: 'Aprobar cierre' });
    expect(approve).toBeDisabled();
    await fireEvent.input(screen.getByLabelText('Explicación de la diferencia'), {
      target: { value: 'Vuelto mal dado' }
    });
    expect(approve).toBeEnabled();
    await fireEvent.click(approve);
    await waitFor(() =>
      expect(posApi.approve).toHaveBeenCalledWith('s1', 3, '48.50', 'Vuelto mal dado')
    );
  });

  it('el supervisor no revisa su propio turno', async () => {
    permissions.set(SUPERVISOR, false);
    session.setUser({ id: 'u-cashier', username: 'ana', email: 'a@example.com' } as never);
    const counted = shift({ status: 'counted', counted_cash: '50.00', amounts_visible: true });
    posApi.shift.mockResolvedValue(detail(counted, totals));
    render(ShiftReview, { shiftId: 's1', onclose: vi.fn(), onchanged: vi.fn() });

    expect(await screen.findByText(/otro supervisor debe revisarlo/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Aprobar cierre' })).not.toBeInTheDocument();
  });
});
