import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { DocumentRecordOut } from '$lib/api/client';
import type { OwnedDocumentsApi } from '$lib/api/owned-documents';
import Modal from '$lib/components/ui/Modal.svelte';
import DriverLicensePreview from './DriverLicensePreview.svelte';

const record: DocumentRecordOut = {
  id: 'doc-1',
  company_id: 'company-1',
  module: 'employees',
  owner_type: 'employee',
  owner_id: 'employee-1',
  owner_label: 'Conductor de prueba',
  owner_deleted: false,
  category_id: 'license',
  category_name: 'Licencia de conducir',
  category_group: 'Identificación',
  title: 'Licencia',
  description: null,
  reference_code: null,
  issuer: null,
  issued_on: null,
  expires_on: '2028-06-30',
  confidentiality: 'internal',
  tags: [],
  version_group_id: 'group-1',
  version_number: 1,
  is_current: true,
  replaces_document_id: null,
  business_status: 'current',
  original_filename: 'licencia.jpg',
  extension: 'jpg',
  content_type: 'image/jpeg',
  size_bytes: 128,
  checksum_sha256: 'test',
  technical_status: 'active',
  failure_code: null,
  upload_expires_at: null,
  scanned_at: null,
  uploaded_by: null,
  created_by: null,
  updated_by: null,
  created_at: null,
  updated_at: null,
  ocr_status: null,
  ocr_available: false,
  ocr_failure_code: null,
  ocr_completed_at: null
};
const get = vi.fn();
const previewUrl = vi.fn();
const owner: OwnedDocumentsApi = {
  basePath: '/drivers/d1',
  get,
  previewUrl,
  categories: vi.fn(),
  list: vi.fn(),
  initiate: vi.fn(),
  complete: vi.fn(),
  update: vi.fn(),
  replace: vi.fn(),
  versions: vi.fn(),
  downloadUrl: vi.fn()
};
const props = { owner, documentId: 'doc-1', name: 'Conductor de prueba' };
const future = { url: 'https://example.invalid/licencia.jpg', expires_at: '2999-01-01T00:00:00Z' };

beforeEach(() => {
  vi.clearAllMocks();
  get.mockReset().mockResolvedValue(record);
  previewUrl.mockReset().mockResolvedValue(future);
});
afterEach(cleanup);

async function loadImage() {
  const image = await screen.findByRole('img', {
    name: 'Licencia de conducir de Conductor de prueba'
  });
  await fireEvent.load(image);
  return image;
}

describe('driver license preview', () => {
  it('loads the owned image and expands it with zoom and focus restoration', async () => {
    render(DriverLicensePreview, props);
    expect(screen.getByRole('status')).toHaveTextContent('Cargando licencia');
    const image = await loadImage();
    expect(image).toHaveAttribute('src', future.url);
    expect(get).toHaveBeenCalledWith('doc-1');
    expect(previewUrl).toHaveBeenCalledWith('doc-1');
    const trigger = screen.getByRole('button', { name: 'Ampliar licencia de conducir' });
    trigger.focus();
    await fireEvent.click(trigger);
    const viewer = await screen.findByRole('dialog', {
      name: 'Licencia de conducir · Conductor de prueba'
    });
    expect(viewer).toHaveStyle({ 'z-index': '1100' });
    await fireEvent.click(within(viewer).getByRole('button', { name: 'Acercar' }));
    expect(within(viewer).getByText('150%')).toBeVisible();
    await fireEvent.keyDown(within(viewer).getByRole('button', { name: 'Cerrar visor' }), {
      key: 'Escape'
    });
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it('keeps non-image documents available through the document manager without signing an image URL', async () => {
    get.mockResolvedValue({ ...record, content_type: 'application/pdf', extension: 'pdf' });
    render(DriverLicensePreview, props);
    expect(await screen.findByText('Consulta este formato desde Documentos.')).toBeVisible();
    expect(previewUrl).not.toHaveBeenCalled();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });

  it('does not request a preview for a document still pending antivirus', async () => {
    get.mockResolvedValue({ ...record, technical_status: 'pending_scan' });
    render(DriverLicensePreview, props);
    expect(await screen.findByText(/Consulta el estado en Documentos/)).toBeVisible();
    expect(previewUrl).not.toHaveBeenCalled();
  });

  it('offers recovery after a permission or network error without exposing server details', async () => {
    get.mockRejectedValueOnce(new Error('sensitive transport details'));
    render(DriverLicensePreview, props);
    const retry = await screen.findByRole('button', { name: 'Reintentar vista previa' });
    expect(screen.queryByText('sensitive transport details')).not.toBeInTheDocument();
    await fireEvent.click(retry);
    await loadImage();
    expect(screen.getByRole('button', { name: 'Ampliar licencia de conducir' })).toBeEnabled();
  });

  it('refreshes a broken or expired image only when the user retries', async () => {
    render(DriverLicensePreview, props);
    await fireEvent.error(await screen.findByRole('img'));
    expect(previewUrl).toHaveBeenCalledOnce();
    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar vista previa' }));
    await loadImage();
    expect(previewUrl).toHaveBeenCalledTimes(2);
  });

  it('renews a short-lived URL before opening the full image', async () => {
    previewUrl
      .mockResolvedValueOnce({ ...future, expires_at: '2000-01-01T00:00:00Z' })
      .mockResolvedValueOnce({ ...future, url: 'https://example.invalid/renewed.jpg' });
    render(DriverLicensePreview, props);
    await loadImage();
    await fireEvent.click(screen.getByRole('button', { name: 'Ampliar licencia de conducir' }));
    const viewer = await screen.findByRole('dialog');
    expect(within(viewer).getByRole('img')).toHaveAttribute(
      'src',
      'https://example.invalid/renewed.jpg'
    );
    expect(previewUrl).toHaveBeenCalledTimes(2);
  });

  it('ignores stale preview responses after switching to another driver', async () => {
    let resolveOld!: (value: typeof future) => void;
    previewUrl.mockReturnValueOnce(
      new Promise<typeof future>((resolve) => {
        resolveOld = resolve;
      })
    );
    const { rerender } = render(DriverLicensePreview, props);
    await waitFor(() => expect(previewUrl).toHaveBeenCalledOnce());
    const nextUrl = 'https://example.invalid/next-driver.jpg';
    const nextOwner = {
      ...owner,
      basePath: '/drivers/d2',
      get: vi.fn().mockResolvedValue({ ...record, id: 'doc-2' }),
      previewUrl: vi.fn().mockResolvedValue({ ...future, url: nextUrl })
    };
    await rerender({ ...props, owner: nextOwner, documentId: 'doc-2', name: 'Segundo conductor' });
    const nextImage = await screen.findByRole('img', {
      name: 'Licencia de conducir de Segundo conductor'
    });
    resolveOld(future);
    await waitFor(() => expect(nextImage).toHaveAttribute('src', nextUrl));
  });

  it('closes only the viewer when opened over the compact profile dialog', async () => {
    const closeProfile = vi.fn();
    render(Modal, { open: true, title: 'Resumen del conductor', onclose: closeProfile });
    render(DriverLicensePreview, props);
    await loadImage();
    await fireEvent.click(screen.getByRole('button', { name: 'Ampliar licencia de conducir' }));
    const viewer = await screen.findByRole('dialog', {
      name: 'Licencia de conducir · Conductor de prueba'
    });
    await fireEvent.keyDown(within(viewer).getByRole('button', { name: 'Cerrar visor' }), {
      key: 'Escape'
    });
    expect(closeProfile).not.toHaveBeenCalled();
    expect(screen.getByRole('dialog', { name: 'Resumen del conductor' })).toBeVisible();
  });
  it('allows keyboard panning of the expanded license', async () => {
    render(DriverLicensePreview, props);
    await loadImage();
    await fireEvent.click(screen.getByRole('button', { name: 'Ampliar licencia de conducir' }));
    const viewer = await screen.findByRole('dialog');
    await fireEvent.load(within(viewer).getByRole('img'));
    await fireEvent.click(within(viewer).getByRole('button', { name: 'Acercar' }));
    await fireEvent.keyDown(within(viewer).getByRole('button', { name: 'Cerrar visor' }), {
      key: 'ArrowRight'
    });
    await fireEvent.keyDown(within(viewer).getByRole('button', { name: 'Cerrar visor' }), {
      key: 'ArrowDown'
    });
    expect(within(viewer).getByRole('img').style.transform).toContain('translate(-60px, -60px)');
  });

  it('recovers from a failed image GET in the expanded viewer', async () => {
    render(DriverLicensePreview, props);
    await loadImage();
    await fireEvent.click(screen.getByRole('button', { name: 'Ampliar licencia de conducir' }));
    const viewer = await screen.findByRole('dialog');
    await fireEvent.error(within(viewer).getByRole('img'));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    const retry = screen.getByRole('button', { name: 'Reintentar vista previa' });
    await waitFor(() => expect(retry).toHaveFocus());
    await fireEvent.click(retry);
    await loadImage();
    expect(previewUrl).toHaveBeenCalledTimes(2);
  });
});
