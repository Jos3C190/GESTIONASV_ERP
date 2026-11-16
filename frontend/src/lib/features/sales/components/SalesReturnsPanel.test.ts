import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { salesApi, documentApi } = vi.hoisted(() => ({
  salesApi: {
    returnableAllocations: vi.fn(),
    returnsForSale: vi.fn(),
    createReturn: vi.fn(),
    receiveReturn: vi.fn(),
    resolveReturn: vi.fn(),
    cancelReturn: vi.fn()
  },
  documentApi: { list: vi.fn() }
}));

vi.mock('$lib/api/sales', () => ({ salesApi }));
vi.mock('$lib/api/client', () => ({
  HttpError: class HttpError extends Error {},
  api: { documents: { list: documentApi.list } }
}));

import { permissions } from '$lib/stores/permissions.svelte';
import type { Sale, SalesReturn, SalesReturnableAllocation } from '$lib/types/sales';
import SalesReturnsPanel from './SalesReturnsPanel.svelte';

const sale: Sale = {
  id: 'sale-1', company_id: 'company-1', branch_id: 'branch-1', customer_id: 'customer-1',
  customer_code: 'CLI-001', customer_name: 'Cliente ficticio', quotation_id: 'quote-1',
  quotation_code: 'COT-00001', code: 'VEN-00001', currency: 'USD', subtotal: '20.00',
  total: '20.00', status: 'confirmed', version: 2, notes: null, delivery_progress: 'partial',
  lines: [], created_at: '2026-10-19T12:00:00Z', updated_at: '2026-10-19T12:00:00Z'
};

const allocation: SalesReturnableAllocation = {
  delivery_id: 'delivery-1', delivery_code: 'ENT-00001', delivery_line_id: 'delivery-line-1',
  delivery_allocation_id: 'allocation-1', delivery_date: '2026-10-19T12:00:00Z',
  handling_unit_code: 'HU-00001', inventory_item_id: 'item-1', product_sku: 'SKU-FICT-01',
  product_name: 'Producto ficticio', unit_name: 'Caja', base_unit_name: 'unidad', lot_code: 'LOT-FICT-01',
  quantity_delivered_base: '2.000000', quantity_returned_base: '0.000000',
  quantity_reserved_base: '0.000000', quantity_returnable_base: '2.000000'
};

function returnDocument(status: SalesReturn['status']): SalesReturn {
  return {
    id: 'return-1', company_id: 'company-1', branch_id: 'branch-1', sale_id: 'sale-1',
    code: 'DEV-20261019-ABCDEF12', status, notes: null, created_by_id: 'user-1',
    received_by_id: status === 'draft' ? null : 'user-1', received_at: status === 'draft' ? null : '2026-10-19T12:01:00Z',
    cancelled_at: null, cancellation_reason: null, created_at: '2026-10-19T12:00:00Z',
    updated_at: '2026-10-19T12:01:00Z', evidence: [],
    lines: [{
      id: 'return-line-1', delivery_id: 'delivery-1', delivery_code: 'ENT-00001',
      delivery_allocation_id: 'allocation-1', source_handling_unit_id: 'hu-1',
      inventory_item_id: 'item-1', product_sku: 'SKU-FICT-01', product_name: 'Producto ficticio',
      unit_name: 'Caja', base_unit_name: 'unidad', lot_code: 'LOT-FICT-01',
      quantity_received_base: '1.000000', quantity_accepted_base: '0.000000',
      quantity_rejected_base: '0.000000', quantity_pending_base: '1.000000',
      quantity_returnable_base: '1.000000', reason: 'Empaque sin abrir', declared_condition: 'resalable', events: []
    }]
  };
}

function setup() {
  return render(SalesReturnsPanel, { sale, onChanged: vi.fn() });
}

describe('SalesReturnsPanel', () => {
  beforeEach(() => {
    sessionStorage.clear();
    permissions.clear();
    allocation.base_unit_name = 'unidad';
    salesApi.returnableAllocations.mockReset().mockResolvedValue([allocation]);
    salesApi.returnsForSale.mockReset().mockResolvedValue([]);
    salesApi.createReturn.mockReset().mockResolvedValue(returnDocument('draft'));
    salesApi.receiveReturn.mockReset().mockResolvedValue(returnDocument('received'));
    salesApi.resolveReturn.mockReset().mockResolvedValue(returnDocument('accepted'));
    salesApi.cancelReturn.mockReset().mockResolvedValue(returnDocument('cancelled'));
    documentApi.list.mockReset().mockResolvedValue({
      items: [{
        id: 'document-1', module: 'general', business_status: 'active', is_current: true,
        title: 'Factura ficticia', original_filename: 'factura-prueba.pdf', reference_code: 'FAC-TEST-01'
      }],
      meta: { page: 1, size: 20, total: 1, pages: 1 }
    });
  });

  it('normaliza la unidad base repetida en la asignación y en el historial', async () => {
    permissions.set(['sales_returns:read', 'sales_returns:manage'], false);
    allocation.base_unit_name = 'Unidad (u) (u)';
    const historicalReturn = returnDocument('received');
    historicalReturn.lines[0]!.base_unit_name = 'Unidad (u) (u)';
    salesApi.returnsForSale.mockResolvedValue([historicalReturn]);
    setup();

    expect(await screen.findByText(/Entregado 2\.000000 Unidad \(u\).*quedan 2\.000000 Unidad \(u\)/)).toBeInTheDocument();
    expect(screen.getByLabelText('Cantidad devuelta (Unidad (u))')).toBeInTheDocument();
    expect(screen.getByText(/recibido 1\.000000 Unidad \(u\)/)).toBeInTheDocument();
    expect(screen.queryByText(/Unidad \(u\) \(u\)/)).not.toBeInTheDocument();
  });

  it('crea borrador con origen y evidencia seleccionada por nombre, sin recibir ni modificar inventario', async () => {
    permissions.set(['sales_returns:manage', 'sales_returns:read', 'documents:read'], false);
    setup();

    await screen.findByText(/SKU-FICT-01/);
    await fireEvent.input(screen.getByLabelText('Cantidad devuelta de Producto ficticio'), { target: { value: '1' } });
    await fireEvent.input(screen.getByLabelText('Motivo de devolución de Producto ficticio'), { target: { value: 'Empaque sin abrir' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Buscar documentos' }));
    const evidence = await screen.findByLabelText('Adjuntar evidencia Factura ficticia');
    await fireEvent.click(evidence);
    expect(screen.getByLabelText('Evidencia seleccionada')).toHaveTextContent('Factura ficticia · factura-prueba.pdf');
    await fireEvent.click(screen.getByRole('button', { name: 'Quitar evidencia Factura ficticia' }));
    expect(screen.queryByLabelText('Evidencia seleccionada')).not.toBeInTheDocument();
    await fireEvent.click(evidence);
    expect(screen.getByLabelText('Cantidad devuelta de Producto ficticio')).toHaveValue(1);
    expect(screen.getByLabelText('Motivo de devolución de Producto ficticio')).toHaveValue('Empaque sin abrir');
    await fireEvent.submit(screen.getByRole('button', { name: 'Crear borrador' }).closest('form')!);

    await waitFor(() => expect(salesApi.createReturn).toHaveBeenCalledOnce());
    expect(salesApi.createReturn).toHaveBeenCalledWith('sale-1', expect.objectContaining({
      document_ids: ['document-1'],
      lines: [expect.objectContaining({ delivery_allocation_id: 'allocation-1', quantity_base: '1', reason: 'Empaque sin abrir' })]
    }), expect.stringMatching(/^create:/));
    expect(await screen.findByRole('status')).toHaveTextContent('Se creó el borrador DEV-20261019-ABCDEF12');
    expect(screen.getByLabelText('Cantidad devuelta de Producto ficticio')).toHaveValue(null);
    expect(screen.getByLabelText('Motivo de devolución de Producto ficticio')).toHaveValue('');
    expect(salesApi.receiveReturn).not.toHaveBeenCalled();
    expect(salesApi.resolveReturn).not.toHaveBeenCalled();
    expect(documentApi.list).toHaveBeenCalledWith({
      module: 'general', status: 'active', search: undefined, page: 1, size: 20
    });
  });

  it('busca evidencia con Enter sin enviar el borrador de devolución', async () => {
    permissions.set(['sales_returns:manage', 'sales_returns:read', 'documents:read'], false);
    setup();

    await screen.findByText(/SKU-FICT-01/);
    await fireEvent.input(screen.getByLabelText('Cantidad devuelta de Producto ficticio'), { target: { value: '1' } });
    await fireEvent.input(screen.getByLabelText('Motivo de devolución de Producto ficticio'), { target: { value: 'Empaque sin abrir' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Buscar documentos' }));
    const search = screen.getByLabelText('Buscar evidencia por nombre o referencia');
    await fireEvent.input(search, { target: { value: 'Factura' } });
    await fireEvent.keyDown(search, { key: 'Enter' });

    await waitFor(() => expect(documentApi.list).toHaveBeenCalledTimes(2));
    expect(salesApi.createReturn).not.toHaveBeenCalled();
    expect(screen.getByLabelText('Cantidad devuelta de Producto ficticio')).toHaveValue(1);
  });

  it('registra recepción documental separada de la decisión de inventario', async () => {
    permissions.set(['sales_returns:read', 'sales_returns:receive'], false);
    salesApi.returnsForSale.mockResolvedValue([returnDocument('draft')]);
    setup();

    await fireEvent.click(await screen.findByRole('button', { name: 'Registrar recepción física' }));

    await waitFor(() => expect(salesApi.receiveReturn).toHaveBeenCalledOnce());
    expect(salesApi.resolveReturn).not.toHaveBeenCalled();
  });

  it('conserva la clave de un envío incierto al volver a abrir la venta', async () => {
    permissions.set(['sales_returns:read', 'sales_returns:receive'], false);
    salesApi.returnsForSale.mockResolvedValue([returnDocument('draft')]);
    salesApi.receiveReturn.mockRejectedValueOnce(new Error('Respuesta perdida'));
    const first = setup();
    await fireEvent.click(await screen.findByRole('button', { name: 'Registrar recepción física' }));
    await screen.findByRole('alert');
    const firstKey = salesApi.receiveReturn.mock.calls[0]?.[1];
    expect(firstKey).toEqual(expect.any(String));
    first.unmount();

    setup();
    await fireEvent.click(await screen.findByRole('button', { name: 'Registrar recepción física' }));
    await waitFor(() => expect(salesApi.receiveReturn).toHaveBeenCalledTimes(2));
    expect(salesApi.receiveReturn.mock.calls[1]?.[1]).toBe(firstKey);
  });

  it('reconsulta el estado si se pierde la respuesta después de aplicar la recepción', async () => {
    permissions.set(['sales_returns:read', 'sales_returns:receive'], false);
    let serverReceived = false;
    salesApi.returnsForSale.mockImplementation(async () => [returnDocument(serverReceived ? 'received' : 'draft')]);
    salesApi.receiveReturn.mockImplementationOnce(async () => {
      serverReceived = true;
      throw new Error('Respuesta perdida después de confirmar');
    });
    setup();

    await fireEvent.click(await screen.findByRole('button', { name: 'Registrar recepción física' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Se consultó de nuevo el estado antes de reintentar.');
    expect(await screen.findByText('Recibida · pendiente de revisión')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Registrar recepción física' })).not.toBeInTheDocument();
    expect(salesApi.returnsForSale).toHaveBeenCalledTimes(2);
    expect(salesApi.receiveReturn).toHaveBeenCalledOnce();
  });

  it('permite resolver cantidades parciales mixtas conservando el pendiente entre decisiones', async () => {
    permissions.set(['sales_returns:read', 'sales_returns:resolve'], false);
    const serverReturn = returnDocument('received');
    serverReturn.lines[0]!.quantity_received_base = '3.000000';
    serverReturn.lines[0]!.quantity_pending_base = '3.000000';
    serverReturn.lines[0]!.quantity_returnable_base = '3.000000';
    salesApi.returnsForSale.mockImplementation(async () => [serverReturn]);
    salesApi.resolveReturn.mockImplementation(async (_id, payload) => {
      const decision = payload.lines[0]!;
      const line = serverReturn.lines[0]!;
      const quantity = Number(decision.quantity_base);
      line.quantity_pending_base = (Number(line.quantity_pending_base) - quantity).toFixed(6);
      if (decision.decision === 'accepted') {
        line.quantity_accepted_base = (Number(line.quantity_accepted_base) + quantity).toFixed(6);
      } else {
        line.quantity_rejected_base = (Number(line.quantity_rejected_base) + quantity).toFixed(6);
      }
      line.events.push({
        id: `event-${line.events.length + 1}`,
        decision: decision.decision,
        quantity_base: decision.quantity_base,
        condition: decision.condition,
        reason: decision.reason,
        destination_location_id: decision.decision === 'accepted' ? 'location-test' : null,
        movement_id: decision.decision === 'accepted' ? `movement-${line.events.length + 1}` : null,
        movement_line_id: decision.decision === 'accepted' ? `movement-line-${line.events.length + 1}` : null,
        valuation_entry_id: decision.decision === 'accepted' ? `valuation-${line.events.length + 1}` : null,
        actor_id: 'user-test',
        created_at: '2026-10-20T18:00:00-06:00'
      });
      serverReturn.status = Number(line.quantity_pending_base) > 0 ? 'under_review' : 'mixed';
      return serverReturn;
    });
    setup();

    await screen.findByLabelText('Cantidad a resolver');
    const decisionButton = () => screen.getByRole('button', { name: 'Registrar decisión de esta cantidad' });

    await fireEvent.input(screen.getByLabelText('Cantidad a resolver'), { target: { value: '1' } });
    expect(screen.getByLabelText('Cantidad a resolver')).toHaveValue(1);
    await fireEvent.click(decisionButton());
    await waitFor(() => expect(salesApi.resolveReturn).toHaveBeenCalledTimes(1));
    expect(await screen.findByText('En revisión parcial')).toBeInTheDocument();
    await waitFor(() => expect(decisionButton()).toBeEnabled());

    await fireEvent.input(screen.getByLabelText('Cantidad a resolver'), { target: { value: '1' } });
    expect(screen.getByLabelText('Cantidad a resolver')).toHaveValue(1);
    const secondDecision = screen.getByRole('combobox', { name: 'Resultado' });
    await fireEvent.change(secondDecision, { target: { value: 'rejected' } });
    expect(secondDecision).toHaveValue('rejected');
    await fireEvent.click(decisionButton());
    await waitFor(() => expect(salesApi.resolveReturn).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(decisionButton()).toBeEnabled());

    await fireEvent.input(screen.getByLabelText('Cantidad a resolver'), { target: { value: '1' } });
    expect(screen.getByLabelText('Cantidad a resolver')).toHaveValue(1);
    await fireEvent.change(screen.getByLabelText('Resultado'), { target: { value: 'accepted' } });
    await fireEvent.click(decisionButton());
    await waitFor(() => expect(salesApi.resolveReturn).toHaveBeenCalledTimes(3));

    expect(salesApi.resolveReturn.mock.calls.map((call) => ({
      decision: call[1].lines[0]?.decision,
      quantity: call[1].lines[0]?.quantity_base
    }))).toEqual([
      { decision: 'accepted', quantity: '1' },
      { decision: 'rejected', quantity: '1' },
      { decision: 'accepted', quantity: '1' }
    ]);
    expect(serverReturn.status).toBe('mixed');
    expect(serverReturn.lines[0]?.quantity_accepted_base).toBe('2.000000');
    expect(serverReturn.lines[0]?.quantity_rejected_base).toBe('1.000000');
    expect(serverReturn.lines[0]?.quantity_pending_base).toBe('0.000000');
    expect(screen.getByText('Mixta')).toBeInTheDocument();
    expect(salesApi.resolveReturn.mock.calls.map((call) => call[1].lines[0]?.decision)).toEqual([
      'accepted', 'rejected', 'accepted'
    ]);
  });

  it('agrupa en una devolución varias asignaciones de distintas entregas sin perder su origen', async () => {
    permissions.set(['sales_returns:read', 'sales_returns:manage'], false);
    const secondAllocation: SalesReturnableAllocation = {
      ...allocation,
      delivery_id: 'delivery-2',
      delivery_code: 'ENT-00002',
      delivery_line_id: 'delivery-line-2',
      delivery_allocation_id: 'allocation-2',
      handling_unit_code: 'HU-00002',
      lot_code: 'LOT-FICT-02'
    };
    salesApi.returnableAllocations.mockResolvedValue([allocation, secondAllocation]);
    setup();

    await screen.findByText(/HU-00001/);
    expect(screen.getByText(/entrega ENT-00001/)).toBeInTheDocument();
    expect(screen.getByText(/entrega ENT-00002/)).toBeInTheDocument();
    const quantities = screen.getAllByLabelText('Cantidad devuelta de Producto ficticio');
    const reasons = screen.getAllByLabelText('Motivo de devolución de Producto ficticio');
    await fireEvent.input(quantities[0]!, { target: { value: '1' } });
    await fireEvent.input(quantities[1]!, { target: { value: '1' } });
    await fireEvent.input(reasons[0]!, { target: { value: 'Caja cerrada' } });
    await fireEvent.input(reasons[1]!, { target: { value: 'Unidad sin uso' } });
    expect(quantities[0]).toHaveValue(1);
    expect(quantities[1]).toHaveValue(1);
    expect(reasons[0]).toHaveValue('Caja cerrada');
    expect(reasons[1]).toHaveValue('Unidad sin uso');
    await fireEvent.submit(screen.getByRole('button', { name: 'Crear borrador' }).closest('form')!);

    await waitFor(() => expect(salesApi.createReturn).toHaveBeenCalledOnce());
    expect(salesApi.createReturn.mock.calls[0]?.[1].lines).toEqual([
      expect.objectContaining({ delivery_allocation_id: 'allocation-1', quantity_base: '1', reason: 'Caja cerrada' }),
      expect.objectContaining({ delivery_allocation_id: 'allocation-2', quantity_base: '1', reason: 'Unidad sin uso' })
    ]);
  });

  it('acepta una cantidad parcial solo después de registrar una decisión explícita', async () => {
    permissions.set(['sales_returns:read', 'sales_returns:resolve'], false);
    salesApi.returnsForSale.mockResolvedValue([returnDocument('received')]);
    setup();

    await fireEvent.click(await screen.findByRole('button', { name: 'Registrar decisión de esta cantidad' }));

    await waitFor(() => expect(salesApi.resolveReturn).toHaveBeenCalledOnce());
    expect(salesApi.resolveReturn).toHaveBeenCalledWith('return-1', {
      lines: [expect.objectContaining({ return_line_id: 'return-line-1', decision: 'accepted', quantity_base: '1.000000', condition: 'resalable' })]
    }, expect.stringMatching(/^resolve:return-1:return-line-1:/));
    expect(await screen.findByRole('status')).toHaveTextContent('quedó en cuarentena');
  });

  it.each(['', '0', '-1', '1.000001', '0.0000001'])('rechaza una cantidad a resolver inválida: %s', async (quantity) => {
    permissions.set(['sales_returns:read', 'sales_returns:resolve'], false);
    salesApi.returnsForSale.mockResolvedValue([returnDocument('received')]);
    setup();
    const input = await screen.findByLabelText('Cantidad a resolver');
    await fireEvent.input(input, { target: { value: quantity } });
    await fireEvent.click(screen.getByRole('button', { name: 'Registrar decisión de esta cantidad' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('La cantidad a resolver debe ser positiva');
    expect(salesApi.resolveReturn).not.toHaveBeenCalled();
  });

  it('anuncia errores de carga y ofrece volver a consultar', async () => {
    permissions.set(['sales_returns:read', 'sales_returns:manage'], false);
    salesApi.returnableAllocations.mockRejectedValueOnce(new Error('offline'));
    setup();

    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo cargar el flujo de devoluciones.');
    await fireEvent.click(screen.getByRole('button', { name: 'Actualizar' }));
    expect(await screen.findByText(/Producto ficticio/)).toBeInTheDocument();
  });

  it('conserva el formulario y muestra un error si no se pudo crear el borrador', async () => {
    permissions.set(['sales_returns:manage'], false);
    salesApi.createReturn.mockRejectedValueOnce(new Error('server error'));
    setup();

    const quantity = await screen.findByLabelText('Cantidad devuelta de Producto ficticio');
    await fireEvent.input(quantity, { target: { value: '1' } });
    await fireEvent.input(screen.getByLabelText('Motivo de devolución de Producto ficticio'), { target: { value: 'Empaque sin abrir' } });
    await fireEvent.submit(screen.getByRole('button', { name: 'Crear borrador' }).closest('form')!);

    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo guardar el borrador.');
    expect(quantity).toHaveValue(1);
    expect(screen.getByLabelText('Motivo de devolución de Producto ficticio')).toHaveValue('Empaque sin abrir');
  });

  it('exige motivo para cancelar y anuncia la cancelación del borrador', async () => {
    permissions.set(['sales_returns:read', 'sales_returns:cancel'], false);
    salesApi.returnsForSale.mockResolvedValue([returnDocument('draft')]);
    setup();

    await fireEvent.click(await screen.findByRole('button', { name: 'Cancelar borrador' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Escribe por qué se cancela el borrador.');
    expect(salesApi.cancelReturn).not.toHaveBeenCalled();

    await fireEvent.input(screen.getByLabelText('Motivo de cancelación de DEV-20261019-ABCDEF12'), {
      target: { value: 'Duplicado de prueba' }
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Cancelar borrador' }));
    await waitFor(() => expect(salesApi.cancelReturn).toHaveBeenCalledWith('return-1', 'Duplicado de prueba', expect.stringMatching(/^cancel:return-1:/)));
    expect(await screen.findByRole('status')).toHaveTextContent('Se canceló el borrador DEV-20261019-ABCDEF12');
  });
});
