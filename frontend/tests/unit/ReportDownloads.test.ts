import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ReportDownloads from '$lib/components/ui/ReportDownloads.svelte';
import { saveRetaceoPreview } from './retaceo-preview';
import { tick } from 'svelte';

const mocks = vi.hoisted(() => ({
  download: vi.fn(),
  company: { id: 'company' },
  branch: { id: 'branch' }
}));
vi.mock('$lib/api/client', () => ({ apiDownload: mocks.download }));
vi.mock('$lib/stores/company.svelte', () => ({ company: mocks.company }));
vi.mock('$lib/stores/branch.svelte', () => ({ branch: mocks.branch }));

describe('Report downloads', () => {
  beforeEach(() => {
    mocks.download.mockReset();
    mocks.company.id = 'company';
    mocks.branch.id = 'branch';
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:report');
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  });
  afterEach(() => vi.restoreAllMocks());

  it('downloads the chosen format with a filename and reports completion', async () => {
    mocks.download.mockResolvedValue(new Blob(['report']));
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click');
    const { container } = render(ReportDownloads, {
      path: '/retaceos/ret/export',
      code: 'RET-00021'
    });
    saveRetaceoPreview('descargas-retaceo', container);
    await fireEvent.click(screen.getByRole('button', { name: 'Descargar Excel' }));
    await screen.findByText(/Excel preparado/);
    expect(mocks.download).toHaveBeenCalledWith('/retaceos/ret/export?format=xlsx');
    expect(click.mock.instances[0]).toHaveProperty('download', 'RET-00021.xlsx');
  });

  it('prevents duplicate exports while preparing and lets the user retry a failure', async () => {
    let reject!: (cause: Error) => void;
    mocks.download.mockReturnValueOnce(
      new Promise((_, fail) => {
        reject = fail;
      })
    );
    const { container } = render(ReportDownloads, {
      path: '/retaceos/ret/export',
      code: 'RET-00021'
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Descargar PDF' }));
    expect(screen.getByRole('button', { name: 'Descargar Excel' })).toBeDisabled();
    reject(new Error('No se pudo preparar el reporte'));
    await screen.findByRole('alert');
    saveRetaceoPreview('descargas-error', container);
    mocks.download.mockResolvedValue(new Blob(['pdf']));
    await fireEvent.click(screen.getByRole('button', { name: 'Descargar PDF' }));
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
    await screen.findByText(/PDF preparado/);
  });

  it('offers only PDF for the general consolidation', () => {
    const { container } = render(ReportDownloads, {
      path: '/purchase-consolidations/con/export',
      code: 'CON-001',
      formats: ['pdf']
    });
    expect(screen.getByRole('button', { name: 'Descargar PDF' })).toBeEnabled();
    expect(screen.queryByRole('button', { name: 'Descargar Excel' })).not.toBeInTheDocument();
    saveRetaceoPreview('descargas-consolidado', container);
  });

  it('discards a response if the user changes documents during preparation', async () => {
    let finish!: (blob: Blob) => void;
    mocks.download.mockReturnValueOnce(
      new Promise((resolve) => {
        finish = resolve;
      })
    );
    const { rerender } = render(ReportDownloads, {
      path: '/retaceos/ret/export',
      code: 'RET-00021'
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Descargar PDF' }));
    await rerender({ path: '/retaceos/other/export', code: 'RET-00022' });
    finish(new Blob(['old report']));
    await screen.findByRole('alert');
    expect(HTMLAnchorElement.prototype.click).not.toHaveBeenCalled();
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Cambió el documento, la empresa o la sucursal'
    );
  });

  it.each(['company', 'branch'] as const)(
    'discards a response after changing %s',
    async (context) => {
      let finish!: (blob: Blob) => void;
      mocks.download.mockReturnValueOnce(
        new Promise((resolve) => {
          finish = resolve;
        })
      );
      render(ReportDownloads, { path: '/retaceos/ret/export', code: 'RET-00021' });
      await fireEvent.click(screen.getByRole('button', { name: 'Descargar PDF' }));
      mocks[context].id = 'other-context';
      finish(new Blob(['old report']));
      await screen.findByRole('alert');
      expect(HTMLAnchorElement.prototype.click).not.toHaveBeenCalled();
    }
  );

  it('does not start a download after unmounting', async () => {
    let finish!: (blob: Blob) => void;
    const pending = new Promise<Blob>((resolve) => {
      finish = resolve;
    });
    mocks.download.mockReturnValueOnce(pending);
    const { unmount } = render(ReportDownloads, {
      path: '/retaceos/ret/export',
      code: 'RET-00021'
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Descargar PDF' }));
    unmount();
    finish(new Blob(['old report']));
    await pending;
    await tick();
    expect(HTMLAnchorElement.prototype.click).not.toHaveBeenCalled();
    expect(URL.createObjectURL).not.toHaveBeenCalled();
  });
});
