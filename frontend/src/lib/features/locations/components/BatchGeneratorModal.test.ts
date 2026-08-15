import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { LocationBatchJob } from '../types';
import BatchGeneratorModal from './BatchGeneratorModal.svelte';

const serviceMocks = vi.hoisted(() => ({
  previewGeneratedLocations: vi.fn(),
  publishLocationBatch: vi.fn()
}));

vi.mock('../services', () => serviceMocks);

const previewJob: LocationBatchJob = {
  id: 'job-1',
  warehouse_id: 'warehouse-1',
  kind: 'generate',
  status: 'preview',
  idempotency_key: 'generate-test',
  input_checksum: 'checksum',
  scheme_id: 'scheme-1',
  scheme_version: 1,
  total_rows: 80,
  create_count: 80,
  update_count: 0,
  unchanged_count: 0,
  conflict_count: 0,
  error_count: 0,
  summary: {},
  required_permissions: ['locations.bulk', 'locations.create'],
  rows_meta: { page: 1, size: 100, total: 80, pages: 1 },
  created_by: 'user-1',
  published_by: null,
  created_at: '2026-08-12T00:00:00Z',
  published_at: null,
  rows: []
};

describe('BatchGeneratorModal', () => {
  beforeEach(() => vi.clearAllMocks());

  it('inicia el esquema A/R/N/P con un pasillo numérico y orienta sobre pasillos alfabéticos', () => {
    render(BatchGeneratorModal, {
      props: {
        open: true,
        warehouseId: 'warehouse-1',
        onclose: vi.fn(),
        onpublished: vi.fn()
      }
    });

    const aisleStart = screen.getAllByLabelText(/^Desde/)[0];
    const aisleEnd = screen.getAllByLabelText(/^Hasta/)[0];
    expect(aisleStart).toHaveAttribute('id', 'batch-aisle-start');
    expect(aisleStart).toHaveValue('1');
    expect(aisleEnd).toHaveValue('1');
    expect(aisleStart).toHaveAttribute('placeholder', '01');
    expect(screen.getByText(/pasillos A, B, C configure ese segmento con ancho 0/i)).toBeVisible();
  });

  it('bloquea la publicación cuando el impacto requiere permisos faltantes', async () => {
    serviceMocks.previewGeneratedLocations.mockResolvedValueOnce(previewJob);
    render(BatchGeneratorModal, {
      props: {
        open: true,
        warehouseId: 'warehouse-1',
        hasPermission: (permission: string) => permission === 'locations.bulk',
        onclose: vi.fn(),
        onpublished: vi.fn()
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Generar vista previa' }));

    expect(
      await screen.findByText(/No puede publicar este impacto con sus permisos actuales/i)
    ).toBeVisible();
    expect(screen.getByText(/Crear ubicaciones/)).toBeVisible();
    expect(screen.getByRole('checkbox')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Publicar lote' })).toBeDisabled();
  });
});
