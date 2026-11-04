import { cleanup, render, screen, within } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { OwnedDocumentsApi } from '$lib/api/owned-documents';
import OwnedDocumentsPanel from './OwnedDocumentsPanel.svelte';

vi.mock('$lib/stores/permissions.svelte', () => ({
  permissions: { hasPermission: () => true }
}));

const owner = {
  list: vi.fn().mockResolvedValue({ items: [] }),
  categories: vi.fn().mockResolvedValue([
    {
      id: 'card',
      code: 'circulation_card',
      name: 'Tarjeta de circulación',
      compliance_required: true
    },
    { id: 'policy', code: 'insurance_policy', name: 'Póliza de seguro', compliance_required: true }
  ])
} as unknown as OwnedDocumentsApi;

describe('OwnedDocumentsPanel', () => {
  afterEach(() => cleanup());

  it('lists a capture-only document as pending without offering to upload it', async () => {
    render(OwnedDocumentsPanel, {
      owner,
      title: 'Documentos',
      description: 'Del vehículo',
      permissionPrefix: 'fleet_documents'
    });

    const pending = await screen.findByRole('status');
    const card = within(pending).getByText('Tarjeta de circulación').closest('li') as HTMLElement;
    const policy = within(pending).getByText('Póliza de seguro').closest('li') as HTMLElement;

    expect(within(card).queryByRole('button', { name: 'Cargar' })).toBeNull();
    expect(within(policy).getByRole('button', { name: 'Cargar' })).toBeInTheDocument();
    expect(within(card).getByText(/captura guiada/)).toBeInTheDocument();
  });
});
