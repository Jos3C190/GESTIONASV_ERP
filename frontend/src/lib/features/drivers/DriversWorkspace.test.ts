import { cleanup, render, screen, within } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Driver } from './api';

const apiMock = vi.hoisted(() => ({ list: vi.fn(), summary: vi.fn(), candidates: vi.fn() }));
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
});

describe('drivers workspace', () => {
  it('lists drivers with license, vehicle and fitness', async () => {
    render(DriversWorkspace);
    const row = (await screen.findByText('Carlos Martínez')).closest('tr')!;
    expect(within(row).getByText('FL-001 · C 123-456')).toBeVisible();
    expect(
      within(row).getByText('Licencia de conducir vencida desde el 01/09/2026.')
    ).toBeVisible();
    expect(within(row).getByRole('link')).toHaveAttribute('href', '/drivers/d1');
    expect(screen.queryByRole('button', { name: /Nuevo conductor/ })).not.toBeInTheDocument();
  });

  it('allows registering drivers with drivers:create', async () => {
    permissionMock.codes.add('drivers:create');
    render(DriversWorkspace);
    expect(await screen.findByRole('button', { name: /Nuevo conductor/ })).toBeVisible();
  });
});
