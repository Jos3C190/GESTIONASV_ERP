import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('$app/state', () => ({ page: { url: new URL('http://localhost/drivers') } }));
vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: { hasPermission: () => true, hasAnyPermission: () => true }
}));
vi.mock('$lib/stores/session.svelte', () => ({
  session: { user: { username: 'admin', is_superuser: true } }
}));
vi.mock('$lib/stores/company.svelte', () => ({ company: { id: 'company-1' } }));
vi.mock('$lib/stores/branch.svelte', () => ({
  branch: {
    id: null,
    active: null,
    label: 'Todas las sucursales',
    ready: true,
    accessAllBranches: true,
    branches: []
  }
}));
vi.mock('$lib/api/client', () => ({ api: {} }));
vi.mock('$lib/services/query-client', () => ({ clearPrivateQueryCache: vi.fn() }));

import Sidebar from './Sidebar.svelte';

afterEach(cleanup);

describe('Sidebar display controls', () => {
  it('keeps focus, current route and links when contracting and expanding the menu', async () => {
    const onToggleCollapse = vi.fn();
    const onNavigate = vi.fn();
    const props = { id: 'desktop-navigation', collapsed: false, onToggleCollapse, onNavigate };
    const { rerender } = render(Sidebar, props);
    const toggle = screen.getByRole('button', { name: 'Contraer menú' });
    const driverLink = screen.getByRole('link', { name: 'Conductores' });
    const destinations = screen.getAllByRole('link').map((link) => link.getAttribute('href'));

    expect(toggle).toHaveTextContent('Contraer menú');
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(toggle).toHaveAttribute('aria-controls', 'desktop-navigation');
    expect(driverLink).toHaveAttribute('aria-current', 'page');
    toggle.focus();
    await fireEvent.click(toggle);
    expect(onToggleCollapse).toHaveBeenCalledOnce();
    expect(onNavigate).not.toHaveBeenCalled();

    await rerender({ ...props, collapsed: true });
    const expand = screen.getByRole('button', { name: 'Expandir menú' });
    expect(expand).toBe(toggle);
    expect(expand).toHaveFocus();
    expect(expand).toHaveAttribute('aria-expanded', 'false');
    expect(driverLink).toHaveAttribute('aria-current', 'page');
    expect(screen.getAllByRole('link').map((link) => link.getAttribute('href'))).toEqual(
      destinations
    );

    await fireEvent.click(expand);
    await rerender(props);
    expect(screen.getByRole('button', { name: 'Contraer menú' })).toHaveFocus();
    expect(onToggleCollapse).toHaveBeenCalledTimes(2);
    expect(onNavigate).not.toHaveBeenCalled();
  });

  it('leaves mobile navigation without a collapse control and closes through onNavigate', async () => {
    const onNavigate = vi.fn();
    render(Sidebar, { onNavigate });
    expect(
      screen.queryByRole('button', { name: /Contraer menú|Expandir menú/ })
    ).not.toBeInTheDocument();
    await fireEvent.click(screen.getByRole('link', { name: 'Conductores' }));
    expect(onNavigate).toHaveBeenCalledOnce();
  });

  it('dismisses the expansion hint with Escape without moving focus or toggling the menu', async () => {
    const onToggleCollapse = vi.fn();
    render(Sidebar, { collapsed: true, onToggleCollapse });
    const expand = screen.getByRole('button', { name: 'Expandir menú' });
    expand.focus();
    expect(screen.getByText('Expandir menú')).toBeInTheDocument();
    await fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByText('Expandir menú')).not.toBeInTheDocument();
    expect(expand).toHaveFocus();
    expect(onToggleCollapse).not.toHaveBeenCalled();
    await fireEvent.pointerEnter(expand);
    expect(screen.getByText('Expandir menú')).toBeInTheDocument();
  });
});
