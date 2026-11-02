import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Driver } from './api';

const apiMock = vi.hoisted(() => ({
  list: vi.fn(),
  summary: vi.fn(),
  candidates: vi.fn(),
  create: vi.fn(),
  documents: vi.fn(),
  captureCapabilities: vi.fn().mockResolvedValue({ enabled: false, extraction_available: false }),
  assignments: vi.fn(),
  trips: vi.fn()
}));
const documentsMock = vi.hoisted(() => ({ list: vi.fn(), categories: vi.fn() }));
const navigationMock = vi.hoisted(() => ({ goto: vi.fn() }));
vi.mock('$app/navigation', () => navigationMock);
vi.mock('$lib/stores/branch.svelte', () => ({
  branch: {
    id: null,
    label: 'Todas las sucursales',
    branches: [{ id: 'b1', name: 'Roosevelt' }],
    accessAllBranches: true
  }
}));
const permissionMock = vi.hoisted(() => ({ codes: new Set<string>() }));

vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  driversApi: apiMock
}));
vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: { hasPermission: (code: string) => permissionMock.codes.has(code) }
}));

import DriversWorkspace from './DriversWorkspace.svelte';

const driver: Driver = {
  id: 'd1',
  employee: {
    id: 'e1',
    code: 'EMP-001',
    name: 'Carlos Martínez',
    initials: 'CM',
    document_id: '01234567-8',
    phone: null,
    photo_url: null,
    position: 'Motorista',
    status: 'activo'
  },
  branch_id: 'b1',
  branch_name: 'Roosevelt',
  license: {
    license_class: 'pesada',
    number: 'L-123',
    expires_on: '2026-09-01',
    document_id: 'doc'
  },
  status: 'active',
  status_reason: null,
  notes: null,
  vehicle: {
    assignment_id: 'a1',
    vehicle_id: 'v1',
    code: 'FL-001',
    plate: 'C 123-456',
    kind: 'refrigerated',
    since: '2026-10-01T00:00:00Z'
  },
  compliance: {
    state: 'blocked',
    issues: [
      {
        code: 'document_expired',
        severity: 'blocking',
        message: 'Licencia de conducir vencida desde el 01/09/2026.'
      }
    ]
  },
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z'
};

beforeEach(() => {
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
  );
  documentsMock.list.mockResolvedValue({
    items: [],
    meta: { total: 0, pages: 1, page: 1, size: 100 }
  });
  documentsMock.categories.mockResolvedValue([]);
  apiMock.documents.mockImplementation((id: string) => ({
    basePath: `/drivers/${id}`,
    get: vi.fn().mockResolvedValue({ content_type: 'application/pdf', technical_status: 'active' }),
    ...documentsMock
  }));
  apiMock.assignments.mockResolvedValue([]);
  apiMock.trips.mockResolvedValue([]);
  apiMock.candidates.mockResolvedValue([
    {
      employee_id: 'e2',
      code: 'EMP-002',
      name: 'Ana López',
      position: 'Motorista',
      photo_url: null
    }
  ]);
  apiMock.create.mockResolvedValue(driver);
  permissionMock.codes = new Set(['drivers:read']);
  apiMock.list.mockResolvedValue({
    items: [driver],
    meta: { page: 1, size: 50, total: 1, pages: 1 }
  });
  apiMock.summary.mockResolvedValue({
    total: 1,
    active: 1,
    fit: 0,
    warning: 0,
    blocked: 1,
    assigned: 1
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe('drivers workspace', () => {
  it('lists drivers with license, vehicle and fitness', async () => {
    render(DriversWorkspace);
    const row = (await screen.findByRole('link', { name: 'Carlos Martínez' })).closest('tr')!;
    expect(within(row).getByText('FL-001')).toBeVisible();
    expect(within(row).getByText('C 123-456')).toBeVisible();
    expect(
      screen.getByText('Licencia de conducir vencida desde el 01/09/2026.', {
        selector: '.issues span'
      })
    ).toBeVisible();
    expect(within(row).getByRole('link', { name: 'Carlos Martínez' })).toHaveAttribute(
      'href',
      '/drivers/d1'
    );
    expect(screen.queryByRole('button', { name: /Nuevo conductor/ })).not.toBeInTheDocument();
  });

  it('allows registering drivers with drivers:create', async () => {
    permissionMock.codes.add('drivers:create');
    render(DriversWorkspace);
    expect(await screen.findByRole('button', { name: /Nuevo conductor/ })).toBeVisible();
  });

  it('loads real history only when requested and offers retry on failure', async () => {
    apiMock.assignments.mockRejectedValueOnce(new Error('network'));
    render(DriversWorkspace);
    await screen.findByRole('link', { name: 'Carlos Martínez' });
    expect(apiMock.assignments).not.toHaveBeenCalled();
    await fireEvent.click(screen.getByRole('button', { name: 'Historial' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo cargar el historial');
    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar historial' }));
    expect(await screen.findByText('Aún no tiene asignaciones registradas.')).toBeVisible();
    expect(apiMock.assignments).toHaveBeenCalledWith('d1');
  });

  it('opens the licensed document manager with the selected owner and respects upload permissions', async () => {
    render(DriversWorkspace);
    await screen.findByRole('link', { name: 'Carlos Martínez' });
    await fireEvent.click(screen.getByRole('button', { name: 'Documentos' }));
    await waitFor(() => expect(documentsMock.list).toHaveBeenCalled());
    expect(apiMock.documents).toHaveBeenCalledWith('d1');
    expect(screen.queryByRole('button', { name: 'Agregar documento' })).not.toBeInTheDocument();
  });

  it('allows document upload with drivers:documents', async () => {
    permissionMock.codes.add('drivers:documents');
    render(DriversWorkspace);
    await screen.findByRole('link', { name: 'Carlos Martínez' });
    await fireEvent.click(screen.getByRole('button', { name: 'Documentos' }));
    expect(await screen.findByRole('button', { name: 'Agregar documento' })).toBeVisible();
  });

  it('filters administrative status on the server and debounces search', async () => {
    render(DriversWorkspace);
    await screen.findByRole('link', { name: 'Carlos Martínez' });
    await fireEvent.click(screen.getByRole('button', { name: 'Suspendidos' }));
    await waitFor(() =>
      expect(apiMock.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ status: 'suspended', page: 1, size: 12 })
      )
    );
    await fireEvent.input(screen.getByRole('searchbox', { name: 'Buscar conductores' }), {
      target: { value: 'Carlos' }
    });
    await waitFor(() =>
      expect(apiMock.list).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: 'Carlos', page: 1 })
      )
    );
  });

  it('keeps all pages accessible and updates server pagination', async () => {
    apiMock.list.mockResolvedValue({
      items: [driver],
      meta: { page: 1, size: 12, total: 14, pages: 2 }
    });
    render(DriversWorkspace);
    await screen.findByRole('link', { name: 'Carlos Martínez' });
    await fireEvent.click(screen.getByRole('button', { name: 'Página siguiente' }));
    await waitFor(() =>
      expect(apiMock.list).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2, size: 12 }))
    );
  });

  it('restores focus when the inspector closes', async () => {
    render(DriversWorkspace);
    const open = await screen.findByRole('button', { name: 'Ver resumen de Carlos Martínez' });
    await fireEvent.click(open);
    await fireEvent.click(screen.getByRole('button', { name: 'Cerrar resumen del conductor' }));
    expect(screen.queryByRole('complementary')).not.toBeInTheDocument();
    await waitFor(() => expect(open).toHaveFocus());
  });

  it('offers recovery for failed list loads without presenting an empty directory as success', async () => {
    apiMock.list.mockRejectedValueOnce(new Error('network'));
    render(DriversWorkspace);
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudieron cargar');
    expect(screen.getByText('El directorio no está disponible')).toBeVisible();
    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    expect(await screen.findByRole('link', { name: 'Carlos Martínez' })).toBeVisible();
  });

  it('registers an eligible employee through the existing API and opens the full profile', async () => {
    permissionMock.codes.add('drivers:create');
    render(DriversWorkspace);
    await fireEvent.click(await screen.findByRole('button', { name: 'Nuevo conductor' }));
    await fireEvent.click(await screen.findByRole('radio', { name: /Ana López/ }));
    await fireEvent.click(screen.getByRole('button', { name: 'Registrar conductor' }));
    await waitFor(() =>
      expect(apiMock.create).toHaveBeenCalledWith({
        employee_id: 'e2',
        branch_id: 'b1',
        license_class: 'liviana',
        notes: null
      })
    );
    expect(navigationMock.goto).toHaveBeenCalledWith('/drivers/d1');
  });

  it('opens the responsive summary as a dialog instead of compressing the directory', async () => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
    );
    render(DriversWorkspace);
    const open = await screen.findByRole('button', { name: 'Ver resumen de Carlos Martínez' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    await fireEvent.click(open);
    expect(await screen.findByRole('dialog', { name: 'Resumen del conductor' })).toBeVisible();
    await fireEvent.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Cerrar' })
    );
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('switches the document owner and lazy history to the newly selected driver', async () => {
    const second = {
      ...driver,
      id: 'd2',
      employee: { ...driver.employee, name: 'Ana López', code: 'EMP-002', initials: 'AL' }
    };
    apiMock.list.mockResolvedValue({
      items: [driver, second],
      meta: { page: 1, size: 12, total: 2, pages: 1 }
    });
    render(DriversWorkspace);
    await fireEvent.click(await screen.findByRole('button', { name: 'Ver resumen de Ana López' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Documentos' }));
    await waitFor(() => expect(apiMock.documents).toHaveBeenLastCalledWith('d2'));
    await fireEvent.click(screen.getByRole('button', { name: 'Historial' }));
    await waitFor(() => expect(apiMock.assignments).toHaveBeenCalledWith('d2'));
    expect(apiMock.trips).toHaveBeenCalledWith('d2');
  });
  it('recovers eligible employees after a candidate service failure', async () => {
    permissionMock.codes.add('drivers:create');
    apiMock.candidates.mockRejectedValueOnce(new Error('network'));
    render(DriversWorkspace);
    await fireEvent.click(await screen.findByRole('button', { name: 'Nuevo conductor' }));
    await fireEvent.click(await screen.findByRole('button', { name: 'Reintentar empleados' }));
    expect(await screen.findByRole('radio', { name: /Ana López/ })).toBeVisible();
  });
  it('distinguishes a registered license without expiry from a missing license', async () => {
    apiMock.list.mockResolvedValue({
      items: [{ ...driver, license: { ...driver.license, expires_on: null } }],
      meta: { page: 1, size: 12, total: 1, pages: 1 }
    });
    render(DriversWorkspace);
    const row = (await screen.findByRole('link', { name: 'Carlos Martínez' })).closest('tr')!;
    expect(within(row).getByText('Sin vencimiento registrado')).toBeVisible();
    expect(within(row).queryByText('Sin licencia cargada')).not.toBeInTheDocument();
  });
});
