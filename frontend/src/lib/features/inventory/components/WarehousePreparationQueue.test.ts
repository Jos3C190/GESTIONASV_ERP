import { fireEvent, render, screen, waitFor, cleanup } from '@testing-library/svelte';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import Queue from './WarehousePreparationQueue.svelte';

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  execute: vi.fn(),
  measure: vi.fn(),
  locations: vi.fn()
}));
vi.mock('$lib/features/locations/services', () => ({ listLocations: mocks.locations }));
vi.mock('../preparation', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../preparation')>()),
  preparationApi: { list: mocks.list, execute: mocks.execute }
}));
vi.mock('../services', () => ({ inventoryApi: { verifyHandlingUnitMeasurements: mocks.measure } }));
const unit = {
  id: 'unit-1',
  code: 'HU-TEST-1',
  quantity_base: 50,
  phase: 'place',
  measurement_status: 'verified',
  label_confirmed: true,
  product_name: 'Azúcar Glass Premium 10kg',
  base_unit_symbol: 'cj',
  receipt_lot_code: 'LOT-COM-28',
  stock_status: 'quarantine',
  warehouse_id: 'warehouse-1',
  inventory_item_id: 'item-1'
};
const result = (items = [unit]) => ({
  items,
  meta: { total: items.length, page: 1, size: 10, pages: 1 }
});
beforeEach(() => {
  vi.clearAllMocks();
  mocks.list.mockResolvedValue(result());
  mocks.locations.mockResolvedValue({ items: [], meta: { page: 1, pages: 1 } });
});
afterEach(cleanup);
async function selectUnit() {
  await fireEvent.click(await screen.findByRole('button', { name: /Azúcar Glass Premium/ }));
}
describe('preparación del bodeguero', () => {
  it('conserva el código automático al pasar de medidas a etiqueta', async () => {
    mocks.list.mockResolvedValue(result([{ ...unit, phase: 'measure' }]));
    mocks.measure.mockImplementation(async () => {
      mocks.list.mockResolvedValue(result([{ ...unit, phase: 'label' }]));
    });
    render(Queue, { warehouseId: 'warehouse-1', contextKey: 'company-1', canOperate: true });
    await selectUnit();
    await fireEvent.input(screen.getByLabelText('Peso bruto (kg)'), { target: { value: '10' } });
    await fireEvent.input(screen.getByLabelText('Volumen (m³)'), { target: { value: '0.1' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar medidas' }));
    await screen.findByRole('button', { name: 'Revisar y colocar etiqueta' });
    expect(screen.getByLabelText(/Código de unidad o producto/)).toHaveValue(unit.code);
  });

  it('elige una ubicación activa de su bodega y envía el código sin escribirlo', async () => {
    const location = {
      id: 'destination',
      code: 'A01-R01-N01-P01',
      warehouse_id: 'warehouse-1',
      is_active: true,
      lifecycle_status: 'active',
      storage_eligible: true,
      area: '',
      aisle: '01',
      rack: '01',
      level: '01',
      position: '01'
    };
    mocks.locations.mockResolvedValue({
      items: [
        location,
        { ...location, id: 'foreign', code: 'OTRA-BODEGA', warehouse_id: 'warehouse-2' },
        { ...location, id: 'blocked', code: 'BLOQUEADA', lifecycle_status: 'blocked' }
      ],
      meta: { page: 1, pages: 1 }
    });
    mocks.execute.mockRejectedValue(new Error('Sin conexión'));
    render(Queue, { warehouseId: 'warehouse-1', contextKey: 'company-1', canOperate: true });
    await selectUnit();
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Elegir en el mapa' })).toBeEnabled()
    );
    await fireEvent.click(screen.getByRole('button', { name: 'Elegir en el mapa' }));
    await fireEvent.click(screen.getByRole('button', { name: /Seleccionar Pasillo 01/ }));
    await fireEvent.click(screen.getAllByRole('button', { name: /Asignar A01-R01-N01-P01/ })[0]!);
    expect(screen.getByLabelText(/Código de ubicación/)).toHaveValue(location.code);
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar ubicación e ingresar' }));
    await waitFor(() =>
      expect(mocks.execute).toHaveBeenCalledWith(
        unit.id,
        'place',
        expect.objectContaining({ unit_scan: unit.code, location_scan: location.code })
      )
    );
    expect(screen.queryByText('OTRA-BODEGA')).not.toBeInTheDocument();
    expect(screen.queryByText('BLOQUEADA')).not.toBeInTheDocument();
  });
  it('exige lectura de unidad y ubicación antes de ingresar', async () => {
    render(Queue, { warehouseId: 'warehouse-1', contextKey: 'company-1', canOperate: true });
    await selectUnit();
    expect(screen.getByLabelText(/Código de unidad o producto/)).toHaveValue('HU-TEST-1');
    await fireEvent.input(screen.getByLabelText(/Código de unidad o producto/), {
      target: { value: '' }
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar ubicación e ingresar' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Escanea o escribe el código de la unidad'
    );
    expect(mocks.execute).not.toHaveBeenCalled();
    await fireEvent.input(screen.getByLabelText(/Código de unidad o producto/), {
      target: { value: 'HU-TEST-1' }
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar ubicación e ingresar' }));
    expect(screen.getByRole('alert')).toHaveTextContent('código de la ubicación');
  });
  it('prepara la porción y conserva la clave al reintentar un fallo de red', async () => {
    mocks.execute
      .mockRejectedValueOnce(new Error('Sin conexión'))
      .mockResolvedValueOnce({ prepared_unit_id: 'unit-2', quantity_base: '30' });
    render(Queue, { warehouseId: 'warehouse-1', contextKey: 'company-1', canOperate: true });
    await selectUnit();
    await fireEvent.input(screen.getByLabelText(/Código de unidad o producto/), {
      target: { value: 'HU-TEST-1' }
    });
    await fireEvent.input(screen.getByLabelText(/Cantidad a ubicar/), { target: { value: '30' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Preparar porción' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Sin conexión');
    await fireEvent.click(screen.getByRole('button', { name: 'Preparar porción' }));
    await waitFor(() => expect(mocks.execute).toHaveBeenCalledTimes(2));
    expect(mocks.execute.mock.calls[0]).toEqual(mocks.execute.mock.calls[1]);
    expect(mocks.execute.mock.calls[0]?.[1]).toBe('split');
    expect(mocks.execute.mock.calls[0]?.[2]).not.toHaveProperty('location_scan');
  });
  it('el Enter del lector avanza el foco y no confirma una entrada', async () => {
    render(Queue, { warehouseId: 'warehouse-1', contextKey: 'company-1', canOperate: true });
    await selectUnit();
    await fireEvent.keyDown(screen.getByLabelText(/Código de unidad o producto/), { key: 'Enter' });
    expect(screen.getByLabelText(/Cantidad a ubicar/)).toHaveFocus();
    expect(mocks.execute).not.toHaveBeenCalled();
  });
  it.each([
    ['measure', 'preparation-weight'],
    ['label', 'preparation-label'],
    ['place', 'preparation-location']
  ])('dirige Enter al control de la fase %s', async (phase, target) => {
    mocks.list.mockResolvedValue(result([{ ...unit, phase }]));
    render(Queue, { warehouseId: 'warehouse-1', contextKey: 'company-1', canOperate: true });
    await selectUnit();
    await fireEvent.keyDown(screen.getByLabelText(/Cantidad a ubicar/), { key: 'Enter' });
    expect(document.activeElement?.id).toBe(target);
    expect(mocks.execute).not.toHaveBeenCalled();
  });
  it('registra una ubicación y muestra la cantidad confirmada', async () => {
    mocks.execute.mockImplementation(async () => {
      mocks.list.mockResolvedValue(result([]));
      return { prepared_unit_id: 'unit-1', quantity_base: '50', movement_id: 'move-1' };
    });
    const onplaced = vi.fn();
    render(Queue, {
      warehouseId: 'warehouse-1',
      contextKey: 'company-1',
      canOperate: true,
      onplaced
    });
    await selectUnit();
    await fireEvent.input(screen.getByLabelText(/Código de unidad o producto/), {
      target: { value: 'HU-TEST-1' }
    });
    await fireEvent.input(screen.getByLabelText(/Código de ubicación/), {
      target: { value: 'A01-R01-N01-P01' }
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar ubicación e ingresar' }));
    expect(await screen.findByRole('status')).toHaveTextContent('50 cj ingresaron');
    expect(onplaced).toHaveBeenCalledOnce();
    expect(await screen.findByText('No hay unidades pendientes')).toBeInTheDocument();
  });
  it('valida las medidas de la unidad completa y respeta permisos de operación', async () => {
    mocks.list.mockResolvedValue(
      result([{ ...unit, phase: 'measure', measurement_status: 'incomplete' }])
    );
    render(Queue, { warehouseId: 'warehouse-1', contextKey: 'company-1', canOperate: true });
    await selectUnit();
    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar medidas' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('peso bruto y volumen positivos');
    expect(mocks.measure).not.toHaveBeenCalled();
    cleanup();
    render(Queue, { warehouseId: 'warehouse-1', contextKey: 'company-1', canOperate: false });
    await selectUnit();
    expect(screen.queryByRole('button', { name: 'Confirmar medidas' })).not.toBeInTheDocument();
  });
  it('descarta respuestas de una bodega anterior al cambiar el contexto', async () => {
    let resolve!: (value: ReturnType<typeof result>) => void;
    mocks.list
      .mockReturnValueOnce(new Promise((done) => (resolve = done)))
      .mockResolvedValueOnce(result([]));
    const view = render(Queue, {
      warehouseId: 'warehouse-1',
      contextKey: 'company-1',
      canOperate: true
    });
    await waitFor(() => expect(mocks.list).toHaveBeenCalledOnce());
    await view.rerender({ warehouseId: 'warehouse-2', contextKey: 'company-2', canOperate: true });
    await screen.findByText('No hay unidades pendientes');
    resolve(result());
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /Azúcar Glass Premium/ })).not.toBeInTheDocument()
    );
  });
});
