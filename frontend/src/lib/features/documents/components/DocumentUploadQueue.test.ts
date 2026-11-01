import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { DocumentCategoryOut } from '$lib/api/client';
import { HttpError } from '$lib/api/client';
import type { OwnedDocumentsApi } from '$lib/api/owned-documents';
import DocumentUploadQueue from './DocumentUploadQueue.svelte';

const transport = vi.hoisted(() => ({
  uploadDirect: vi.fn(),
  initiate: vi.fn(),
  complete: vi.fn()
}));
vi.mock('$lib/api/client', async (original) => ({
  ...(await original<typeof import('$lib/api/client')>()),
  api: { documents: transport }
}));

const license: DocumentCategoryOut = {
  id: 'license-id',
  company_id: 'company-test',
  module: 'employees',
  code: 'driver_license',
  name: 'Licencia de conducir',
  group_name: 'Licencias',
  description: null,
  sort_order: 1,
  document_count: 0,
  is_active: true,
  requires_expiry: true,
  compliance_required: true
};
const other: DocumentCategoryOut = {
  ...license,
  id: 'other-id',
  code: 'other',
  name: 'Otros',
  requires_expiry: false,
  compliance_required: false
};
let serial = 0;
const initiate = vi.fn();
const complete = vi.fn();
const replace = vi.fn();
const owner: OwnedDocumentsApi = {
  basePath: '/drivers/driver-1',
  initiate,
  complete,
  categories: vi.fn(),
  get: vi.fn(),
  list: vi.fn(),
  update: vi.fn(),
  replace,
  versions: vi.fn(),
  previewUrl: vi.fn(),
  downloadUrl: vi.fn()
};
const finished = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  serial = 0;
  vi.stubGlobal('crypto', {
    randomUUID: () => `fixture-${++serial}`,
    subtle: { digest: vi.fn().mockResolvedValue(new Uint8Array(32).buffer) }
  });
  initiate.mockResolvedValue({
    document_id: 'document-id',
    upload_url: 'https://storage.invalid/test',
    required_headers: {},
    expires_at: '2027-01-01'
  });
  complete.mockResolvedValue({ id: 'document-id' });
  replace.mockResolvedValue({ document_id: 'replacement-id' });
  transport.uploadDirect.mockResolvedValue(undefined);
  transport.initiate.mockResolvedValue({ document_id: 'general-id' });
  transport.complete.mockResolvedValue({ id: 'general-id' });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function addFile(name = 'licencia.jpg') {
  const file = new File(['fixture'], name, { type: 'image/jpeg' });
  Object.defineProperty(file, 'arrayBuffer', {
    value: async () => new Uint8Array([1, 2, 3]).buffer
  });
  await fireEvent.change(
    screen.getByLabelText('Seleccionar documentos para cargar', { selector: 'input[type="file"]' }),
    { target: { files: [file] } }
  );
}
const category = () => screen.getByLabelText('Categoría', { selector: '#document-category' });
const expiry = () =>
  screen.getByLabelText(/Fecha de vencimiento/, { selector: '#document-expires' });
const upload = () => screen.getByRole('button', { name: /^Cargar / });

describe('document upload metadata', () => {
  it('uses category and expiry edited AFTER the file was selected', async () => {
    render(DocumentUploadQueue, {
      categories: [other, license],
      owner,
      onclose: vi.fn(),
      onfinished: finished
    });
    await addFile();
    await fireEvent.change(category(), { target: { value: license.id } });
    expect(category()).toHaveValue(license.id);
    expect(expiry()).toBeRequired();
    await fireEvent.input(expiry(), { target: { value: '2028-10-31' } });
    await fireEvent.input(screen.getByLabelText('Código o referencia'), {
      target: { value: 'LIC-123' }
    });
    await fireEvent.click(upload());
    await waitFor(() => expect(finished).toHaveBeenCalledOnce());
    expect(initiate).toHaveBeenCalledWith(
      expect.objectContaining({
        category_id: license.id,
        expires_on: '2028-10-31',
        reference_code: 'LIC-123'
      })
    );
    expect(transport.uploadDirect).toHaveBeenCalledOnce();
    expect(complete).toHaveBeenCalledWith('document-id');
  });

  it('selects the sole permitted owner category and omits unsupported Otros', async () => {
    render(DocumentUploadQueue, { categories: [license], owner, onclose: vi.fn() });
    await waitFor(() => expect(category()).toHaveValue(license.id));
    expect(screen.queryByRole('option', { name: 'Otros' })).not.toBeInTheDocument();
    expect(expiry()).toBeRequired();
  });

  it('explains missing expiry before requesting authorization, then retries with corrected metadata', async () => {
    render(DocumentUploadQueue, {
      categories: [license],
      owner,
      onclose: vi.fn(),
      onfinished: finished
    });
    await addFile();
    await fireEvent.click(upload());
    expect(await screen.findByText(/Indica la fecha de vencimiento/)).toBeVisible();
    expect(initiate).not.toHaveBeenCalled();
    await fireEvent.input(expiry(), { target: { value: '2028-10-31' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar este archivo' }));
    await waitFor(() => expect(finished).toHaveBeenCalledOnce());
    expect(initiate).toHaveBeenCalledWith(
      expect.objectContaining({ category_id: license.id, expires_on: '2028-10-31' })
    );
  });

  it('updates failed files before retrying a server rejection', async () => {
    initiate.mockRejectedValueOnce(
      new HttpError(
        'document_category_invalid',
        'La categoría no está disponible en este módulo.',
        422
      )
    );
    render(DocumentUploadQueue, {
      categories: [other, license],
      owner,
      onclose: vi.fn(),
      onfinished: finished
    });
    await addFile();
    await fireEvent.click(upload());
    await screen.findByText('La categoría no está disponible en este módulo.');
    await fireEvent.change(category(), { target: { value: license.id } });
    await fireEvent.input(expiry(), { target: { value: '2029-02-01' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar este archivo' }));
    await waitFor(() => expect(finished).toHaveBeenCalledOnce());
    expect(initiate).toHaveBeenLastCalledWith(
      expect.objectContaining({ category_id: license.id, expires_on: '2029-02-01' })
    );
  });

  it('preserves deliberate per-file values when common defaults change', async () => {
    render(DocumentUploadQueue, {
      categories: [other, license],
      owner,
      onclose: vi.fn(),
      onfinished: finished
    });
    await addFile();
    await fireEvent.input(screen.getByLabelText('Título', { selector: 'input[id^="title-"]' }), {
      target: { value: 'Título individual' }
    });
    await fireEvent.input(screen.getByLabelText('Título (opcional)'), {
      target: { value: 'Título común' }
    });
    await fireEvent.change(category(), { target: { value: license.id } });
    await fireEvent.input(expiry(), { target: { value: '2028-10-31' } });
    await fireEvent.click(upload());
    await waitFor(() => expect(finished).toHaveBeenCalledOnce());
    expect(initiate).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Título individual',
        category_id: license.id,
        expires_on: '2028-10-31'
      })
    );
  });

  it('can retry failed items with the main Cargar action', async () => {
    render(DocumentUploadQueue, {
      categories: [license],
      owner,
      onclose: vi.fn(),
      onfinished: finished
    });
    await addFile();
    await fireEvent.click(upload());
    await screen.findByText(/Indica la fecha de vencimiento/);
    await fireEvent.input(expiry(), { target: { value: '2028-10-31' } });
    await fireEvent.click(upload());
    await waitFor(() => expect(finished).toHaveBeenCalledOnce());
  });

  it('keeps the generic Otros upload available outside restricted owners', async () => {
    render(DocumentUploadQueue, {
      categories: [other, license],
      onclose: vi.fn(),
      onfinished: finished
    });
    await addFile('general.jpg');
    await fireEvent.click(upload());
    await waitFor(() => expect(finished).toHaveBeenCalledOnce());
    expect(transport.initiate).toHaveBeenCalledOnce();
    expect(initiate).not.toHaveBeenCalled();
  });
  it('preserves per-file category and expiry while common defaults change', async () => {
    render(DocumentUploadQueue, {
      categories: [other, license],
      owner,
      onclose: vi.fn(),
      onfinished: finished
    });
    await addFile();
    await fireEvent.change(
      screen.getByLabelText('Categoría', { selector: 'select[id^="category-"]' }),
      { target: { value: license.id } }
    );
    await fireEvent.input(
      screen.getByLabelText('Vencimiento', { selector: 'input[id^="expires-"]' }),
      { target: { value: '2029-10-31' } }
    );
    await fireEvent.input(screen.getByLabelText('Título (opcional)'), {
      target: { value: 'Licencia individual' }
    });
    await fireEvent.click(upload());
    await waitFor(() => expect(finished).toHaveBeenCalledOnce());
    expect(initiate).toHaveBeenCalledWith(
      expect.objectContaining({
        category_id: license.id,
        expires_on: '2029-10-31',
        title: 'Licencia individual'
      })
    );
  });

  it('keeps replacement metadata inheritance under the server validation rules', async () => {
    render(DocumentUploadQueue, {
      categories: [license],
      owner,
      replaceDocumentId: 'previous-document',
      initialCategoryId: license.id,
      onclose: vi.fn(),
      onfinished: finished
    });
    await addFile();
    await fireEvent.click(screen.getByRole('button', { name: 'Crear nueva versión' }));
    await waitFor(() => expect(finished).toHaveBeenCalledOnce());
    expect(replace).toHaveBeenCalledWith(
      'previous-document',
      expect.objectContaining({ category_id: license.id })
    );
    expect(initiate).not.toHaveBeenCalled();
  });
});
