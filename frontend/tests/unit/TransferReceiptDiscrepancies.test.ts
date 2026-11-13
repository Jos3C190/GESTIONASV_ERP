import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import TransferOperationsPage from '../../src/lib/features/inventory/components/TransferOperationsPage.svelte';
import type { InventoryTransfer } from '../../src/lib/features/inventory/transfer-documents';
import { makeDiscrepancy, makeLine, makeTransfer } from './fixtures/inventory-transfer';

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  list: vi.fn(),
  receive: vi.fn(),
  closeReception: vi.fn(),
  prepareDiscrepancyAdjustment: vi.fn(),
  claimDiscrepancy: vi.fn(),
  routeOptions: vi.fn(),
  pendingApprovalCount: vi.fn(),
  listLocations: vi.fn(),
  listTransferUnits: vi.fn(),
  listDemand: vi.fn(),
  listVehicles: vi.fn(),
  goto: vi.fn(),
  permissions: new Set<string>(),
  accessAllBranches: true,
  branches: [] as Array<{ id: string }>
}));
vi.mock('$app/navigation', () => ({ goto: mocks.goto }));
vi.mock('$lib/stores/company.svelte', () => ({ company: { id: 'company-1' } }));
vi.mock('$lib/stores/branch.svelte', () => ({
  branch: {
    id: null,
    ready: true,
    get accessAllBranches() {
      return mocks.accessAllBranches;
    },
    get branches() {
      return mocks.branches;
    }
  }
}));
vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: { hasPermission: (code: string) => mocks.permissions.has(code) }
}));
vi.mock('$lib/stores/session.svelte', () => ({
  session: { user: { id: 'user-receiver', is_superuser: false } }
}));
vi.mock('$lib/features/locations/services', () => ({ listLocations: mocks.listLocations }));
vi.mock('$lib/features/inventory/services', () => ({
  inventoryApi: {
    listTransferUnits: mocks.listTransferUnits,
    listPackaging: vi.fn().mockResolvedValue([])
  }
}));
vi.mock('$lib/features/inventory/transfer-documents', () => ({
  inventoryTransfersApi: {
    get: mocks.get,
    list: mocks.list,
    receive: mocks.receive,
    closeReception: mocks.closeReception,
    prepareDiscrepancyAdjustment: mocks.prepareDiscrepancyAdjustment,
    claimDiscrepancy: mocks.claimDiscrepancy,
    routeOptions: mocks.routeOptions,
    pendingApprovalCount: mocks.pendingApprovalCount,
    listDemand: mocks.listDemand,
    listVehicles: mocks.listVehicles
  }
}));

const location = {
  id: 'location-1',
  warehouse_id: 'destination',
  code: 'SEC-01',
  location_type: 'storage',
  lifecycle_status: 'active',
  storage_eligible: true,
  is_active: true
};

function inTransit(patch: Partial<InventoryTransfer> = {}): InventoryTransfer {
  return makeTransfer({
    status: 'in_transit',
    dispatched_at: '2026-10-19T12:01:00Z',
    destination_warehouse_id: 'destination',
    lines: [makeLine()],
    ...patch
  });
}

function show(transfer: InventoryTransfer) {
  mocks.get.mockResolvedValue(transfer);
  mocks.list.mockResolvedValue([transfer]);
}

async function openDocument() {
  render(TransferOperationsPage);
  await fireEvent.click(await screen.findByRole('button', { name: 'Documentos' }));
  await fireEvent.click(await screen.findByRole('button', { name: /TR-DEMO-A/ }));
}

beforeEach(() => {
  mocks.permissions = new Set([
    'inventory:read',
    'inventory:move',
    'inventory:receive',
    'inventory:adjust',
    'inventory:adjust_approve'
  ]);
  for (const mock of Object.values(mocks))
    if (typeof mock === 'function' && 'mockReset' in mock) mock.mockReset();
  mocks.routeOptions.mockResolvedValue({
    policy: { allow_branch_to_branch: true, allow_branch_to_central: true, require_approval: true },
    origins: [],
    destinations: []
  });
  mocks.pendingApprovalCount.mockResolvedValue(0);
  mocks.list.mockResolvedValue([]);
  mocks.listLocations.mockResolvedValue({ items: [location], meta: { pages: 1 } });
  mocks.listTransferUnits.mockResolvedValue([]);
  mocks.listDemand.mockResolvedValue([]);
  mocks.listVehicles.mockResolvedValue([]);
  mocks.accessAllBranches = true;
  mocks.branches = [];
  sessionStorage.clear();
});

describe('recepción con avería y sobrante', () => {
  it('una recepción sin declarar nada manda solo la cantidad y la ubicación', async () => {
    show(inTransit());
    mocks.receive.mockResolvedValue(inTransit());
    await openDocument();
    await fireEvent.input(await screen.findByLabelText('Cantidad contada ahora'), {
      target: { value: '3' }
    });
    await fireEvent.change(screen.getByLabelText('Ubicación de recepción / cuarentena'), {
      target: { value: 'location-1' }
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar cantidades recibidas' }));
    await waitFor(() => expect(mocks.receive).toHaveBeenCalledTimes(1));
    expect(mocks.receive).toHaveBeenCalledWith('transfer-a', expect.any(String), [
      { transfer_detail_id: 'line-1', destination_location_id: 'location-1', quantity_base: '3' }
    ]);
  });

  it('declara avería y sobrante por línea con su tipo, descripción y evidencia', async () => {
    show(inTransit());
    mocks.receive.mockResolvedValue(inTransit());
    await openDocument();
    const toggle = await screen.findByRole('checkbox', { name: 'Registrar avería o sobrante' });
    expect(screen.queryByLabelText('Cantidad con avería')).not.toBeInTheDocument();
    await fireEvent.click(toggle);

    await fireEvent.input(screen.getByLabelText('Cantidad contada ahora'), {
      target: { value: '2' }
    });
    await fireEvent.change(screen.getByLabelText('Ubicación de recepción / cuarentena'), {
      target: { value: 'location-1' }
    });
    await fireEvent.input(screen.getByLabelText('Cantidad con avería'), { target: { value: '1' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar cantidades recibidas' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Indica el tipo de avería de Producto de prueba y descríbela (mínimo 5 caracteres).'
    );
    expect(mocks.receive).not.toHaveBeenCalled();

    await fireEvent.change(screen.getByLabelText('Tipo de avería'), { target: { value: 'wet' } });
    await fireEvent.input(screen.getByLabelText('Describe el daño'), {
      target: { value: 'Cajas mojadas por la lluvia' }
    });
    await fireEvent.input(screen.getByLabelText('Cantidad sobrante'), { target: { value: '1' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar cantidades recibidas' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Describe el sobrante de Producto de prueba (mínimo 5 caracteres).'
    );
    await fireEvent.input(screen.getByLabelText('Describe el sobrante'), {
      target: { value: 'Una caja de otro lote' }
    });
    await fireEvent.input(screen.getByLabelText('Referencia de evidencia (opcional)'), {
      target: { value: 'FOTO-12' }
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar cantidades recibidas' }));
    await waitFor(() => expect(mocks.receive).toHaveBeenCalledTimes(1));
    expect(mocks.receive).toHaveBeenCalledWith('transfer-a', expect.any(String), [
      {
        transfer_detail_id: 'line-1',
        destination_location_id: 'location-1',
        quantity_base: '2',
        damaged_quantity: '1',
        damage_type: 'wet',
        damage_notes: 'Cajas mojadas por la lluvia',
        surplus_quantity: '1',
        surplus_notes: 'Una caja de otro lote',
        evidence_reference: 'FOTO-12'
      }
    ]);
  });

  it('no deja declarar sobrante si no se registra todo lo pendiente ni pasarse de lo pendiente', async () => {
    show(inTransit());
    await openDocument();
    await fireEvent.click(
      await screen.findByRole('checkbox', { name: 'Registrar avería o sobrante' })
    );
    await fireEvent.change(screen.getByLabelText('Ubicación de recepción / cuarentena'), {
      target: { value: 'location-1' }
    });
    await fireEvent.input(screen.getByLabelText('Cantidad contada ahora'), {
      target: { value: '1' }
    });
    await fireEvent.input(screen.getByLabelText('Cantidad sobrante'), { target: { value: '1' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar cantidades recibidas' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Declara sobrante de Producto de prueba solo cuando registras todo lo pendiente de la línea.'
    );
    await fireEvent.input(screen.getByLabelText('Cantidad contada ahora'), {
      target: { value: '2' }
    });
    await fireEvent.input(screen.getByLabelText('Cantidad con avería'), { target: { value: '2' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar cantidades recibidas' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      /no puede superar lo que falta por llegar: 3/
    );
    expect(mocks.receive).not.toHaveBeenCalled();
  });

  it('permite recibir solo mercadería averiada dejando vacía la cantidad buena', async () => {
    show(inTransit());
    mocks.receive.mockResolvedValue(inTransit());
    await openDocument();
    await fireEvent.click(
      await screen.findByRole('checkbox', { name: 'Registrar avería o sobrante' })
    );
    await fireEvent.change(screen.getByLabelText('Ubicación de recepción / cuarentena'), {
      target: { value: 'location-1' }
    });
    await fireEvent.input(screen.getByLabelText('Cantidad con avería'), { target: { value: '3' } });
    await fireEvent.change(screen.getByLabelText('Tipo de avería'), {
      target: { value: 'crushed' }
    });
    await fireEvent.input(screen.getByLabelText('Describe el daño'), {
      target: { value: 'Pallet aplastado' }
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar cantidades recibidas' }));
    await waitFor(() => expect(mocks.receive).toHaveBeenCalledTimes(1));
    expect(mocks.receive.mock.calls[0]![2][0]).toMatchObject({
      quantity_base: '0',
      damaged_quantity: '3',
      damage_type: 'crushed'
    });
  });
});

describe('recepción parcial', () => {
  const partial = () =>
    inTransit({
      status: 'partially_received',
      lines: [
        makeLine({
          quantity_received: '2',
          quantity_in_transit: '1',
          quantity_pending_reception: '1'
        })
      ]
    });

  it('pregunta si llegará el resto y deja seguir esperando', async () => {
    show(partial());
    await openDocument();
    expect(
      await screen.findByText('Recepción parcial: faltan 1 u por llegar. ¿Llegará el resto?')
    ).toBeInTheDocument();
    await fireEvent.click(
      screen.getByRole('button', { name: 'Registrar faltante y cerrar recepción' })
    );
    expect(await screen.findByLabelText('Motivo del faltante')).toHaveFocus();
    await fireEvent.click(screen.getByRole('button', { name: 'Seguir esperando' }));
    expect(screen.queryByLabelText('Motivo del faltante')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Cantidad contada ahora')).toHaveFocus();
    expect(mocks.closeReception).not.toHaveBeenCalled();
  });

  it('registra el faltante con su motivo y evidencia y avisa que quedó con discrepancia', async () => {
    const closed = inTransit({
      status: 'discrepancy',
      has_open_discrepancies: true,
      discrepancies: [makeDiscrepancy({ id: 'disc-short', kind: 'shortage', damage_type: null })]
    });
    show(partial());
    mocks.closeReception.mockResolvedValue(closed);
    await openDocument();
    await fireEvent.click(
      await screen.findByRole('button', { name: 'Registrar faltante y cerrar recepción' })
    );
    const confirm = screen.getByRole('button', { name: 'Confirmar faltante y cerrar' });
    expect(confirm).toBeDisabled();
    await fireEvent.input(screen.getByLabelText('Motivo del faltante'), {
      target: { value: 'El transportista confirma que no llevó el resto' }
    });
    await fireEvent.input(screen.getByLabelText('Referencia de evidencia (opcional)'), {
      target: { value: 'CORREO-3' }
    });
    show(closed);
    await fireEvent.click(confirm);
    await waitFor(() => expect(mocks.closeReception).toHaveBeenCalledTimes(1));
    expect(mocks.closeReception).toHaveBeenCalledWith('transfer-a', {
      reason: 'El transportista confirma que no llevó el resto',
      evidence_reference: 'CORREO-3',
      idempotency_key: expect.any(String)
    });
    expect(await screen.findByText(/quedó con discrepancia/)).toBeInTheDocument();
    expect(
      await screen.findByText('Con discrepancia: resuelve cada diferencia para cerrar el traslado.')
    ).toBeInTheDocument();
  });

  it('sin permiso de recepción no deja registrar el faltante', async () => {
    mocks.permissions.delete('inventory:receive');
    show(partial());
    await openDocument();
    expect(
      await screen.findByRole('button', { name: 'Registrar faltante y cerrar recepción' })
    ).toBeDisabled();
  });
});

describe('discrepancias en el detalle', () => {
  const withSurplus = () =>
    inTransit({
      status: 'discrepancy',
      has_open_discrepancies: true,
      origin_count_pending: true,
      lines: [
        makeLine({
          quantity_in_transit: '0',
          quantity_pending_reception: '0',
          quantity_received: '3'
        })
      ],
      discrepancies: [
        makeDiscrepancy({
          id: 'disc-extra',
          kind: 'surplus',
          damage_type: null,
          quantity: '1',
          notes: 'Llegó una caja de más',
          origin_count_required: true
        })
      ]
    });

  it('prepara el ajuste de ingreso de un sobrante y lleva al ajuste para adjuntar la evidencia', async () => {
    show(withSurplus());
    mocks.prepareDiscrepancyAdjustment.mockResolvedValue({ id: 'adj-9', code: 'AJ-9' });
    await openDocument();
    await fireEvent.click(
      await screen.findByRole('button', { name: 'Preparar ajuste de ingreso' })
    );
    await fireEvent.input(await screen.findByLabelText('Documento de respaldo (referencia)'), {
      target: { value: 'ACTA-77' }
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Crear borrador del ajuste' }));
    await waitFor(() => expect(mocks.prepareDiscrepancyAdjustment).toHaveBeenCalledTimes(1));
    expect(mocks.prepareDiscrepancyAdjustment).toHaveBeenCalledWith(
      'transfer-a',
      'disc-extra',
      expect.objectContaining({
        document_reference: 'ACTA-77',
        reason: 'Ingreso del sobrante del traslado TR-DEMO-A',
        idempotency_key: expect.any(String)
      })
    );
    await waitFor(() => expect(mocks.goto).toHaveBeenCalledWith('/inventory/adjustments/adj-9'));
  });

  it('muestra el error del servidor dentro del formulario si el ajuste no se pudo preparar', async () => {
    show(withSurplus());
    mocks.prepareDiscrepancyAdjustment.mockRejectedValue(
      new Error('Falta un costo promedio o documentado para valuar el ingreso.')
    );
    await openDocument();
    await fireEvent.click(
      await screen.findByRole('button', { name: 'Preparar ajuste de ingreso' })
    );
    await fireEvent.input(await screen.findByLabelText('Documento de respaldo (referencia)'), {
      target: { value: 'ACTA-77' }
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Crear borrador del ajuste' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/costo promedio o documentado/);
    expect(mocks.goto).not.toHaveBeenCalled();
  });

  it('registra un reclamo sobre una avería y vuelve a leer el traslado', async () => {
    const withDamage = inTransit({
      status: 'discrepancy',
      has_open_discrepancies: true,
      discrepancies: [makeDiscrepancy()]
    });
    const claimed = {
      ...withDamage,
      discrepancies: [makeDiscrepancy({ status: 'in_claim', claim_reference: 'REC-5' })]
    };
    show(withDamage);
    mocks.claimDiscrepancy.mockResolvedValue(claimed);
    await openDocument();
    await fireEvent.click(await screen.findByRole('button', { name: 'Registrar reclamo' }));
    await fireEvent.input(await screen.findByLabelText('Referencia del reclamo'), {
      target: { value: 'REC-5' }
    });
    show(claimed);
    await fireEvent.click(screen.getByRole('button', { name: 'Guardar reclamo' }));
    await waitFor(() =>
      expect(mocks.claimDiscrepancy).toHaveBeenCalledWith('transfer-a', 'disc-1', {
        idempotency_key: expect.any(String),
        claim_reference: 'REC-5'
      })
    );
    expect(await screen.findByText(/En reclamo: REC-5/)).toBeInTheDocument();
  });

  it('muestra la insignia y filtra la lista por conteo pendiente en origen', async () => {
    show(withSurplus());
    render(TransferOperationsPage);
    await fireEvent.click(await screen.findByRole('button', { name: 'Documentos' }));
    expect(await screen.findAllByText('Conteo pendiente en origen')).not.toHaveLength(0);
    await fireEvent.click(screen.getByLabelText('Conteo pendiente en origen'));
    await waitFor(() =>
      expect(mocks.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ originCountPending: true })
      )
    );
  });
});

describe('lado de destino y unidades comprometidas', () => {
  it('quien no cubre la sucursal de destino no puede registrar la recepción ni cerrarla', async () => {
    mocks.accessAllBranches = false;
    mocks.branches = [{ id: 'other-branch' }];
    show(
      inTransit({
        status: 'partially_received',
        destination_branch_id: 'branch',
        lines: [
          makeLine({
            quantity_received: '2',
            quantity_in_transit: '1',
            quantity_pending_reception: '1'
          })
        ]
      })
    );
    await openDocument();
    expect(
      await screen.findByText(
        /Solo quien tiene acceso a la sucursal de destino puede registrar la recepción/
      )
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Registrar faltante y cerrar recepción' })
    ).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Confirmar cantidades recibidas' })).toBeDisabled();
    expect(screen.getByRole('checkbox', { name: 'Registrar avería o sobrante' })).toBeDisabled();
  });

  it('con acceso al destino la casilla de avería informa si está desplegada', async () => {
    show(inTransit());
    await openDocument();
    const toggle = await screen.findByRole('checkbox', { name: 'Registrar avería o sobrante' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(toggle).not.toHaveAttribute('aria-controls');
    await fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(toggle).toHaveAttribute('aria-controls', 'receipt-extras-line-1');
    expect(document.getElementById('receipt-extras-line-1')).not.toBeNull();
  });

  it('el detalle de una línea muestra solo las partes que no son cero', async () => {
    show(
      inTransit({
        lines: [
          makeLine({
            quantity_received_damaged: '2',
            quantity_surplus: '0',
            quantity_short_open: '0'
          })
        ]
      })
    );
    await openDocument();
    expect(await screen.findByText('Con avería 2')).toBeInTheDocument();
    expect(screen.queryByText(/Sobrante 0/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Faltante por resolver/)).not.toBeInTheDocument();
  });

  it('la bandeja por aprobar no arrastra el filtro de conteo pendiente en origen', async () => {
    mocks.permissions.add('inventory:transfer_approve');
    mocks.pendingApprovalCount.mockResolvedValue(1);
    show(inTransit());
    render(TransferOperationsPage);
    await fireEvent.click(await screen.findByRole('button', { name: 'Documentos' }));
    await fireEvent.click(await screen.findByLabelText('Conteo pendiente en origen'));
    await waitFor(() =>
      expect(mocks.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ originCountPending: true })
      )
    );
    await fireEvent.click(screen.getByRole('button', { name: 'Por aprobar (1)' }));
    await waitFor(() =>
      expect(mocks.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ awaitingMyApproval: true, originCountPending: undefined })
      )
    );
    expect(screen.getByLabelText('Conteo pendiente en origen')).not.toBeChecked();
  });

  it('en la preparación, una unidad comprometida en otro traslado no se ofrece como disponible', async () => {
    const central = {
      id: 'wh-central',
      code: 'BOD-C',
      name: 'Bodega Central',
      branch_id: 'branch-matrix',
      branch_name: 'Casa matriz',
      is_central: true
    };
    mocks.routeOptions.mockImplementation(async (origin?: string) => ({
      policy: {
        allow_branch_to_branch: true,
        allow_branch_to_central: true,
        require_approval: true
      },
      origins: [central],
      destinations: origin
        ? [
            {
              id: 'wh-north',
              code: 'BOD-N',
              name: 'Bodega Norte',
              branch_id: 'branch-north',
              branch_name: 'Sucursal Norte',
              is_central: false,
              route_type: 'central_distribution'
            }
          ]
        : []
    }));
    const unit = (id: string, code: string, committed: string | null) => ({
      id,
      code,
      product_id: 1,
      inventory_item_id: 'item-1',
      base_unit_id: 1,
      base_unit_symbol: 'u',
      base_unit_name: 'Unidad',
      product_name: 'Producto de prueba',
      product_sku: 'SKU-DEMO',
      quantity_base: '10.000000',
      lot_code: null,
      receipt_lot_code: null,
      committed_transfer_code: committed
    });
    mocks.listTransferUnits.mockResolvedValue([
      unit('hu-1', 'HU-LIBRE', null),
      unit('hu-2', 'HU-RESERVADA', 'TR-0099')
    ]);
    render(TransferOperationsPage);
    await fireEvent.click(await screen.findByRole('button', { name: /Producto de prueba/ }));
    await fireEvent.click(await screen.findByRole('button', { name: 'Envío manual' }));
    expect(await screen.findByText(/Comprometida en TR-0099 10/)).toBeInTheDocument();
    const reserved = screen.getByRole('checkbox', { name: /HU-RESERVADA/ });
    expect(reserved).toBeDisabled();
    expect(screen.getByRole('checkbox', { name: /HU-LIBRE/ })).toBeEnabled();
    expect(screen.getByText(/Disponible 10/)).toBeInTheDocument();
  });
});

describe('cierre con ajuste', () => {
  it('el aviso de cierre cuenta lo que pasó con cada diferencia en lugar de hablar solo de pérdidas', async () => {
    show(
      inTransit({
        status: 'closed_with_adjustment',
        received_at: '2026-10-21T10:00:00Z',
        lines: [
          makeLine({
            quantity_in_transit: '0',
            quantity_pending_reception: '0',
            quantity_received: '3'
          })
        ],
        discrepancies: [
          makeDiscrepancy({ id: 'd-a', status: 'in_claim', claim_reference: 'REC-1' }),
          makeDiscrepancy({
            id: 'd-b',
            kind: 'surplus',
            damage_type: null,
            status: 'resolved',
            resolution: 'regularized'
          })
        ]
      })
    );
    await openDocument();
    expect(
      await screen.findByText(
        /Traslado cerrado con ajuste: 1 avería en reclamo · 1 sobrante regularizado\./
      )
    ).toBeInTheDocument();
    expect(screen.queryByText(/ninguna pérdida se contó como recibida/)).not.toBeInTheDocument();
  });

  it('los textos de confirmación terminan en punto', async () => {
    mocks.permissions.add('inventory:transfer_approve');
    show(
      makeTransfer({
        status: 'pending_approval',
        requires_approval: true,
        route_type: 'branch_to_branch',
        created_by_id: 'someone-else',
        vehicle: { id: 'v', code: 'FL-1', name: 'Hiace', status: 'active', plate: 'C 1' },
        driver: { id: 'd', name: 'Carlos', employee_code: 'E-1' }
      })
    );
    await openDocument();
    await fireEvent.click(await screen.findByRole('button', { name: 'Aprobar traslado' }));
    expect(await screen.findByText(/antes de dejarlo listo para despachar.$/)).toBeInTheDocument();
  });
});
