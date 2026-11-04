import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { DocumentRecordOut } from '$lib/api/client';
import { formatDocumentDate, isCaptureOnly } from '../document-upload';
import DocumentDetailPanel from './DocumentDetailPanel.svelte';
import DocumentList from './DocumentList.svelte';

function record(category_code: string, title: string): DocumentRecordOut {
  return {
    id: title,
    title,
    category_id: 'category',
    category_code,
    category_name: 'Categoría',
    category_group: null,
    business_status: 'current',
    technical_status: 'active',
    extension: '.jpg',
    size_bytes: 1024,
    original_filename: `${title}.jpg`,
    tags: []
  } as unknown as DocumentRecordOut;
}

const actions = {
  canUpdate: true,
  canReplace: true,
  onupdate: vi.fn(),
  onreplace: vi.fn(),
  onversions: vi.fn()
};

async function menuFor(title: string) {
  // La tabla dibuja una versión móvil y otra de escritorio: ambas ofrecen el mismo menú.
  const [trigger] = screen.getAllByRole('button', { name: `Más acciones para ${title}` });
  await fireEvent.click(trigger!);
  return (await screen.findAllByRole('menuitem')).map((item) => item.textContent?.trim());
}

describe('formatDocumentDate', () => {
  it('keeps the calendar day whatever the time zone', () => {
    expect(formatDocumentDate('2029-05-31')).toBe(
      new Date(2029, 4, 31).toLocaleDateString('es-SV')
    );
  });
});

describe('capture-only documents', () => {
  afterEach(() => cleanup());

  it('recognises the license categories', () => {
    expect(isCaptureOnly({ category_code: 'driver_license' })).toBe(true);
    expect(isCaptureOnly({ category_code: 'driver_license_back' })).toBe(true);
    expect(isCaptureOnly({ category_code: 'circulation_card' })).toBe(true);
    expect(isCaptureOnly({ category_code: 'circulation_card_back' })).toBe(true);
    expect(isCaptureOnly({ category_code: 'dui' })).toBe(false);
    expect(isCaptureOnly({})).toBe(false);
  });

  it('does not offer editing or replacing a license in the list', async () => {
    render(DocumentList, {
      documents: [record('driver_license', 'Licencia')],
      viewMode: 'table',
      ...actions
    });

    const items = await menuFor('Licencia');

    expect(items).not.toContain('Editar metadatos');
    expect(items).not.toContain('Reemplazar archivo');
    expect(items).toContain('Ver versiones');
  });

  it('keeps those actions for any other document', async () => {
    render(DocumentList, { documents: [record('dui', 'DUI')], viewMode: 'table', ...actions });

    const items = await menuFor('DUI');

    expect(items).toContain('Editar metadatos');
    expect(items).toContain('Reemplazar archivo');
  });

  it('does not offer them in the detail panel either', () => {
    render(DocumentDetailPanel, {
      document: record('driver_license', 'Licencia'),
      onclose: vi.fn(),
      ...actions
    });

    expect(screen.queryByRole('button', { name: 'Editar' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Reemplazar' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Versiones' })).toBeInTheDocument();
  });

  it('shows the given hint when there is nothing to list', () => {
    render(DocumentList, { documents: [], emptyHint: 'Usa la captura guiada.' });

    expect(screen.getByText('Usa la captura guiada.')).toBeInTheDocument();
    expect(screen.queryByText(/Carga el primer documento/)).toBeNull();
  });
});
