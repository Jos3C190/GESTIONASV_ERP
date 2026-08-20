import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { LocationOut } from '../types';
import LocationFormModal from './LocationFormModal.svelte';

const serviceMocks = vi.hoisted(() => ({
  createLocation: vi.fn(),
  updateLocation: vi.fn(),
  previewLocationCode: vi.fn()
}));
const capacityGroupMocks = vi.hoisted(() => ({
  listCapacityGroups: vi.fn()
}));

vi.mock('../services', () => serviceMocks);
vi.mock('../../warehouses/capacity-groups.service', () => capacityGroupMocks);

const legacyLocation: LocationOut = {
  id: 'location-legacy',
  warehouse_id: 'warehouse-1',
  code: 'REC-01',
  area: 'RECEPCION',
  aisle: 'R',
  rack: '01',
  level: '01',
  position: '01',
  capacity_group_id: null,
  certified_max_weight_kg: 1000,
  operational_max_weight_kg: 900,
  certified_usable_volume_m3: 100,
  operational_usable_volume_m3: 90,
  capacity_profile: 'general_mixed',
  capacity_enforcement_mode: 'observe',
  capacity_status: 'available',
  storage_eligible: true,
  usable_length_m: 10,
  usable_width_m: 8,
  usable_height_m: 3,
  notes: null,
  location_type: 'receiving',
  lifecycle_status: 'active',
  barcode: '7501234567890',
  verification_code: 'REC-01-CHECK',
  pick_sequence: null,
  putaway_sequence: null,
  external_id: null,
  scheme_id: null,
  scheme_version: null,
  code_source: 'legacy',
  is_active: true,
  created_at: '2026-08-12T00:00:00Z',
  updated_at: '2026-08-12T15:30:45Z'
};

describe('LocationFormModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    capacityGroupMocks.listCapacityGroups.mockResolvedValue([]);
    serviceMocks.previewLocationCode.mockResolvedValue({
      code: 'AREC-RR01-N01-P01',
      normalized_components: {
        area: 'RECEPCION',
        aisle: 'R',
        rack: '01',
        level: '01',
        position: '01'
      },
      scheme_id: 'scheme-active',
      scheme_version: 2,
      code_exists: false,
      coordinates_exist: true
    });
  });

  it('expone el código como resultado autogenerado y no como entrada editable', () => {
    render(LocationFormModal, {
      props: {
        open: true,
        warehouseId: 'warehouse-1',
        location: null,
        onclose: vi.fn(),
        onsaved: vi.fn()
      }
    });

    expect(screen.getByText('Código autogenerado')).toBeInTheDocument();
    expect(screen.getByText('Solo lectura')).toBeInTheDocument();
    expect(screen.queryByRole('textbox', { name: /^código$/i })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Guardar y crear otra' })).toBeDisabled();
  });

  it('presenta las notas como un campo multilinea coherente con el sistema visual', () => {
    render(LocationFormModal, {
      props: {
        open: true,
        warehouseId: 'warehouse-1',
        location: null,
        onclose: vi.fn(),
        onsaved: vi.fn()
      }
    });

    const notes = screen.getByLabelText('Notas');
    expect(notes.tagName).toBe('TEXTAREA');
    expect(notes).toHaveAttribute('rows', '4');
    expect(notes).toHaveAttribute(
      'placeholder',
      'Añada instrucciones operativas o contexto para el bodeguero'
    );
    expect(notes).toHaveClass(
      'w-full',
      'min-h-24',
      'rounded-lg',
      'border-border',
      'bg-surface',
      'resize-y',
      'focus:border-primary'
    );
  });

  it('conserva un código legado cuando la ruta normalizada no cambió', async () => {
    const onclose = vi.fn();
    serviceMocks.updateLocation.mockResolvedValue(legacyLocation);

    render(LocationFormModal, {
      props: {
        open: true,
        warehouseId: 'warehouse-1',
        location: legacyLocation,
        onclose,
        onsaved: vi.fn()
      }
    });

    expect(await screen.findByText('Código actual')).toBeInTheDocument();
    expect(screen.getByText('REC-01')).toBeInTheDocument();
    expect(screen.getByText(/código estable: se conserva/i)).toBeInTheDocument();
    expect(screen.queryByText(/cambiará a/i)).not.toBeInTheDocument();
    expect(screen.getByLabelText('Código de barras')).toHaveValue('7501234567890');
    expect(screen.getByLabelText('Código de verificación')).toHaveValue('REC-01-CHECK');

    await waitFor(() => expect(serviceMocks.previewLocationCode).not.toHaveBeenCalled());

    const submit = screen.getByRole('button', { name: 'Guardar cambios' });
    expect(submit).toBeEnabled();
    await fireEvent.submit(submit.closest('form')!);

    await waitFor(() => {
      expect(serviceMocks.updateLocation).toHaveBeenCalledWith(
        'warehouse-1',
        'location-legacy',
        expect.objectContaining({
          certified_max_weight_kg: 1000,
          operational_max_weight_kg: 900,
          notes: null,
          lifecycle_status: 'active',
          barcode: '7501234567890',
          verification_code: 'REC-01-CHECK',
          expected_updated_at: '2026-08-12T15:30:45Z'
        })
      );
    });
    expect(serviceMocks.previewLocationCode).not.toHaveBeenCalled();
    expect(onclose).toHaveBeenCalledOnce();
  });

  it('excluye la propia ubicacion al previsualizar un cambio fisico', async () => {
    serviceMocks.updateLocation.mockResolvedValueOnce(legacyLocation);
    serviceMocks.previewLocationCode.mockResolvedValueOnce({
      code: 'REC-01',
      normalized_components: {
        area: 'RECEPCION NORTE',
        aisle: 'R',
        rack: '01',
        level: '01',
        position: '01'
      },
      scheme_id: 'scheme-active',
      scheme_version: 2,
      code_exists: false,
      coordinates_exist: false
    });

    render(LocationFormModal, {
      props: {
        open: true,
        warehouseId: 'warehouse-1',
        location: legacyLocation,
        canRecode: true,
        onclose: vi.fn(),
        onsaved: vi.fn()
      }
    });

    await fireEvent.input(document.querySelector('#location-area')!, {
      target: { value: 'Recepcion norte' }
    });

    await waitFor(() => {
      expect(serviceMocks.previewLocationCode).toHaveBeenCalledWith(
        'warehouse-1',
        expect.objectContaining({
          area: 'Recepcion norte',
          exclude_location_id: 'location-legacy'
        }),
        expect.anything()
      );
    });
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Guardar cambios' })).toBeEnabled()
    );
    await fireEvent.submit(
      screen.getByRole('button', { name: 'Guardar cambios' }).closest('form')!
    );
    await waitFor(() =>
      expect(serviceMocks.updateLocation).toHaveBeenCalledWith(
        'warehouse-1',
        'location-legacy',
        expect.objectContaining({
          scheme_version: 2,
          expected_updated_at: '2026-08-12T15:30:45Z'
        })
      )
    );
  });

  it('bloquea ruta y transiciones no autorizadas, pero permite editar metadatos', async () => {
    render(LocationFormModal, {
      props: {
        open: true,
        warehouseId: 'warehouse-1',
        location: legacyLocation,
        canRecode: false,
        canCommission: false,
        canActivate: false,
        canDeactivate: false,
        onclose: vi.fn(),
        onsaved: vi.fn()
      }
    });

    expect(screen.getByLabelText('Área o zona')).toBeDisabled();
    expect(screen.getByLabelText(/^Pasillo/)).toBeDisabled();
    expect(screen.getByLabelText(/^Rack/)).toBeDisabled();
    expect(screen.getByLabelText(/^Nivel/)).toBeDisabled();
    expect(screen.getByLabelText(/^Posición/)).toBeDisabled();
    expect(screen.getByLabelText(/^Peso certificado/)).toBeEnabled();
    expect(screen.getByLabelText('Referencia externa')).toBeEnabled();
    expect(screen.getByLabelText('Código de barras')).toBeEnabled();
    expect(screen.getByText(/puede actualizar capacidad, secuencias/i)).toBeVisible();
    expect(serviceMocks.previewLocationCode).not.toHaveBeenCalled();
    expect(screen.getByRole('combobox', { name: 'Estado operativo' })).toBeDisabled();
    expect(screen.getByText(/estado operativo está protegido/i)).toBeVisible();
  });

  it('habilita solamente las transiciones cubiertas por los permisos efectivos', async () => {
    render(LocationFormModal, {
      props: {
        open: true,
        warehouseId: 'warehouse-1',
        location: legacyLocation,
        canDeactivate: true,
        onclose: vi.fn(),
        onsaved: vi.fn()
      }
    });

    const status = screen.getByRole('combobox', { name: 'Estado operativo' });
    expect(status).toBeEnabled();
    await fireEvent.focus(status);
    expect(screen.getByRole('option', { name: 'Retirada' })).toBeEnabled();
    expect(screen.getByRole('option', { name: 'Mantenimiento' })).toBeDisabled();
  });
});
