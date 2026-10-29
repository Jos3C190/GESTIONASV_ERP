import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import LocationTable from './LocationTable.svelte';
import type { LocationOut } from '../types';

const location: LocationOut = {
  id: 'loc-1',
  warehouse_id: 'warehouse-1',
  code: 'PICK-A-01-02-03',
  area: 'PICKING',
  aisle: 'A',
  rack: '01',
  level: '02',
  position: '03',
  capacity_group_id: null,
  certified_max_weight_kg: 1000,
  operational_max_weight_kg: 900,
  certified_usable_volume_m3: 100,
  operational_usable_volume_m3: 90,
  capacity_profile: 'rack',
  capacity_enforcement_mode: 'observe',
  capacity_status: 'available',
  storage_eligible: true,
  usable_length_m: 10,
  usable_width_m: 8,
  usable_height_m: 3,
  notes: null,
  location_type: 'standard',
  lifecycle_status: 'active',
  barcode: null,
  verification_code: null,
  pick_sequence: null,
  putaway_sequence: null,
  external_id: null,
  scheme_id: 'scheme-1',
  scheme_version: 1,
  code_source: 'generated',
  is_active: true,
  created_at: '2026-08-12T00:00:00Z',
  updated_at: null
};

describe('LocationTable', () => {
  it('presenta código, ruta y estado para escritorio y móvil', () => {
    render(LocationTable, { props: { items: [location], actionsFor: () => [] } });
    expect(screen.getAllByText('PICK-A-01-02-03')).toHaveLength(2);
    expect(screen.getAllByText('Activa')).toHaveLength(2);
    expect(screen.getAllByText('Configurada')).toHaveLength(2);
    expect(screen.getAllByLabelText('Ruta física')).toHaveLength(2);
    expect(screen.getAllByText('Directa del almacén')).toHaveLength(2);
  });

  it('no renderiza menús vacíos para usuarios de solo lectura', () => {
    render(LocationTable, { props: { items: [location], actionsFor: () => [] } });
    expect(screen.queryByRole('button', { name: /acciones para/i })).not.toBeInTheDocument();
  });
});
