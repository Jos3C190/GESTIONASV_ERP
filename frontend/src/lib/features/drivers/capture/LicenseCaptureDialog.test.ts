import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Driver, LicenseCapture, LicenseIssue } from '../api';
import LicenseCaptureDialog from './LicenseCaptureDialog.svelte';

const apiMock = vi.hoisted(() => ({
  openCapture: vi.fn(),
  getCapture: vi.fn(),
  startCaptureUpload: vi.fn(),
  completeCaptureUpload: vi.fn(),
  capturePreview: vi.fn(),
  checkCapture: vi.fn(),
  confirmCapture: vi.fn(),
  cancelCapture: vi.fn()
}));
const uploadDirect = vi.hoisted(() => vi.fn());
const permissionMock = vi.hoisted(() => ({ codes: new Set<string>() }));

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api')>()),
  driversApi: apiMock
}));
vi.mock('$lib/api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('$lib/api/client')>()),
  api: { documents: { uploadDirect } }
}));
vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: { hasPermission: (code: string) => permissionMock.codes.has(code) }
}));
vi.mock('./upload', () => ({
  checksumOf: vi.fn().mockResolvedValue('a'.repeat(64)),
  prepareForUpload: vi.fn(async (_source: Blob, side: string) => ({
    file: new File(['x'], `licencia-${side}.jpg`, { type: 'image/jpeg' }),
    quality: { blurry: false, dark: false, tooSmall: false }
  }))
}));

const driver = { id: 'driver-1' } as Driver;
const EMPTY = {
  license_class: null,
  expires: null,
  number: null,
  surnames: null,
  given_names: null,
  dui: null,
  issued: null,
  birth: null,
  control_number: null
};

function capture(overrides: Partial<LicenseCapture> = {}): LicenseCapture {
  return {
    id: 'capture-1',
    status: 'draft',
    failure_code: null,
    extraction_available: true,
    front: { document_id: null, status: null, extracted: false },
    back: { document_id: null, status: null, extracted: false },
    values: { ...EMPTY },
    issues: [],
    ...overrides
  };
}

const bothSides = {
  front: { document_id: 'f', status: 'active', extracted: true },
  back: { document_id: 'b', status: 'active', extracted: true }
};

async function reachReview(result: Partial<LicenseCapture>, issues: LicenseIssue[] = []) {
  apiMock.completeCaptureUpload.mockResolvedValue(capture({ ...bothSides, ...result }));
  apiMock.checkCapture.mockResolvedValue(issues);
  render(LicenseCaptureDialog, { open: true, driver, onconfirmed: vi.fn() });
  await waitFor(() => expect(apiMock.openCapture).toHaveBeenCalled());
  for (const side of ['frente', 'reverso']) {
    await screen.findByText(new RegExp(`Carga el ${side}`));
    const input = screen.getByText('Subir archivo').querySelector('input') as HTMLInputElement;
    Object.defineProperty(input, 'files', {
      value: [new File(['x'], 'foto.jpg', { type: 'image/jpeg' })],
      configurable: true
    });
    await fireEvent.change(input);
    await waitFor(() => expect(screen.queryByText(new RegExp(`Carga el ${side}`))).toBeNull());
  }
  await screen.findByRole('button', { name: 'Confirmar licencia' });
}

describe('LicenseCaptureDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    permissionMock.codes = new Set();
    apiMock.openCapture.mockResolvedValue(capture());
    apiMock.getCapture.mockResolvedValue(capture());
    apiMock.startCaptureUpload.mockResolvedValue({ upload_url: 'u' });
    apiMock.capturePreview.mockResolvedValue({ url: 'http://storage/foto', expires_at: '' });
    uploadDirect.mockResolvedValue(undefined);
    URL.createObjectURL = vi.fn(() => 'blob:foto');
    URL.revokeObjectURL = vi.fn();
  });

  afterEach(() => cleanup());

  it('prefills what the model read and never claims the license is authentic', async () => {
    await reachReview({
      status: 'ready',
      values: { ...EMPTY, number: '0101-010101-101-1', expires: '02-2099' }
    });

    expect(screen.getByLabelText(/Número de licencia/)).toHaveValue('0101-010101-101-1');
    expect(screen.getByLabelText(/Vence/)).toHaveValue('02-2099');
    expect(screen.getByText(/no certifican que el documento sea auténtico/)).toBeInTheDocument();
  });

  it('still allows typing the data when the reader is unavailable', async () => {
    await reachReview({
      status: 'draft',
      extraction_available: false,
      front: { document_id: 'f', status: 'active', extracted: false },
      back: { document_id: 'b', status: 'active', extracted: false }
    });

    expect(screen.getByText(/lectura automática no está disponible/)).toBeInTheDocument();
    await fireEvent.input(screen.getByLabelText(/Número de licencia/), {
      target: { value: '0101-010101-101-1' }
    });
    expect(screen.getByRole('button', { name: 'Confirmar licencia' })).toBeEnabled();
  });

  it('asks to acknowledge warnings before confirming', async () => {
    const warning: LicenseIssue = {
      code: 'dui_check_digit',
      severity: 'warning',
      field: 'dui',
      message: 'El dígito verificador del DUI no cuadra.'
    };
    await reachReview({ status: 'ready', issues: [warning] }, [warning]);
    const confirm = screen.getByRole('button', { name: 'Confirmar licencia' });
    await screen.findByText(warning.message);
    expect(confirm).toBeDisabled();

    await fireEvent.click(screen.getByRole('checkbox'));

    expect(confirm).toBeEnabled();
  });

  it('blocks a mismatch for users who cannot authorize it', async () => {
    const mismatch: LicenseIssue = {
      code: 'name_mismatch',
      severity: 'mismatch',
      field: 'surnames',
      message: 'El nombre no coincide con el del empleado.'
    };
    await reachReview({ status: 'ready', issues: [mismatch] }, [mismatch]);

    expect(await screen.findByText(/pide autorización a un administrador/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Confirmar licencia' })).toBeDisabled();
  });

  it('lets an authorized user continue only with a reason', async () => {
    permissionMock.codes = new Set(['drivers:license_override']);
    const mismatch: LicenseIssue = {
      code: 'dui_mismatch',
      severity: 'mismatch',
      field: 'dui',
      message: 'El DUI no coincide con el del empleado.'
    };
    await reachReview({ status: 'ready', issues: [mismatch] }, [mismatch]);
    const reason = await screen.findByLabelText(/Motivo de la excepción/);
    const confirm = screen.getByRole('button', { name: 'Confirmar licencia' });
    expect(confirm).toBeDisabled();

    await fireEvent.input(reason, { target: { value: 'Error en expediente' } });

    expect(confirm).toBeEnabled();
  });

  it('blocks confirming while a value is invalid, even with no warnings', async () => {
    const invalid: LicenseIssue = {
      code: 'expiry_invalid',
      severity: 'error',
      field: 'expires',
      message: 'Indica el vencimiento como MM-AAAA.'
    };
    await reachReview({ status: 'ready', issues: [invalid] }, [invalid]);

    await screen.findByText(invalid.message);

    expect(screen.getByRole('button', { name: 'Confirmar licencia' })).toBeDisabled();
  });

  it('resumes an unfinished capture with its photos at the review step', async () => {
    apiMock.openCapture.mockResolvedValue(capture({ ...bothSides, status: 'ready' }));
    apiMock.checkCapture.mockResolvedValue([]);

    render(LicenseCaptureDialog, { open: true, driver, onconfirmed: vi.fn() });

    expect(await screen.findByRole('button', { name: 'Confirmar licencia' })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByAltText('Reverso')).toBeInTheDocument());
    expect(screen.getByAltText('Frente')).toHaveAttribute('src', 'http://storage/foto');
  });

  it('retaking the front does not force retaking the back', async () => {
    await reachReview({ status: 'ready' });

    await fireEvent.click(screen.getByRole('button', { name: 'Repetir fotos' }));
    await fireEvent.click(await screen.findByRole('button', { name: 'Continuar con esta foto' }));
    await fireEvent.click(await screen.findByRole('button', { name: 'Continuar con esta foto' }));

    expect(await screen.findByRole('button', { name: 'Confirmar licencia' })).toBeInTheDocument();
    expect(apiMock.startCaptureUpload).toHaveBeenCalledTimes(2);
  });

  it('does not offer confirmation until both photos are in', async () => {
    render(LicenseCaptureDialog, { open: true, driver, onconfirmed: vi.fn() });

    await screen.findByText(/Carga el frente/);

    expect(screen.queryByRole('button', { name: 'Confirmar licencia' })).toBeNull();
  });
});
