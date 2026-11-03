import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { FleetVehicle } from './api';
import VehicleIncidentsPanel from './VehicleIncidentsPanel.svelte';
import VehicleInspectionsPanel from './VehicleInspectionsPanel.svelte';

const apiMock = vi.hoisted(() => ({
  incidents: vi.fn(),
  addIncident: vi.fn(),
  updateIncident: vi.fn(),
  inspections: vi.fn(),
  inspectionItems: vi.fn(),
  addInspection: vi.fn(),
  resolveInspectionResult: vi.fn(),
  documents: vi.fn()
}));
const permissionMock = vi.hoisted(() => ({ codes: new Set<string>() }));
const confirmMock = vi.hoisted(() => ({ request: vi.fn() }));

vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  fleetApi: apiMock
}));
vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: { hasPermission: (code: string) => permissionMock.codes.has(code) }
}));
vi.mock('$lib/stores/confirmation.svelte', () => ({ confirmation: confirmMock }));
vi.mock('$lib/stores/company.svelte', () => ({ company: { id: 'c1' } }));

const vehicle = {
  id: 'v1',
  status: 'active',
  branch_id: 'b1',
  driver: null,
  type: { meter_unit: 'km' }
} as unknown as FleetVehicle;

const incident = (overrides = {}) => ({
  id: 'i1',
  vehicle_id: 'v1',
  vehicle_code: 'V-1',
  driver_id: null,
  driver_name: null,
  kind: 'accident',
  severity: 'moderate',
  responsible: 'unknown',
  status: 'open',
  occurred_at: '2026-11-01T10:00:00Z',
  location: null,
  description: 'Golpe en la puerta',
  cost: null,
  insurance_claim: null,
  document_id: null,
  resolution: null,
  reported_by_name: 'ana',
  closed_at: null,
  closed_by_name: null,
  ...overrides
});

const item = (id: string, name: string, is_critical = false) => ({
  id,
  name,
  is_critical,
  is_active: true
});

async function choose(label: RegExp | string, value: string) {
  const select = screen.getByLabelText(label) as HTMLSelectElement;
  // Svelte lee la opción con :checked, que el DOM de pruebas no marca para <option>.
  const real = select.querySelector.bind(select);
  select.querySelector = ((query: string) =>
    query === ':checked'
      ? real(`option[value="${value}"]`)
      : real(query)) as typeof select.querySelector;
  await fireEvent.change(select, { target: { value } });
  select.querySelector = real;
}

describe('vehicle incidents', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    permissionMock.codes = new Set(['fleet:incidents']);
    apiMock.incidents.mockResolvedValue([incident()]);
    apiMock.addIncident.mockResolvedValue(incident({ vehicle_taken_out: true }));
    apiMock.updateIncident.mockResolvedValue(incident());
  });
  afterEach(cleanup);

  it('offers a retry instead of an empty list when loading fails', async () => {
    apiMock.incidents.mockRejectedValue(new Error('caído'));
    render(VehicleIncidentsPanel, { vehicle, onchanged: vi.fn() });
    expect(await screen.findByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
    expect(screen.queryByText(/no tiene incidentes/)).not.toBeInTheDocument();
  });

  it('asks what is missing and does not preselect a kind or severity', async () => {
    render(VehicleIncidentsPanel, { vehicle, onchanged: vi.fn() });
    await fireEvent.click(await screen.findByRole('button', { name: 'Registrar incidente' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Registrar' }));
    expect(await screen.findByText('Elige el tipo.')).toBeInTheDocument();
    expect(screen.getByText('Elige la gravedad.')).toBeInTheDocument();
    expect(screen.getByText('Describe qué pasó.')).toBeInTheDocument();
    expect(apiMock.addIncident).not.toHaveBeenCalled();
  });

  it('offers to take the vehicle out of service only for something serious', async () => {
    const onchanged = vi.fn();
    render(VehicleIncidentsPanel, { vehicle, onchanged });
    await fireEvent.click(await screen.findByRole('button', { name: 'Registrar incidente' }));
    await choose(/^Tipo/, 'damage');
    await choose(/^Gravedad/, 'minor');
    expect(screen.queryByLabelText(/fuera de servicio/)).not.toBeInTheDocument();

    await choose(/^Tipo/, 'theft');
    expect(screen.getByLabelText(/fuera de servicio/)).toBeChecked();
    await fireEvent.input(screen.getByLabelText(/¿Qué pasó?/), {
      target: { value: 'Robo en el patio' }
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Registrar' }));
    expect(await screen.findByText(/quedó fuera de servicio/)).toBeInTheDocument();
    expect(apiMock.addIncident).toHaveBeenCalledWith(
      'v1',
      expect.objectContaining({ kind: 'theft', take_out_of_service: true })
    );
    expect(onchanged).toHaveBeenCalled();
  });

  it('explains that a vehicle on the road cannot be stopped, and still records', async () => {
    render(VehicleIncidentsPanel, {
      vehicle: { ...vehicle, operational_status: 'in_route' },
      onchanged: vi.fn()
    });
    await fireEvent.click(await screen.findByRole('button', { name: 'Registrar incidente' }));
    await choose(/^Tipo/, 'theft');
    expect(screen.queryByLabelText(/fuera de servicio/)).not.toBeInTheDocument();
    expect(screen.getByText(/Está en un traslado/)).toBeInTheDocument();
  });

  it('asks before discarding what was written', async () => {
    render(VehicleIncidentsPanel, { vehicle, onchanged: vi.fn() });
    await fireEvent.click(await screen.findByRole('button', { name: 'Registrar incidente' }));
    await fireEvent.input(screen.getByLabelText(/¿Qué pasó?/), { target: { value: 'Algo' } });
    await fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));
    expect(confirmMock.request).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Descartar incidente' })
    );
  });

  it('does not offer it for a vehicle that is not active', async () => {
    render(VehicleIncidentsPanel, {
      vehicle: { ...vehicle, status: 'out_of_service' },
      onchanged: vi.fn()
    });
    await fireEvent.click(await screen.findByRole('button', { name: 'Registrar incidente' }));
    await choose(/^Gravedad/, 'severe');
    expect(screen.queryByLabelText(/fuera de servicio/)).not.toBeInTheDocument();
  });

  it('asks how it was resolved before closing', async () => {
    render(VehicleIncidentsPanel, { vehicle, onchanged: vi.fn() });
    await fireEvent.click(await screen.findByRole('button', { name: /^Dar seguimiento/ }));
    await choose('Estado', 'closed');
    await fireEvent.click(screen.getByRole('button', { name: 'Guardar' }));
    expect(await screen.findByText('Indica cómo se resolvió.')).toBeInTheDocument();
    expect(apiMock.updateIncident).not.toHaveBeenCalled();
    await fireEvent.input(screen.getByLabelText(/¿Cómo se resolvió?/), {
      target: { value: 'Pagó el seguro' }
    });
    await fireEvent.click(screen.getByRole('button', { name: 'Guardar' }));
    await vi.waitFor(() =>
      expect(apiMock.updateIncident).toHaveBeenCalledWith(
        'v1',
        'i1',
        expect.objectContaining({ status: 'closed', resolution: 'Pagó el seguro' })
      )
    );
  });

  it('hides recording without permission', async () => {
    permissionMock.codes = new Set();
    render(VehicleIncidentsPanel, { vehicle, onchanged: vi.fn() });
    await screen.findByText('Golpe en la puerta');
    expect(screen.queryByRole('button', { name: 'Registrar incidente' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Dar seguimiento/ })).not.toBeInTheDocument();
  });
});

describe('vehicle inspections', () => {
  const failed = {
    id: 'r1',
    item_name: 'Frenos',
    is_critical: true,
    passed: false,
    notes: 'No frena',
    photo_url: null,
    resolved_at: null,
    resolved_by_name: null,
    resolution: null
  };

  beforeEach(() => {
    vi.clearAllMocks();
    permissionMock.codes = new Set(['fleet:inspections']);
    apiMock.inspections.mockResolvedValue([]);
    apiMock.inspectionItems.mockResolvedValue([item('a', 'Frenos', true), item('b', 'Espejos')]);
    apiMock.addInspection.mockResolvedValue({ passed: true });
  });
  afterEach(cleanup);

  async function start() {
    render(VehicleInspectionsPanel, { vehicle, onchanged: vi.fn() });
    await fireEvent.click(await screen.findByRole('button', { name: 'Nueva inspección' }));
    await screen.findByText('0 de 2');
  }

  it('does not let a point go unanswered', async () => {
    await start();
    await fireEvent.click(screen.getByRole('button', { name: 'Guardar inspección' }));
    expect((await screen.findAllByText('Marca si está bien o tiene falla.')).length).toBe(2);
    expect(apiMock.addInspection).not.toHaveBeenCalled();
  });

  it('warns and asks for a description when a critical point fails', async () => {
    await start();
    await fireEvent.click(screen.getAllByRole('button', { name: 'Falla' })[0] as HTMLElement);
    expect(screen.getByText(/Con Frenos en falla/)).toBeInTheDocument();
    await fireEvent.click(screen.getAllByRole('button', { name: 'Bien' })[1] as HTMLElement);
    await fireEvent.click(screen.getByRole('button', { name: 'Guardar inspección' }));
    expect(await screen.findByText('Describe la falla.')).toBeInTheDocument();
    expect(apiMock.addInspection).not.toHaveBeenCalled();
  });

  it('does not keep a failure note after correcting the point to good', async () => {
    await start();
    await fireEvent.click(screen.getAllByRole('button', { name: 'Falla' })[0] as HTMLElement);
    await fireEvent.input(screen.getByLabelText(/¿Qué falla\?/), { target: { value: 'Ruido' } });
    for (const button of screen.getAllByRole('button', { name: 'Bien' })) {
      await fireEvent.click(button);
    }
    await fireEvent.click(screen.getByRole('button', { name: 'Guardar inspección' }));
    await screen.findByText(/sin fallas críticas/);
    expect(apiMock.addInspection.mock.calls[0]?.[1].results[0].notes).toBeNull();
  });

  it('says a clean inspection still leaves earlier failures pending', async () => {
    apiMock.inspections.mockResolvedValueOnce([]).mockResolvedValue([
      {
        id: 'x',
        inspected_at: '2026-11-01T10:00:00Z',
        passed: false,
        notes: null,
        inspected_by_name: 'ana',
        results: [failed]
      }
    ]);
    await start();
    for (const button of screen.getAllByRole('button', { name: 'Bien' })) {
      await fireEvent.click(button);
    }
    await fireEvent.click(screen.getByRole('button', { name: 'Guardar inspección' }));
    expect(await screen.findByText(/Hay 1 falla crítica sin resolver/)).toBeInTheDocument();
  });

  it('sends every answer', async () => {
    await start();
    for (const button of screen.getAllByRole('button', { name: 'Bien' })) {
      await fireEvent.click(button);
    }
    expect(screen.getByText('2 de 2')).toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: 'Guardar inspección' }));
    expect(await screen.findByText(/sin fallas críticas/)).toBeInTheDocument();
    const body = apiMock.addInspection.mock.calls[0]?.[1];
    expect(body.results.map((r: { passed: boolean }) => r.passed)).toEqual([true, true]);
  });

  it('shows pending critical failures first, with a reason to resolve them', async () => {
    apiMock.inspections.mockResolvedValue([
      {
        id: 'x',
        inspected_at: '2026-11-01T10:00:00Z',
        passed: false,
        notes: null,
        inspected_by_name: 'ana',
        results: [failed]
      }
    ]);
    render(VehicleInspectionsPanel, { vehicle, onchanged: vi.fn() });
    expect(await screen.findByText('1 falla crítica sin resolver')).toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: 'Resolver' }));
    expect(confirmMock.request).toHaveBeenCalledWith(
      expect.objectContaining({ requireReason: true })
    );
  });

  it('stops asking once the failure is resolved', async () => {
    apiMock.inspections.mockResolvedValue([
      {
        id: 'x',
        inspected_at: '2026-11-01T10:00:00Z',
        passed: false,
        notes: null,
        inspected_by_name: 'ana',
        results: [{ ...failed, resolved_at: '2026-11-02T10:00:00Z', resolution: 'Reparado' }]
      }
    ]);
    render(VehicleInspectionsPanel, { vehicle, onchanged: vi.fn() });
    await screen.findByText('No apta');
    expect(screen.queryByRole('button', { name: 'Resolver' })).not.toBeInTheDocument();
  });

  it('hides inspecting without permission', async () => {
    permissionMock.codes = new Set();
    render(VehicleInspectionsPanel, { vehicle, onchanged: vi.fn() });
    await screen.findByText(/aún no tiene inspecciones/);
    expect(screen.queryByRole('button', { name: 'Nueva inspección' })).not.toBeInTheDocument();
  });
});
