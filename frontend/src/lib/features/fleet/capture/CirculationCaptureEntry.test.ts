import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { CaptureIssue, CaptureState } from '$lib/features/document-capture/types';
import type { FleetVehicle } from '../api';
import { confirmationNotice, filledFields } from './circulation-config';
import CirculationCaptureEntry from './CirculationCaptureEntry.svelte';

const captureApi = vi.hoisted(() => ({
  open: vi.fn(),
  get: vi.fn(),
  startUpload: vi.fn(),
  completeUpload: vi.fn(),
  preview: vi.fn(),
  check: vi.fn(),
  confirm: vi.fn(),
  cancel: vi.fn()
}));
const capabilities = vi.hoisted(() => vi.fn());
const permissionMock = vi.hoisted(() => ({ codes: new Set<string>(['fleet_documents:upload']) }));

vi.mock('../api', async (importOriginal) => {
  const original = await importOriginal<typeof import('../api')>();
  return {
    ...original,
    fleetApi: {
      ...original.fleetApi,
      circulationCaptures: () => captureApi,
      circulationCaptureCapabilities: capabilities
    }
  };
});
const prepareMock = vi.hoisted(() => vi.fn());
const uploadDirect = vi.hoisted(() => vi.fn());
vi.mock('$lib/features/document-capture/upload', () => ({
  checksumOf: vi.fn().mockResolvedValue('a'.repeat(64)),
  prepareForUpload: prepareMock
}));
vi.mock('$lib/api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('$lib/api/client')>()),
  api: { documents: { uploadDirect } }
}));
vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: { hasPermission: (code: string) => permissionMock.codes.has(code) }
}));

const vehicle = { id: 'vehicle-1', plate: 'PFAK3420' } as FleetVehicle;
const VALUES = {
  plate: 'PFAK3420-2007',
  expires: '05-2029',
  issued: '05-25-2026',
  year: '2017',
  brand: 'MITSUBISHI',
  model: 'LANCER',
  color: 'NEGRO',
  chassis: 'CHS7X9A42QK881',
  engine: 'MTRZP49931FAKE',
  vin: '1FAKE9X7K0M123456'
};
const bothSides = {
  front: { document_id: 'f', status: 'active', extracted: true },
  back: { document_id: 'b', status: 'active', extracted: true }
};

function capture(overrides: Partial<CaptureState> = {}): CaptureState {
  return {
    id: 'capture-1',
    status: 'ready',
    failure_code: null,
    extraction_available: true,
    ...bothSides,
    values: VALUES,
    issues: [],
    fills: [],
    ...overrides
  };
}

async function reachReview(issues: CaptureIssue[] = [], fills: string[] = []) {
  captureApi.open.mockResolvedValue(capture({ issues, fills }));
  captureApi.check.mockResolvedValue({ issues, fills });
  const onconfirmed = vi.fn();
  render(CirculationCaptureEntry, { vehicle, onconfirmed });
  await fireEvent.click(await screen.findByRole('button', { name: /Capturar con fotos/ }));
  await screen.findByRole('button', { name: 'Confirmar tarjeta' });
  return onconfirmed;
}

describe('CirculationCaptureEntry', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    permissionMock.codes = new Set(['fleet_documents:upload']);
    capabilities.mockResolvedValue({ enabled: true, extraction_available: true });
    captureApi.preview.mockResolvedValue({ url: 'http://storage/foto', expires_at: '' });
  });

  afterEach(() => cleanup());

  it('is not offered to a vehicle without a plate', async () => {
    render(CirculationCaptureEntry, {
      vehicle: { ...vehicle, plate: null },
      onconfirmed: vi.fn()
    });

    await waitFor(() => expect(capabilities).toHaveBeenCalled());
    expect(screen.queryByRole('button', { name: /Capturar con fotos/ })).toBeNull();
  });

  it('is not offered without permission to upload', async () => {
    permissionMock.codes = new Set();

    render(CirculationCaptureEntry, { vehicle, onconfirmed: vi.fn() });

    expect(capabilities).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: /Capturar con fotos/ })).toBeNull();
  });

  it('prefills what the model read and asks for no owner data', async () => {
    await reachReview();

    expect(screen.getByLabelText(/Placa/)).toHaveValue('PFAK3420-2007');
    expect(screen.getByLabelText(/VIN/)).toHaveValue('1FAKE9X7K0M123456');
    expect(screen.queryByLabelText(/Nombre|DUI|Titular/i)).toBeNull();
  });

  it('never lets another plate through, whatever the permissions', async () => {
    permissionMock.codes = new Set(['fleet_documents:upload', 'drivers:license_override']);
    const issue: CaptureIssue = {
      code: 'plate_mismatch',
      severity: 'error',
      field: 'plate',
      message: 'La placa de la tarjeta no coincide con PFAK3420: es de otro vehículo.'
    };

    await reachReview([issue]);

    await screen.findByText(issue.message);
    expect(screen.queryByLabelText(/Motivo de la excepción/)).toBeNull();
    expect(screen.getByRole('button', { name: 'Confirmar tarjeta' })).toBeDisabled();
    expect(screen.getByText(/Esta tarjeta es de otro vehículo/)).toBeInTheDocument();
  });

  it('does not mark empty fields as mistakes while the model is reading', async () => {
    const issue: CaptureIssue = {
      code: 'plate_missing',
      severity: 'error',
      field: 'plate',
      message: 'Indica la placa.'
    };
    const empty = Object.fromEntries(Object.keys(VALUES).map((key) => [key, null]));
    captureApi.open.mockResolvedValue(capture({ status: 'pending', values: empty }));
    captureApi.get.mockResolvedValue(capture({ status: 'pending', values: empty }));
    captureApi.check.mockResolvedValue({ issues: [issue], fills: [] });
    render(CirculationCaptureEntry, { vehicle, onconfirmed: vi.fn() });
    await fireEvent.click(await screen.findByRole('button', { name: /Capturar con fotos/ }));
    const confirm = await screen.findByRole('button', { name: 'Confirmar tarjeta' });
    await waitFor(() => expect(captureApi.check).toHaveBeenCalled());

    expect(await screen.findByText('Leyendo la tarjeta…')).toBeInTheDocument();
    expect(screen.queryByText(issue.message)).toBeNull();
    expect(confirm).toBeDisabled();
  });

  it('asks to acknowledge a difference with the vehicle', async () => {
    const issue: CaptureIssue = {
      code: 'color_mismatch',
      severity: 'warning',
      field: 'color',
      message: 'Color: la tarjeta dice NEGRO; el vehículo tiene Blanco.'
    };
    await reachReview([issue]);
    const confirm = screen.getByRole('button', { name: 'Confirmar tarjeta' });
    await screen.findByText(issue.message);
    expect(confirm).toBeDisabled();

    await fireEvent.click(screen.getByRole('checkbox'));

    expect(confirm).toBeEnabled();
  });

  it('says which empty vehicle data the card will complete', async () => {
    await reachReview([], ['chassis_number']);

    const field = await screen.findByLabelText(/Número de chasis/);
    await waitFor(() => expect(field.getAttribute('aria-describedby')).toMatch(/fill/));
    expect(screen.getByText('Se completará en el vehículo.')).toBeInTheDocument();
  });

  it.each([
    ['frente', true],
    ['reverso', false]
  ])('on the %s, the glare check stopping the photo is %s', async (side, stops) => {
    // El reverso deja mucho en blanco: a ese detector le parece un reflejo.
    URL.createObjectURL = vi.fn(() => 'blob:foto');
    URL.revokeObjectURL = vi.fn();
    prepareMock.mockResolvedValue({
      file: new File(['x'], 'tarjeta.jpg', { type: 'image/jpeg' }),
      issues: ['glare']
    });
    captureApi.startUpload.mockResolvedValue({ upload_url: 'u' });
    captureApi.completeUpload.mockResolvedValue(capture({ status: 'draft' }));
    const frontOnly = {
      front: { document_id: 'f', status: 'active', extracted: false },
      back: { document_id: null, status: null, extracted: false }
    };
    const noPhotos = {
      front: { document_id: null, status: null, extracted: false },
      back: { document_id: null, status: null, extracted: false }
    };
    captureApi.open.mockResolvedValue(
      capture({ status: 'draft', ...(side === 'reverso' ? frontOnly : noPhotos) })
    );
    render(CirculationCaptureEntry, { vehicle, onconfirmed: vi.fn() });
    await fireEvent.click(await screen.findByRole('button', { name: /Capturar con fotos/ }));
    await screen.findByText(new RegExp(`Carga el ${side}`));
    const input = screen.getByText('Subir archivo').querySelector('input') as HTMLInputElement;
    Object.defineProperty(input, 'files', {
      value: [new File(['x'], 'foto.jpg', { type: 'image/jpeg' })],
      configurable: true
    });

    await fireEvent.change(input);

    if (stops) {
      expect(await screen.findByText(/Hay un reflejo/)).toBeInTheDocument();
      expect(captureApi.startUpload).not.toHaveBeenCalled();
    } else {
      await waitFor(() => expect(captureApi.startUpload).toHaveBeenCalled());
      expect(screen.queryByText(/Hay un reflejo/)).toBeNull();
    }
  });

  it('reports the outcome and hands the vehicle back after confirming', async () => {
    const saved = { ...vehicle, chassis_number: 'CHS7X9A42QK881' } as FleetVehicle;
    captureApi.confirm.mockResolvedValue({
      vehicle: saved,
      filled_fields: ['chassis_number'],
      skipped_fields: []
    });
    const onconfirmed = await reachReview();

    await fireEvent.click(screen.getByRole('button', { name: 'Confirmar tarjeta' }));

    await waitFor(() => expect(onconfirmed).toHaveBeenCalledWith(saved));
    expect(captureApi.confirm).toHaveBeenCalledWith('capture-1', {
      values: expect.objectContaining({ plate: 'PFAK3420-2007' }),
      acknowledged_warnings: []
    });
    expect(await screen.findByRole('status')).toHaveTextContent(
      /Se completó en el vehículo: chasis/
    );
  });
});

describe('circulation config', () => {
  it('maps vehicle columns to the fields printed on the card', () => {
    expect(filledFields(['vin', 'chassis_number', 'engine_number'])).toEqual([
      'vin',
      'chassis',
      'engine'
    ]);
  });

  it('explains data left out for lack of permission', () => {
    expect(confirmationNotice({ filled_fields: [], skipped_fields: ['vin', 'color'] })).toMatch(
      /No se completó VIN, color: el vehículo está dado de baja o no tienes permiso/
    );
  });
});
