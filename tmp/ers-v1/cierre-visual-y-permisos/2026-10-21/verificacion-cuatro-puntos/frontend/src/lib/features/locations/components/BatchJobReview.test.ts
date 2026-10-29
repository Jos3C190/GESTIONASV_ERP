import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import type { LocationBatchJob, LocationBatchRow } from '../types';
import BatchJobReview from './BatchJobReview.svelte';

const serviceMocks = vi.hoisted(() => ({
  getLocationBatch: vi.fn()
}));

vi.mock('../services', () => serviceMocks);

function row(rowNumber: number): LocationBatchRow {
  return {
    id: `row-${rowNumber}`,
    row_number: rowNumber,
    operation: 'create',
    code: `A-${rowNumber}`,
    normalized_data: {
      aisle: 'A',
      rack: '01',
      level: '01',
      position: String(rowNumber)
    },
    diff: {},
    errors: []
  };
}

function job(rows: LocationBatchRow[], page: number): LocationBatchJob {
  return {
    id: 'job-1',
    warehouse_id: 'warehouse-1',
    kind: 'generate',
    status: 'preview',
    idempotency_key: 'generate-test',
    input_checksum: 'checksum',
    scheme_id: 'scheme-1',
    scheme_version: 2,
    total_rows: 5,
    create_count: 5,
    update_count: 0,
    unchanged_count: 0,
    conflict_count: 0,
    error_count: 0,
    summary: {},
    rows_meta: { page, size: 2, total: 5, pages: 3 },
    created_by: 'user-1',
    published_by: null,
    created_at: '2026-08-12T00:00:00Z',
    published_at: null,
    rows
  };
}

describe('BatchJobReview', () => {
  it('revisa un lote por páginas sin renderizar todas sus filas', async () => {
    serviceMocks.getLocationBatch.mockResolvedValueOnce(job([row(3), row(4)], 2));
    render(BatchJobReview, { props: { job: job([row(1), row(2)], 1), pageSize: 2 } });

    expect(screen.getByText('A-1')).toBeVisible();
    expect(screen.getByText('A-2')).toBeVisible();
    expect(screen.queryByText('A-3')).not.toBeInTheDocument();
    expect(screen.getByText(/Filas 1–2 de 5/)).toBeVisible();

    await fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }));

    await waitFor(() =>
      expect(serviceMocks.getLocationBatch).toHaveBeenCalledWith(
        'job-1',
        2,
        2,
        expect.any(AbortSignal)
      )
    );
    expect(await screen.findByText('A-3')).toBeVisible();
    expect(screen.getByText('A-4')).toBeVisible();
    expect(screen.getByText(/Filas 3–4 de 5/)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Anterior' })).toBeEnabled();
  });
});
