import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiFetchMock = vi.hoisted(() => vi.fn());
vi.mock('$lib/api/client', () => ({ apiFetch: apiFetchMock }));

import { inventoryTransfersApi } from './transfer-documents';

describe('inventoryTransfersApi', () => {
  beforeEach(() => vi.resetAllMocks());

  it('consulta la demanda por sucursal y respeta el límite contractual', async () => {
    apiFetchMock.mockResolvedValue([]);
    await inventoryTransfersApi.listDemand('branch / 1', 42);
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/inventory/transfers/demand?branch_id=branch+%2F+1&limit=1000&product_id=42'
    );
  });

  it('edita preparaciones con PUT, según el router B03', async () => {
    apiFetchMock.mockResolvedValue({ id: 'transfer-1' });
    const body = {
      idempotency_key: 'attempt-123',
      origin_warehouse_id: 'origin',
      destination_warehouse_id: 'destination',
      vehicle_id: 'vehicle-1',
      driver_id: 'driver-1',
      notes: null,
      lines: [{ handling_unit_id: 'hu-1', quantity_base: '2.25' }]
    };
    await inventoryTransfersApi.update('transfer / 1', body);
    expect(apiFetchMock).toHaveBeenCalledWith('/inventory/transfers/transfer%20%2F%201', {
      method: 'PUT',
      body: JSON.stringify(body)
    });
  });

  it('envía solo las cantidades y ubicaciones parciales confirmadas, sin autocompletar remanentes', async () => {
    apiFetchMock.mockResolvedValue({ id: 'transfer-1' });
    const lines = [
      {
        transfer_detail_id: 'detail-1',
        destination_location_id: 'quarantine-1',
        quantity_base: '8'
      }
    ];
    await inventoryTransfersApi.receive('transfer-1', 'receive-attempt-1', lines);
    expect(apiFetchMock).toHaveBeenCalledWith('/inventory/transfers/transfer-1/receive', {
      method: 'POST',
      body: JSON.stringify({ idempotency_key: 'receive-attempt-1', lines })
    });
  });
  it('filtra la lista por ruta, lado y bandeja de aprobación', async () => {
    apiFetchMock.mockResolvedValue([]);
    await inventoryTransfersApi.list({
      status: 'pending_approval',
      routeType: 'branch_to_branch',
      side: 'origin',
      awaitingMyApproval: true,
      page: 2
    });
    expect(apiFetchMock).toHaveBeenCalledWith(
      '/inventory/transfers?page=2&size=50&status=pending_approval&route_type=branch_to_branch&side=origin&awaiting_my_approval=true'
    );
    await inventoryTransfersApi.list();
    expect(apiFetchMock).toHaveBeenLastCalledWith('/inventory/transfers?page=1&size=50');
  });

  it('lee y guarda las reglas de la empresa', async () => {
    apiFetchMock.mockResolvedValue({});
    await inventoryTransfersApi.settings();
    expect(apiFetchMock).toHaveBeenLastCalledWith('/inventory/transfers/settings');
    const flags = {
      allow_branch_to_branch: true,
      allow_branch_to_central: false,
      require_approval: true
    };
    await inventoryTransfersApi.saveSettings(flags);
    expect(apiFetchMock).toHaveBeenLastCalledWith('/inventory/transfers/settings', {
      method: 'PUT',
      body: JSON.stringify(flags)
    });
  });

  it('consulta orígenes y destinos permitidos por separado', async () => {
    apiFetchMock.mockResolvedValue({ policy: {}, origins: [], destinations: [] });
    await inventoryTransfersApi.routeOptions();
    expect(apiFetchMock).toHaveBeenLastCalledWith('/inventory/transfers/route-options');
    await inventoryTransfersApi.routeOptions('origin / 1');
    expect(apiFetchMock).toHaveBeenLastCalledWith(
      '/inventory/transfers/route-options?origin_warehouse_id=origin+%2F+1'
    );
  });

  it('devuelve solo el número de traslados por aprobar', async () => {
    apiFetchMock.mockResolvedValue({ count: 4 });
    await expect(inventoryTransfersApi.pendingApprovalCount()).resolves.toBe(4);
    expect(apiFetchMock).toHaveBeenCalledWith('/inventory/transfers/pending-approval-count');
  });

  it('envía, retira, aprueba y rechaza con la ronda que la persona vio', async () => {
    apiFetchMock.mockResolvedValue({ id: 'transfer-1' });
    await inventoryTransfersApi.submit('transfer-1', 'key-submit-1');
    expect(apiFetchMock).toHaveBeenLastCalledWith('/inventory/transfers/transfer-1/submit', {
      method: 'POST',
      body: JSON.stringify({ idempotency_key: 'key-submit-1' })
    });
    await inventoryTransfersApi.withdraw('transfer-1', 'key-withdraw-1');
    expect(apiFetchMock).toHaveBeenLastCalledWith('/inventory/transfers/transfer-1/withdraw', {
      method: 'POST',
      body: JSON.stringify({ idempotency_key: 'key-withdraw-1' })
    });
    await inventoryTransfersApi.approve('transfer-1', 'key-approve-1', 3);
    expect(apiFetchMock).toHaveBeenLastCalledWith('/inventory/transfers/transfer-1/approve', {
      method: 'POST',
      body: JSON.stringify({ idempotency_key: 'key-approve-1', expected_round: 3 })
    });
    await inventoryTransfersApi.reject('transfer-1', 'key-reject-1', 3, 'Falta el sello');
    expect(apiFetchMock).toHaveBeenLastCalledWith('/inventory/transfers/transfer-1/reject', {
      method: 'POST',
      body: JSON.stringify({
        idempotency_key: 'key-reject-1',
        expected_round: 3,
        reason: 'Falta el sello'
      })
    });
  });

  describe('transporte, recepción y discrepancias', () => {
    beforeEach(() => {
      apiFetchMock.mockResolvedValue({ id: 'transfer-1' });
    });

    it('consulta las opciones de transporte con el origen y el traslado en edición', async () => {
      await inventoryTransfersApi.assignmentOptions('origin / 1', 'transfer-1');
      expect(apiFetchMock).toHaveBeenCalledWith(
        '/inventory/transfers/assignment-options?origin_warehouse_id=origin+%2F+1&transfer_id=transfer-1'
      );
      await inventoryTransfersApi.assignmentOptions('origin-1');
      expect(apiFetchMock).toHaveBeenLastCalledWith(
        '/inventory/transfers/assignment-options?origin_warehouse_id=origin-1'
      );
    });

    it('revisa el transporte de un borrador y el del traslado guardado', async () => {
      await inventoryTransfersApi.assignmentCheck({
        origin_warehouse_id: 'origin',
        vehicle_id: 'vehicle',
        driver_id: '',
        lines: [{ handling_unit_id: 'hu-1', quantity_base: '2' }]
      });
      expect(apiFetchMock).toHaveBeenCalledWith('/inventory/transfers/assignment-check', {
        method: 'POST',
        body: JSON.stringify({
          origin_warehouse_id: 'origin',
          vehicle_id: 'vehicle',
          driver_id: null,
          transfer_id: null,
          lines: [{ handling_unit_id: 'hu-1', quantity_base: '2' }]
        })
      });
      await inventoryTransfersApi.transferAssignmentCheck('transfer / 1');
      expect(apiFetchMock).toHaveBeenLastCalledWith(
        '/inventory/transfers/transfer%20%2F%201/assignment-check'
      );
    });

    it('despacha con la sustitución solo cuando existe', async () => {
      await inventoryTransfersApi.dispatch('transfer-1', 'vehicle-2', 'attempt-1', {
        driverId: 'driver-2',
        substitutionCode: 'vehicle_unavailable',
        substitutionReason: '  El vehículo aprobado no arrancó  '
      });
      expect(apiFetchMock).toHaveBeenCalledWith('/inventory/transfers/transfer-1/dispatch', {
        method: 'POST',
        body: JSON.stringify({
          vehicle_id: 'vehicle-2',
          idempotency_key: 'attempt-1',
          driver_id: 'driver-2',
          override_reason: null,
          substitution_code: 'vehicle_unavailable',
          substitution_reason: 'El vehículo aprobado no arrancó'
        })
      });
      await inventoryTransfersApi.dispatch('transfer-1', 'vehicle-1', 'attempt-2');
      const [, init] = apiFetchMock.mock.calls.at(-1)!;
      expect(JSON.parse(init.body)).toMatchObject({
        substitution_code: null,
        substitution_reason: null
      });
    });

    it('recibe con avería y sobrante y cierra la recepción con faltante', async () => {
      const lines = [
        {
          transfer_detail_id: 'detail-1',
          destination_location_id: 'loc-1',
          quantity_base: '6',
          damaged_quantity: '2',
          damage_type: 'broken' as const,
          damage_notes: 'Cajas rotas',
          surplus_quantity: '1',
          surplus_notes: 'Llegó una caja de más',
          evidence_reference: 'FOTO-1'
        }
      ];
      await inventoryTransfersApi.receive('transfer-1', 'receive-1', lines);
      expect(apiFetchMock).toHaveBeenCalledWith('/inventory/transfers/transfer-1/receive', {
        method: 'POST',
        body: JSON.stringify({ idempotency_key: 'receive-1', lines })
      });
      const body = {
        idempotency_key: 'close-1',
        reason: 'No llegó el resto',
        evidence_reference: null
      };
      await inventoryTransfersApi.closeReception('transfer-1', body);
      expect(apiFetchMock).toHaveBeenLastCalledWith(
        '/inventory/transfers/transfer-1/close-reception',
        { method: 'POST', body: JSON.stringify(body) }
      );
    });

    it('manda cada acción sobre una diferencia a su propio endpoint', async () => {
      const root = '/inventory/transfers/transfer-1/discrepancies/disc%2F1';
      await inventoryTransfersApi.claimDiscrepancy('transfer-1', 'disc/1', {
        idempotency_key: 'k1',
        claim_reference: 'REC-1'
      });
      expect(apiFetchMock).toHaveBeenLastCalledWith(`${root}/claim`, {
        method: 'POST',
        body: JSON.stringify({ idempotency_key: 'k1', claim_reference: 'REC-1' })
      });
      await inventoryTransfersApi.releaseDamage('transfer-1', 'disc/1', {
        idempotency_key: 'k2',
        notes: 'Inspeccionada'
      });
      expect(apiFetchMock).toHaveBeenLastCalledWith(`${root}/release`, {
        method: 'POST',
        body: JSON.stringify({
          idempotency_key: 'k2',
          notes: 'Inspeccionada',
          destination_location_id: null
        })
      });
      const note = { idempotency_key: 'k3', notes: 'Apareció en el pasillo' };
      await inventoryTransfersApi.markShortageFound('transfer-1', 'disc/1', note);
      expect(apiFetchMock).toHaveBeenLastCalledWith(`${root}/found`, {
        method: 'POST',
        body: JSON.stringify(note)
      });
      await inventoryTransfersApi.dismissSurplus('transfer-1', 'disc/1', note);
      expect(apiFetchMock).toHaveBeenLastCalledWith(`${root}/dismiss`, {
        method: 'POST',
        body: JSON.stringify(note)
      });
      await inventoryTransfersApi.recordOriginCount('transfer-1', 'disc/1', note);
      expect(apiFetchMock).toHaveBeenLastCalledWith(`${root}/origin-count`, {
        method: 'POST',
        body: JSON.stringify(note)
      });
      const adjustment = {
        idempotency_key: 'k4',
        operational_date: '2026-10-20',
        accounting_date: '2026-10-20',
        reason: 'Ingreso del sobrante',
        document_reference: 'ACTA-1'
      };
      await inventoryTransfersApi.prepareDiscrepancyAdjustment('transfer-1', 'disc/1', adjustment);
      expect(apiFetchMock).toHaveBeenLastCalledWith(`${root}/adjustment`, {
        method: 'POST',
        body: JSON.stringify(adjustment)
      });
    });

    it('filtra la lista por conteo pendiente en origen y por diferencias abiertas', async () => {
      apiFetchMock.mockResolvedValue([]);
      await inventoryTransfersApi.list({
        status: 'discrepancy',
        originCountPending: true,
        withOpenDiscrepancies: true
      });
      expect(apiFetchMock).toHaveBeenCalledWith(
        '/inventory/transfers?page=1&size=50&status=discrepancy&origin_count_pending=true&with_open_discrepancies=true'
      );
    });
  });
});
