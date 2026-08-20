import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import LocationImportModal from './LocationImportModal.svelte';

vi.mock('../services', () => ({
  previewLocationImport: vi.fn(),
  publishLocationBatch: vi.fn()
}));

describe('LocationImportModal', () => {
  it('documenta el contrato completo y la semántica de actualización del archivo', () => {
    render(LocationImportModal, {
      props: {
        open: true,
        warehouseId: 'warehouse-1',
        onclose: vi.fn(),
        onpublished: vi.fn()
      }
    });

    expect(screen.getByText('Columnas admitidas')).toBeInTheDocument();
    expect(screen.getByText(/aisle, rack, level, position/)).toBeInTheDocument();
    expect(screen.getByText(/lifecycle_status, barcode, verification_code/)).toBeInTheDocument();
    expect(
      screen.getByText(
        /area, certified_max_weight_kg, operational_max_weight_kg,[\s\S]*certified_usable_volume_m3,[\s\S]*capacity_enforcement_mode,[\s\S]*external_id, notes/
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText(/una columna omitida del archivo conserva el valor existente/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/una celda vacía limpia los campos anulables/i)).toBeInTheDocument();
    expect(screen.getByText(/el código siempre se autogenera/i)).toBeInTheDocument();
  });
});
