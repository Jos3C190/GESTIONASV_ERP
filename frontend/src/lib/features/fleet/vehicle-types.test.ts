import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HttpError } from '$lib/api/client';
import type { FleetVehicleType } from './api';
import { meterName, meterShort, plateLabel } from './catalog';
import VehicleImage from './VehicleImage.svelte';
import VehicleTypeForm from './VehicleTypeForm.svelte';

const apiMock = vi.hoisted(() => ({
  createVehicleType: vi.fn(),
  updateVehicleType: vi.fn()
}));

vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  fleetApi: apiMock
}));
vi.mock('$lib/stores/company.svelte', () => ({ company: { active: null } }));

const existing: FleetVehicleType = {
  id: 't1',
  code: 'grua',
  name: 'Grúa',
  plural: 'Grúas',
  license_classes: ['pesada'],
  base_image: null,
  requires_plate: true,
  requires_capacity: true,
  meter_unit: 'km',
  fuel_applicable: true,
  can_tow: false,
  is_towable: false,
  is_system: false,
  is_active: true,
  usage_count: 3
};

describe('helpers', () => {
  it('names the usage by its unit', () => {
    expect(meterShort('km')).toBe('km');
    expect(meterShort('hours')).toBe('h');
    expect(meterName('hours')).toBe('Horómetro');
  });

  it('says when a unit has no plate', () => {
    expect(plateLabel(null)).toBe('Sin placa');
    expect(plateLabel('C 1')).toBe('C 1');
  });
});

describe('VehicleImage', () => {
  afterEach(() => cleanup());

  it('shows the type name instead of breaking when it has no image', () => {
    render(VehicleImage, { image: null, typeName: 'Montacargas', label: 'Toyota' });

    expect(screen.getByText('Montacargas')).toBeInTheDocument();
    expect(screen.queryByRole('img')).toBeNull();
  });
});

describe('VehicleTypeForm', () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => cleanup());

  it('creates a type with what was chosen', async () => {
    const saved = { ...existing, name: 'Montacargas' };
    apiMock.createVehicleType.mockResolvedValue(saved);
    const onsaved = vi.fn();
    render(VehicleTypeForm, { onsaved, oncancel: vi.fn() });

    await fireEvent.input(screen.getByLabelText(/^Nombre/), { target: { value: ' Montacargas ' } });
    await fireEvent.click(screen.getByLabelText(/Circula por la vía pública/));
    await fireEvent.click(screen.getByRole('button', { name: 'Guardar' }));

    await vi.waitFor(() => expect(onsaved).toHaveBeenCalledWith(saved));
    expect(apiMock.createVehicleType).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'Montacargas',
        plural: 'Montacargas',
        requires_plate: false,
        license_classes: [],
        can_tow: false
      })
    );
  });

  it('explains that an empty license list asks for none', async () => {
    render(VehicleTypeForm, { onsaved: vi.fn(), oncancel: vi.fn() });

    expect(screen.getByText(/no se exige licencia/)).toBeInTheDocument();

    await fireEvent.click(screen.getByLabelText('Pesada'));

    expect(screen.getByText(/Un conductor con otra licencia/)).toBeInTheDocument();
  });

  it('requires a name without calling the server', async () => {
    render(VehicleTypeForm, { onsaved: vi.fn(), oncancel: vi.fn() });

    await fireEvent.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(await screen.findByText('Indique el nombre del tipo.')).toBeInTheDocument();
    expect(apiMock.createVehicleType).not.toHaveBeenCalled();
  });

  it('shows a repeated name beside its field', async () => {
    apiMock.createVehicleType.mockRejectedValue(
      new HttpError('vehicle_type_duplicate', 'Ya existe un tipo con ese nombre.', 409)
    );
    render(VehicleTypeForm, { onsaved: vi.fn(), oncancel: vi.fn() });

    await fireEvent.input(screen.getByLabelText(/^Nombre/), { target: { value: 'Grúa' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(await screen.findByText('Ya existe un tipo con ese nombre.')).toBeInTheDocument();
  });

  it('locks the usage unit once vehicles use the type', () => {
    render(VehicleTypeForm, { item: existing, onsaved: vi.fn(), oncancel: vi.fn() });

    expect(screen.getByLabelText(/Cómo se mide su uso/)).toBeDisabled();
    expect(screen.getByText(/La medida de uso no cambia/)).toBeInTheDocument();
  });
});
