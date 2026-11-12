import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { HttpError } from '../../src/lib/api/client';
import SettingsPage from '../../src/routes/(app)/transfers/settings/+page.svelte';

const mocks = vi.hoisted(() => ({
  settings: vi.fn(),
  saveSettings: vi.fn(),
  permissions: new Set<string>()
}));
vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: { hasPermission: (code: string) => mocks.permissions.has(code) }
}));
vi.mock('$lib/features/inventory/transfer-documents', () => ({
  inventoryTransfersApi: { settings: mocks.settings, saveSettings: mocks.saveSettings }
}));

const rules = (patch: Record<string, unknown> = {}) => ({
  allow_branch_to_branch: false,
  allow_branch_to_central: false,
  require_approval: true,
  updated_at: null,
  pending_count: 0,
  approved_count: 0,
  ...patch
});

beforeEach(() => {
  mocks.settings.mockReset().mockResolvedValue(rules());
  mocks.saveSettings.mockReset();
  mocks.permissions = new Set(['inventory:read']);
});

describe('Reglas de traslados', () => {
  it('muestra las reglas en solo lectura a quien no puede configurarlas', async () => {
    render(SettingsPage);

    expect(await screen.findByRole('heading', { name: 'Reglas de traslados' })).toBeInTheDocument();
    expect(screen.getByLabelText(/Permitir traslados entre sucursales/)).toBeDisabled();
    expect(screen.getByLabelText(/Permitir retornos a la bodega central/)).toBeDisabled();
    const approval = screen.getByLabelText(
      /Exigir aprobación para traslados que salen de una sucursal/
    );
    expect(approval).toBeDisabled();
    expect(approval).toBeChecked();
    expect(screen.queryByRole('button', { name: 'Guardar cambios' })).not.toBeInTheDocument();
    expect(screen.getByText(/Solo quien tenga el permiso de configurar/)).toBeInTheDocument();
  });

  it('no consulta nada sin permiso de lectura', () => {
    mocks.permissions = new Set();
    render(SettingsPage);
    expect(screen.getByRole('alert')).toHaveTextContent(
      'No tienes permiso para ver los traslados.'
    );
    expect(mocks.settings).not.toHaveBeenCalled();
  });

  it('guarda los cambios y confirma con un mensaje de estado', async () => {
    mocks.permissions.add('inventory:transfer_settings');
    mocks.saveSettings.mockResolvedValue(
      rules({ allow_branch_to_branch: true, require_approval: false })
    );
    render(SettingsPage);

    const between = await screen.findByLabelText(/Permitir traslados entre sucursales/);
    expect(between).toBeEnabled();
    await fireEvent.click(between);
    await fireEvent.click(screen.getByLabelText(/Exigir aprobación/));
    await fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    await waitFor(() =>
      expect(mocks.saveSettings).toHaveBeenCalledWith({
        allow_branch_to_branch: true,
        allow_branch_to_central: false,
        require_approval: false
      })
    );
    expect(await screen.findByText('Se guardó la configuración.')).toBeInTheDocument();
    expect(screen.getByLabelText(/Exigir aprobación/)).not.toBeChecked();
  });

  it('advierte que apagar una ruta congela lo pendiente y lo aprobado', async () => {
    mocks.settings.mockResolvedValue(
      rules({ allow_branch_to_branch: true, pending_count: 2, approved_count: 1 })
    );
    render(SettingsPage);
    const warning = await screen.findByText(
      /Hay 2 traslados pendientes de aprobación y 1 aprobado/
    );
    expect(warning).toHaveTextContent('quedan congelados');
    expect(warning).toHaveTextContent('rechazar, retirar o cancelar');
  });

  it('no muestra la advertencia cuando no hay nada que congelar', async () => {
    render(SettingsPage);
    await screen.findByRole('heading', { name: 'Reglas de traslados' });
    expect(screen.queryByText(/quedan congelados/)).not.toBeInTheDocument();
  });

  it('informa del fallo al cargar y al guardar', async () => {
    mocks.permissions.add('inventory:transfer_settings');
    mocks.settings.mockRejectedValueOnce(new HttpError('http_error', 'No se pudo conectar.', 500));
    render(SettingsPage);
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo conectar.');

    mocks.settings.mockResolvedValue(rules());
    await fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    await screen.findByLabelText(/Permitir traslados entre sucursales/);

    mocks.saveSettings.mockRejectedValue(
      new HttpError('forbidden', 'Permiso requerido: inventory:transfer_settings', 403)
    );
    await fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Permiso requerido');
  });
});
