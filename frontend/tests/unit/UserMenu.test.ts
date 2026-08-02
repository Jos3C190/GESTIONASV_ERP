import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import UserMenu from '$lib/components/ui/UserMenu.svelte';
import type { CurrentUser } from '$lib/stores/session.svelte';

const user: CurrentUser = {
  id: 'user-1',
  username: 'superadmin',
  email: 'superadmin@erp-system.dev',
  is_active: true,
  is_superuser: true,
  mfa_enabled: false,
  last_login_at: null,
  created_at: '2026-08-01T00:00:00Z',
  updated_at: '2026-08-01T00:00:00Z'
};

describe('UserMenu', () => {
  afterEach(cleanup);

  it('shows the account identity and unavailable settings state', async () => {
    render(UserMenu, { props: { user, onLogout: vi.fn() } });

    await fireEvent.click(
      screen.getByRole('button', { name: 'Abrir menú de cuenta de superadmin' })
    );

    expect(screen.getByRole('menu', { name: 'Menú de cuenta' })).toBeInTheDocument();
    expect(screen.getByText('superadmin@erp-system.dev')).toBeInTheDocument();
    expect(screen.getByText('Superadministrador')).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: /Configuración/ })).toBeDisabled();
  });

  it('closes the menu and delegates logout', async () => {
    const onLogout = vi.fn().mockResolvedValue(undefined);
    render(UserMenu, { props: { user, onLogout } });

    await fireEvent.click(
      screen.getByRole('button', { name: 'Abrir menú de cuenta de superadmin' })
    );
    await fireEvent.click(screen.getByRole('menuitem', { name: 'Cerrar sesión' }));

    await waitFor(() => expect(onLogout).toHaveBeenCalledOnce());
    expect(screen.queryByRole('menu', { name: 'Menú de cuenta' })).not.toBeInTheDocument();
  });
});
