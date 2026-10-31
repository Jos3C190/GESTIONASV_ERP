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
});
