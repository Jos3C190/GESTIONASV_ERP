import { fireEvent, render, screen, waitFor, within } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { HandlingUnit } from '../types';
import HandlingUnitsPanel from './HandlingUnitsPanel.svelte';

const inventoryMocks = vi.hoisted(() => ({
  listHandlingUnits: vi.fn(),
  verifyHandlingUnitMeasurements: vi.fn()
}));

const locationMocks = vi.hoisted(() => ({
  listLocations: vi.fn()
}));

vi.mock('../services', () => ({
  inventoryApi: inventoryMocks
}));

vi.mock('$lib/features/locations/services', () => locationMocks);

function handlingUnit(overrides: Partial<HandlingUnit> = {}): HandlingUnit {
  return {
    id: 'hu-1',
    company_id: 'company-1',
    warehouse_id: 'warehouse-1',
    location_id: 'location-2',
    inventory_item_id: 'item-1',
    packaging_definition_id: null,
    code: 'HU-0001',
    lot_code: 'LOTE-A',
    expiry_date: '2027-01-15',
    quantity_base: 12,
    actual_gross_weight_kg: null,
    actual_length_m: null,
    actual_width_m: null,
    actual_height_m: null,
    actual_volume_m3: null,
    occupied_weight_kg: null,
    occupied_volume_m3: null,
    stock_status: 'quarantine',
    measurement_status: 'incomplete',
    measurement_source: 'receipt',
    closed_at: null,
    created_at: '2026-08-19T12:00:00Z',
    updated_at: null,
    ...overrides
  };
}

function locationPage(id: string, code: string, page: number, pages: number) {
  return {
    items: [{ id, code }],
    meta: { page, size: 100, total: pages, pages }
  };
}

describe('HandlingUnitsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    inventoryMocks.listHandlingUnits.mockResolvedValue([handlingUnit()]);
    locationMocks.listLocations
      .mockResolvedValueOnce(locationPage('location-1', 'REC-A-01', 1, 2))
      .mockResolvedValueOnce(locationPage('location-2', 'CAL-A-02', 2, 2));
  });

  it('resuelve ubicaciones paginadas y conserva las medidas desconocidas como Sin medir', async () => {
    render(HandlingUnitsPanel, {
      props: { warehouseId: 'warehouse-1', canVerify: false }
    });

    expect(await screen.findByText('HU-0001')).toBeInTheDocument();
    expect(screen.getAllByText('CAL-A-02')).toHaveLength(2);
    expect(screen.getAllByText('Sin medir')).toHaveLength(2);
    expect(screen.getByText('LOTE-A')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Verificar medidas' })).not.toBeInTheDocument();
    expect(locationMocks.listLocations).toHaveBeenNthCalledWith(1, 'warehouse-1', {
      page: 1,
      size: 100
    });
    expect(locationMocks.listLocations).toHaveBeenNthCalledWith(2, 'warehouse-1', {
      page: 2,
      size: 100
    });
  });

  it('filtra por código y por estado sin convertir los datos físicos', async () => {
    inventoryMocks.listHandlingUnits.mockResolvedValueOnce([
      handlingUnit(),
      handlingUnit({
        id: 'hu-2',
        code: 'HU-0002',
        lot_code: 'LOTE-B',
        location_id: 'location-1',
        stock_status: 'available',
        measurement_status: 'verified',
        measurement_source: 'manual',
        occupied_weight_kg: 25,
        occupied_volume_m3: 0.5
      })
    ]);

    render(HandlingUnitsPanel, {
      props: { warehouseId: 'warehouse-1', canVerify: false }
    });

    expect(await screen.findByText('HU-0002')).toBeInTheDocument();
    await fireEvent.input(screen.getByLabelText('Buscar por código, lote o ubicación'), {
      target: { value: 'LOTE-A' }
    });
    await waitFor(() => {
      expect(screen.getByText('HU-0001')).toBeInTheDocument();
      expect(screen.queryByText('HU-0002')).not.toBeInTheDocument();
    });

    await fireEvent.input(screen.getByLabelText('Buscar por código, lote o ubicación'), {
      target: { value: '' }
    });
    await fireEvent.change(screen.getByLabelText('Estado de existencia'), {
      target: { value: 'available' }
    });
    await waitFor(() => {
      expect(screen.getByText('HU-0002')).toBeInTheDocument();
      expect(screen.queryByText('HU-0001')).not.toBeInTheDocument();
    });
  });

  it('verifica por dimensiones solo una unidad incompleta en cuarentena con permiso de recepción', async () => {
    const onverified = vi.fn();
    inventoryMocks.listHandlingUnits.mockResolvedValueOnce([
      handlingUnit(),
      handlingUnit({
        id: 'hu-available',
        code: 'HU-AVAILABLE',
        stock_status: 'available'
      })
    ]);
    inventoryMocks.verifyHandlingUnitMeasurements.mockResolvedValueOnce(
      handlingUnit({
        actual_gross_weight_kg: 18.5,
        actual_length_m: 0.8,
        actual_width_m: 0.5,
        actual_height_m: 0.4,
        actual_volume_m3: 0.16,
        occupied_weight_kg: 18.5,
        occupied_volume_m3: 0.16,
        measurement_status: 'verified',
        measurement_source: 'manual'
      })
    );

    render(HandlingUnitsPanel, {
      props: { warehouseId: 'warehouse-1', canVerify: true, onverified }
    });

    const verifyButton = await screen.findByRole('button', { name: 'Verificar medidas' });
    expect(screen.getAllByRole('button', { name: 'Verificar medidas' })).toHaveLength(1);
    await fireEvent.click(verifyButton);

    const form = screen.getByRole('form', { name: 'Verificar medidas de HU-0001' });
    await fireEvent.input(within(form).getByLabelText(/Peso bruto/), {
      target: { value: '18.5' }
    });
    await fireEvent.change(within(form).getByLabelText(/Método de volumen/), {
      target: { value: 'dimensions' }
    });
    const lengthInput = await within(form).findByLabelText(/Largo/);
    await fireEvent.input(lengthInput, {
      target: { value: '0.8' }
    });
    await fireEvent.input(within(form).getByLabelText(/Ancho/), {
      target: { value: '0.5' }
    });
    await fireEvent.input(within(form).getByLabelText(/Alto/), {
      target: { value: '0.4' }
    });
    await fireEvent.submit(form);

    await waitFor(() =>
      expect(inventoryMocks.verifyHandlingUnitMeasurements).toHaveBeenCalledWith(
        'hu-1',
        {
          gross_weight_kg: 18.5,
          volume_m3: null,
          length_m: 0.8,
          width_m: 0.5,
          height_m: 0.4
        },
        'manual'
      )
    );
    expect(await screen.findByRole('status')).toHaveTextContent(
      'Medidas de HU-0001 verificadas correctamente.'
    );
    expect(screen.getByText('18.5 kg')).toBeInTheDocument();
    expect(screen.getByText('0.16 m³')).toBeInTheDocument();
    expect(onverified).toHaveBeenCalledOnce();
  });
});
