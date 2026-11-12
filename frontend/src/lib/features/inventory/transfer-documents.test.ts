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
      vehicle_id: null,
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
    const lines = [{
      transfer_detail_id: 'detail-1',
      destination_location_id: 'quarantine-1',
      quantity_base: '8'
    }];
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
});
