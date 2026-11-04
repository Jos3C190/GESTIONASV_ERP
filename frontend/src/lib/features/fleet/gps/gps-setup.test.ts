import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { FleetVehicle, GpsSetup, GpsStatus } from '../api';
import VehicleGpsPanel from '../VehicleGpsPanel.svelte';
import GpsSetupDialog from './GpsSetupDialog.svelte';
import {
  cardView,
  cleanIdentifier,
  detectPlatform,
  nextStep,
  previousStep,
  readingRows,
  resumeStep,
  stepNumber,
  timeAgo,
  troubleshooting,
  validIdentifier
} from './setup-flow';

const apiMock = vi.hoisted(() => ({
  gpsSetup: vi.fn(),
  gpsStatus: vi.fn(),
  linkPhone: vi.fn(),
  linkGps: vi.fn(),
  unlinkGps: vi.fn()
}));
const permissionMock = vi.hoisted(() => ({ codes: new Set<string>() }));

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api')>()),
  fleetApi: apiMock
}));
vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: { hasPermission: (code: string) => permissionMock.codes.has(code) }
}));
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('qrcode', () => ({
  default: { toDataURL: vi.fn().mockResolvedValue('data:image/png,qr') }
}));

const NOW = new Date('2026-11-02T15:00:00Z').getTime();

const vehicle = {
  id: 'v1',
  code: 'VEH-1',
  status: 'active',
  gps_linked: false,
  gps_device_unique_id: null
} as unknown as FleetVehicle;

const setup: GpsSetup = {
  configured: true,
  server_url: 'http://192.168.1.50:5055',
  host: '192.168.1.50',
  private_network: false,
  phone_config_uri: null,
  trackers: [
    { key: 'gt06', brand: 'Concox / Jimi', models: 'GT06', port: 5023, short_identifier: false },
    { key: 'tk103', brand: 'Coban', models: 'TK103A', port: 5002, short_identifier: true }
  ]
};

function status(overrides: Partial<GpsStatus> = {}): GpsStatus {
  return {
    state: 'unlinked',
    kind: null,
    server_configured: true,
    last_update: null,
    battery_level: null,
    ...overrides
  };
}

describe('setup flow', () => {
  it('walks each path forward and back, with the signal check last', () => {
    expect(nextStep('phone', 'kind')).toBe('install');
    expect(nextStep('phone', 'permissions')).toBe('signal');
    expect(nextStep('tracker', 'kind')).toBe('model');
    expect(nextStep('tracker', 'configure')).toBe('signal');
    expect(previousStep('tracker', 'model')).toBe('kind');
    expect(stepNumber(null, 'kind')).toBe(1);
    expect(stepNumber('phone', 'signal')).toBe(5);
    expect(stepNumber('tracker', 'signal')).toBe(5);
  });

  it('resumes without repeating what cannot be lost', () => {
    expect(resumeStep('phone')).toBe('scan');
    expect(resumeStep('tracker')).toBe('model');
  });

  it('validates identifiers like the server', () => {
    expect(validIdentifier(' 358240051111110 ')).toBe(true);
    expect(validIdentifier('ab')).toBe(false);
    expect(validIdentifier('con#simbolo')).toBe(false);
  });

  it('detects the store to suggest', () => {
    expect(detectPlatform('Mozilla/5.0 (Linux; Android 14)')).toBe('android');
    expect(detectPlatform('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)')).toBe('ios');
    expect(detectPlatform('Mozilla/5.0 (Windows NT 10.0)')).toBe('other');
  });

  it('says how long ago in plain words', () => {
    const ago = (minutes: number) => new Date(NOW - minutes * 60_000).toISOString();

    expect(timeAgo(ago(0), NOW)).toBe('hace un momento');
    expect(timeAgo(ago(2), NOW)).toBe('hace 2 min');
    expect(timeAgo(ago(180), NOW)).toBe('hace 3 h');
    expect(timeAgo(ago(1440), NOW)).toBe('hace 1 día');
  });

  it('warns about the network only when the address is private', () => {
    expect(troubleshooting('phone', false).join()).not.toMatch(/red de la empresa/);
    expect(troubleshooting('tracker', true).join()).toMatch(/red de la empresa/);
  });

  it('does not offer what the user cannot do', () => {
    expect(cardView(status(), NOW, false).action).toBeNull();
    expect(cardView(status(), NOW, false).detail).toMatch(/quien administra la flota/);
    expect(cardView(status(), NOW, false, true).detail).toMatch(/dado de baja/);
  });

  it('turns readings into plain rows, keeping a zero and a false', () => {
    expect(readingRows(undefined)).toEqual([]);
    expect(readingRows({})).toEqual([]);
    expect(
      readingRows({ ignition: false, satellites: 0, voltage: 12.64, engine_hours: 2 })
    ).toEqual([
      { label: 'Motor', value: 'Apagado' },
      { label: 'Voltaje del vehículo', value: '12.6 V' },
      { label: 'Horas de motor', value: '2 h' },
      { label: 'Satélites', value: '0' }
    ]);
  });

  it('accepts an IMEI pasted with spaces', () => {
    expect(validIdentifier('358 240 051 111 110')).toBe(true);
    expect(cleanIdentifier('358 240 051 111 110')).toBe('358240051111110');
  });

  it.each([
    [status(), 'connect', 'Este vehículo no tiene GPS'],
    [status({ server_configured: false }), null, 'Falta configurar el servidor GPS'],
    [status({ state: 'waiting', kind: 'phone' }), 'resume', 'Esperando la primera señal'],
    [
      status({ state: 'reporting', last_update: new Date(NOW).toISOString() }),
      'track',
      'GPS activo'
    ],
    [
      status({ state: 'silent', last_update: new Date(NOW).toISOString() }),
      'help',
      'Sin señal reciente'
    ],
    [status({ state: 'unavailable' }), 'retry', 'No pudimos comprobar la señal'],
    [null, 'retry', 'No pudimos consultar el estado']
  ])('gives each state one action', (value, action, title) => {
    const view = cardView(value, NOW);

    expect(view.action).toBe(action);
    expect(view.title).toBe(title);
  });

  it('never names the underlying server in what the user reads', () => {
    const states = [status(), status({ state: 'waiting' }), status({ state: 'unavailable' })];
    const words = states.map((value) => JSON.stringify(cardView(value, NOW))).join();

    expect(words).not.toMatch(/traccar|osmand|protocolo/i);
  });
});

describe('GpsSetupDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    permissionMock.codes = new Set(['fleet:gps', 'tracking:read']);
    apiMock.gpsSetup.mockResolvedValue(setup);
    apiMock.gpsStatus.mockResolvedValue(status({ state: 'waiting', kind: 'phone' }));
    window.matchMedia = vi.fn().mockReturnValue({ matches: false }) as never;
  });

  afterEach(() => cleanup());

  function open(props: Record<string, unknown> = {}) {
    const onchanged = vi.fn();
    render(GpsSetupDialog, { open: true, vehicle, onchanged, ...props });
    return onchanged;
  }

  it('only links a phone once the app is installed, then shows its QR', async () => {
    const linked = { ...vehicle, gps_linked: true, gps_device_unique_id: 'GS-ABC' };
    apiMock.linkPhone.mockResolvedValue(linked);
    apiMock.gpsSetup.mockResolvedValue({ ...setup, phone_config_uri: 'http://x?id=GS-ABC' });
    const onchanged = open();

    await fireEvent.click(await screen.findByLabelText(/Teléfono del conductor/));
    await fireEvent.click(screen.getByRole('button', { name: 'Continuar' }));
    expect(await screen.findByText('Paso 2 de 5')).toBeInTheDocument();
    expect(apiMock.linkPhone).not.toHaveBeenCalled();

    await fireEvent.click(screen.getByRole('button', { name: 'Ya la instalé' }));

    expect(await screen.findByAltText(/Código QR/)).toBeInTheDocument();
    expect(apiMock.linkPhone).toHaveBeenCalledWith('v1', false);
    expect(onchanged).toHaveBeenCalledWith(linked);
  });

  it('gives a replacing phone its own identifier, only on the first link', async () => {
    apiMock.linkPhone.mockResolvedValue({ ...vehicle, gps_linked: true });
    open({ vehicle: { ...vehicle, gps_linked: true, gps_device_unique_id: 'GS-OLD' } });

    await fireEvent.click(await screen.findByLabelText(/Teléfono del conductor/));
    await fireEvent.click(screen.getByRole('button', { name: 'Continuar' }));
    expect(await screen.findByText(/dejará de aparecer en Seguimiento/)).toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: 'Ya la instalé' }));
    await screen.findByText('Paso 3 de 5');
    expect(apiMock.linkPhone).toHaveBeenLastCalledWith('v1', true);

    await fireEvent.click(screen.getByRole('button', { name: 'Atrás' }));
    await fireEvent.click(await screen.findByRole('button', { name: 'Ya la instalé' }));
    await screen.findByText('Paso 3 de 5');

    expect(apiMock.linkPhone).toHaveBeenLastCalledWith('v1', false);
  });

  it('does not accept the current GPS as its own replacement', async () => {
    open({ vehicle: { ...vehicle, gps_linked: true, gps_device_unique_id: '358240051111110' } });
    await fireEvent.click(await screen.findByLabelText(/GPS instalado/));
    await fireEvent.click(screen.getByRole('button', { name: 'Continuar' }));
    await fireEvent.click(await screen.findByLabelText(/Concox/));
    await fireEvent.click(screen.getByRole('button', { name: 'Continuar' }));
    const field = await screen.findByLabelText('Identificador del GPS');
    expect(field).toHaveValue('');

    await fireEvent.input(field, { target: { value: '358240051111110' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Continuar' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/Ese es el GPS actual/);
    expect(apiMock.linkGps).not.toHaveBeenCalled();
  });

  it('explains an invalid identifier instead of silently blocking', async () => {
    open({ startKind: 'tracker', startStep: 'identifier' });
    const field = await screen.findByLabelText('Identificador del GPS');

    await fireEvent.input(field, { target: { value: 'a#' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Continuar' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/solo letras y números/);
    expect(apiMock.linkGps).not.toHaveBeenCalled();

    await fireEvent.input(field, { target: { value: 'a#b' } });

    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('warns too when resuming and switching to another kind of device', async () => {
    open({
      vehicle: { ...vehicle, gps_linked: true, gps_device_unique_id: 'GS-OLD' },
      startKind: 'phone',
      startStep: 'scan'
    });
    await screen.findByText('Paso 3 de 5');
    await fireEvent.click(screen.getByRole('button', { name: 'Atrás' }));
    await fireEvent.click(await screen.findByRole('button', { name: 'Atrás' }));
    expect(await screen.findByText('Paso 1 de 5')).toBeInTheDocument();
    expect(screen.queryByText(/dejará de aparecer en Seguimiento/)).toBeNull();

    await fireEvent.click(screen.getByLabelText(/GPS instalado/));

    expect(await screen.findByText(/dejará de aparecer en Seguimiento/)).toBeInTheDocument();
  });

  it('offers only to close when it cannot continue', async () => {
    apiMock.gpsSetup.mockResolvedValue({ ...setup, configured: false });
    open({ startKind: 'phone', startStep: 'scan' });

    expect(await screen.findByText('No se puede continuar')).toBeInTheDocument();
    expect(screen.queryByText('Paso 3 de 5')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Atrás' })).toBeNull();
  });

  it('sends a pasted IMEI clean, also with the Enter key', async () => {
    apiMock.linkGps.mockResolvedValue({ ...vehicle, gps_linked: true });
    open({ startKind: 'tracker', startStep: 'identifier' });
    const field = await screen.findByLabelText('Identificador del GPS');

    await fireEvent.input(field, { target: { value: '358 240 051 111 110' } });
    await fireEvent.submit(field.closest('form') as HTMLFormElement);

    await waitFor(() => expect(apiMock.linkGps).toHaveBeenCalledWith('v1', '358240051111110'));
  });

  it('keeps the permissions as a guide that does not block', async () => {
    open({ startKind: 'phone', startStep: 'permissions' });

    expect(await screen.findByRole('button', { name: 'Comprobar señal' })).toBeEnabled();
    expect(screen.getAllByRole('checkbox')).toHaveLength(3);
  });

  it('lets the help route go back to review the setup', async () => {
    apiMock.gpsStatus.mockResolvedValue(
      status({
        state: 'silent',
        kind: 'tracker',
        last_update: new Date(Date.now() - 3 * 3_600_000).toISOString()
      })
    );
    open({ startKind: 'tracker', startStep: 'signal' });

    expect(await screen.findByText('Sin señal hace 3 h')).toBeInTheDocument();
    expect(screen.getByText('Revisa esto')).toBeInTheDocument();

    await fireEvent.click(screen.getByRole('button', { name: 'Revisar datos' }));

    expect(await screen.findByText('¿Qué GPS tienes?')).toBeInTheDocument();
  });

  it('says so when the signal cannot be checked', async () => {
    vi.useFakeTimers();
    try {
      apiMock.gpsStatus.mockRejectedValue(new Error('down'));
      open({ startKind: 'phone', startStep: 'signal' });
      await vi.advanceTimersByTimeAsync(0);
      await vi.advanceTimersByTimeAsync(5_000);
      await vi.advanceTimersByTimeAsync(0);

      expect(screen.getByText('No podemos comprobar la señal')).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it('keeps what was typed and shows a server error beside the field', async () => {
    apiMock.linkGps.mockRejectedValue(new Error('x'));
    open({ startKind: 'tracker', startStep: 'identifier' });
    const field = await screen.findByLabelText('Identificador del GPS');
    const go = screen.getByRole('button', { name: 'Continuar' });

    await fireEvent.input(field, { target: { value: '358240051111110' } });
    await fireEvent.click(go);

    expect(await screen.findByRole('alert')).toHaveTextContent(/No se pudo conectar/);
    expect(field).toHaveValue('358240051111110');
    expect(screen.getByText('Paso 3 de 5')).toBeInTheDocument();
  });

  it('shows the host and the port of the chosen model', async () => {
    apiMock.linkGps.mockResolvedValue({ ...vehicle, gps_linked: true });
    open({ startKind: 'tracker', startStep: 'model' });

    await fireEvent.click(await screen.findByLabelText(/Concox/));
    await fireEvent.click(screen.getByRole('button', { name: 'Continuar' }));
    const field = await screen.findByLabelText('Identificador del GPS');
    await fireEvent.input(field, { target: { value: '358240051111110' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Continuar' }));

    expect(await screen.findByText('5023')).toBeInTheDocument();
    expect(screen.getByText('192.168.1.50')).toBeInTheDocument();
  });

  it('warns about short identifiers only on the models that use them', async () => {
    open({ startKind: 'tracker', startStep: 'model' });

    await fireEvent.click(await screen.findByLabelText(/Coban/));
    await fireEvent.click(screen.getByRole('button', { name: 'Continuar' }));

    expect(await screen.findByText(/últimos 11 del IMEI/)).toBeInTheDocument();
  });

  it('does not lead an unsupported model into a dead end', async () => {
    open({ startKind: 'tracker', startStep: 'model' });

    await fireEvent.click(await screen.findByLabelText(/Otro modelo/));

    expect(await screen.findByText(/confirmar si tu GPS es compatible/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Continuar' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Entendido' })).toBeInTheDocument();
  });

  it('warns before starting when the address only works on the same network', async () => {
    apiMock.gpsSetup.mockResolvedValue({ ...setup, private_network: true });
    open();

    expect(await screen.findByText(/dentro de la red de la empresa/)).toBeInTheDocument();
  });

  it('warns that a new device replaces the linked one', async () => {
    open({ vehicle: { ...vehicle, gps_linked: true, gps_device_unique_id: '123' } });

    expect(await screen.findByText(/dejará de aparecer en Seguimiento/)).toBeInTheDocument();
  });

  it('explains what is missing when the server is not configured', async () => {
    apiMock.gpsSetup.mockResolvedValue({ ...setup, configured: false });
    open();

    expect(await screen.findByText(/Falta configurar la dirección/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Continuar' })).toBeNull();
  });

  it('celebrates the first signal and offers the map', async () => {
    apiMock.gpsStatus.mockResolvedValue(
      status({ state: 'reporting', kind: 'phone', last_update: new Date().toISOString() })
    );
    open({ startKind: 'phone', startStep: 'signal' });

    expect(await screen.findByText(/Ya recibimos su ubicación/)).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Ver en Seguimiento' })).toBeInTheDocument();
  });

  it('stops checking the signal when it closes', async () => {
    vi.useFakeTimers();
    try {
      open({ startKind: 'phone', startStep: 'signal' });
      await vi.advanceTimersByTimeAsync(0);
      await vi.advanceTimersByTimeAsync(0);
      expect(apiMock.gpsStatus).toHaveBeenCalled();
      cleanup();
      apiMock.gpsStatus.mockClear();

      await vi.advanceTimersByTimeAsync(20_000);

      expect(apiMock.gpsStatus).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it('offers help after two minutes without signal', async () => {
    vi.useFakeTimers();
    try {
      open({ startKind: 'phone', startStep: 'permissions' });
      await vi.advanceTimersByTimeAsync(0);
      await vi.advanceTimersByTimeAsync(0);
      for (const box of screen.getAllByRole('checkbox')) await fireEvent.click(box);
      await fireEvent.click(screen.getByRole('button', { name: 'Comprobar señal' }));
      await vi.advanceTimersByTimeAsync(0);
      expect(screen.getByText('Comprobando la señal')).toBeInTheDocument();
      expect(screen.queryByText('Revisa esto')).toBeNull();

      await vi.advanceTimersByTimeAsync(120_000);

      expect(screen.getByText('Revisa esto')).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe('VehicleGpsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    permissionMock.codes = new Set(['fleet:gps', 'tracking:read']);
    apiMock.gpsSetup.mockResolvedValue(setup);
    window.matchMedia = vi.fn().mockReturnValue({ matches: false }) as never;
  });

  afterEach(() => cleanup());

  it('opens the guide from a vehicle without GPS', async () => {
    apiMock.gpsStatus.mockResolvedValue(status());
    render(VehicleGpsPanel, { vehicle, onchanged: vi.fn() });

    await fireEvent.click(await screen.findByRole('button', { name: 'Conectar GPS' }));

    expect(await screen.findByText('¿Qué vas a conectar?')).toBeInTheDocument();
  });

  it('shows the state but no actions to who cannot manage the device', async () => {
    permissionMock.codes = new Set();
    apiMock.gpsStatus.mockResolvedValue(status({ state: 'waiting', kind: 'tracker' }));
    render(VehicleGpsPanel, {
      vehicle: { ...vehicle, gps_linked: true, gps_device_unique_id: '123456' },
      onchanged: vi.fn()
    });

    expect(await screen.findByText('Esperando la primera señal')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Continuar configuración' })).toBeNull();
    expect(screen.queryByText('123456')).toBeNull();
  });

  it('shows the last signal and battery while reporting', async () => {
    apiMock.gpsStatus.mockResolvedValue(
      status({
        state: 'reporting',
        kind: 'phone',
        last_update: new Date().toISOString(),
        battery_level: 76.4
      })
    );
    render(VehicleGpsPanel, {
      vehicle: { ...vehicle, gps_linked: true, gps_device_unique_id: 'GS-ABC' },
      onchanged: vi.fn()
    });

    expect(await screen.findByText(/Última señal hace un momento/)).toBeInTheDocument();
    expect(screen.getByText(/Batería 76 %/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ver en Seguimiento' })).toHaveAttribute(
      'href',
      '/tracking'
    );
  });

  it('adds no empty section when the device sends nothing extra', async () => {
    apiMock.gpsStatus.mockResolvedValue(
      status({ state: 'reporting', kind: 'phone', last_update: new Date().toISOString() })
    );
    render(VehicleGpsPanel, { vehicle, onchanged: vi.fn() });

    await screen.findByText('GPS activo');

    expect(screen.queryByText('Datos del equipo')).toBeNull();
  });

  it('shows only what the device sent', async () => {
    apiMock.gpsStatus.mockResolvedValue(
      status({
        state: 'reporting',
        kind: 'tracker',
        last_update: new Date().toISOString(),
        readings: { ignition: true, temperature: 4.5 }
      })
    );
    render(VehicleGpsPanel, { vehicle, onchanged: vi.fn() });

    expect(await screen.findByText('Datos del equipo')).toBeInTheDocument();
    expect(screen.getByText('Encendido')).toBeInTheDocument();
    expect(screen.getByText('4.5 °C')).toBeInTheDocument();
    expect(screen.queryByText('Voltaje del vehículo')).toBeNull();
  });

  it('says the data is old when the signal was lost', async () => {
    apiMock.gpsStatus.mockResolvedValue(
      status({
        state: 'silent',
        kind: 'tracker',
        last_update: new Date(Date.now() - 3_600_000).toISOString(),
        readings: { ignition: false }
      })
    );
    render(VehicleGpsPanel, { vehicle, onchanged: vi.fn() });

    expect(await screen.findByText('Datos de la última señal')).toBeInTheDocument();
    expect(screen.getByText('Apagado')).toBeInTheDocument();
  });

  it('asks before unlinking', async () => {
    apiMock.gpsStatus.mockResolvedValue(status({ state: 'silent', kind: 'tracker' }));
    apiMock.unlinkGps.mockResolvedValue({ ...vehicle });
    render(VehicleGpsPanel, {
      vehicle: { ...vehicle, gps_linked: true, gps_device_unique_id: '123456' },
      onchanged: vi.fn()
    });

    await fireEvent.click(await screen.findByRole('button', { name: 'Desvincular GPS' }));
    expect(apiMock.unlinkGps).not.toHaveBeenCalled();
    await fireEvent.click(screen.getByRole('button', { name: 'Desvincular' }));

    await waitFor(() => expect(apiMock.unlinkGps).toHaveBeenCalledWith('v1'));
  });

  it('offers a retry when the signal cannot be checked', async () => {
    apiMock.gpsStatus.mockRejectedValueOnce(new Error('down'));
    apiMock.gpsStatus.mockResolvedValue(status());
    render(VehicleGpsPanel, { vehicle, onchanged: vi.fn() });

    await fireEvent.click(await screen.findByRole('button', { name: 'Reintentar' }));

    expect(await screen.findByRole('button', { name: 'Conectar GPS' })).toBeInTheDocument();
  });
});
