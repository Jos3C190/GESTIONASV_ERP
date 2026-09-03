import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import type { DocumentRecordOut } from '$lib/api/client';
import DocumentList from '$lib/features/documents/components/DocumentList.svelte';

function makeDocument(extension: string): DocumentRecordOut {
  return {
    id: 'document-1',
    company_id: 'company-1',
    module: 'general',
    owner_type: null,
    owner_id: null,
    owner_label: null,
    owner_deleted: false,
    category_id: 'category-1',
    category_name: 'Contratos',
    category_group: 'General',
    title: 'Contrato de servicios',
    description: null,
    reference_code: null,
    issuer: null,
    issued_on: null,
    expires_on: null,
    confidentiality: 'internal',
    tags: [],
    version_group_id: 'version-1',
    version_number: 1,
    is_current: true,
    replaces_document_id: null,
    business_status: 'active',
    original_filename: `contrato${extension}`,
    extension,
    content_type: extension === '.pdf' ? 'application/pdf' : 'application/octet-stream',
    size_bytes: 1024,
    checksum_sha256: 'a'.repeat(64),
    technical_status: 'active',
    failure_code: null,
    upload_expires_at: null,
    scanned_at: null,
    uploaded_by: null,
    created_by: null,
    updated_by: null,
    created_at: '2026-09-02T12:00:00Z',
    updated_at: '2026-09-02T12:00:00Z',
    ocr_status: null,
    ocr_available: false,
    ocr_failure_code: null,
    ocr_completed_at: null
  };
}

describe('DocumentList browser opening action', () => {
  it('offers one browser action for an active PDF', async () => {
    const onopenbrowser = vi.fn();
    render(DocumentList, {
      props: {
        documents: [makeDocument('.pdf')],
        onopenbrowser
      }
    });

    await fireEvent.click(
      screen.getByRole('button', { name: 'Más acciones para Contrato de servicios' })
    );

    expect(screen.getByRole('menuitem', { name: 'Abrir en navegador' })).toBeVisible();
    expect(screen.queryByRole('menuitem', { name: 'Vista previa' })).not.toBeInTheDocument();
    expect(screen.queryByRole('menuitem', { name: 'Vista completa' })).not.toBeInTheDocument();

    await fireEvent.click(screen.getByRole('menuitem', { name: 'Abrir en navegador' }));
    expect(onopenbrowser).toHaveBeenCalledWith(expect.objectContaining({ extension: '.pdf' }));
  });

  it('does not offer browser opening for non-PDF files', () => {
    render(DocumentList, {
      props: {
        documents: [makeDocument('.docx')],
        onopenbrowser: vi.fn()
      }
    });

    expect(
      screen.queryByRole('button', { name: 'Más acciones para Contrato de servicios' })
    ).not.toBeInTheDocument();
  });
});
