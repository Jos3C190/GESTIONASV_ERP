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
        /area, capacity, location_type, lifecycle_status, barcode, verification_code,[\s\S]*pick_sequence, putaway_sequence, external_id, notes/
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText(/una columna omitida del archivo conserva el valor existente/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/una celda vacía limpia los campos anulables/i)).toBeInTheDocument();
    expect(screen.getByText(/el código siempre se autogenera/i)).toBeInTheDocument();
  });
});
