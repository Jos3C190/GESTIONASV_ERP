import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import DocumentFolderCard from '$lib/features/documents/components/DocumentFolderCard.svelte';

describe('DocumentFolderCard', () => {
  it('exposes a keyboard-accessible link with safe folder summaries', () => {
    render(DocumentFolderCard, {
      props: {
        href: '/documents/employees/employee-1',
        folder: {
          id: 'employee:employee-1',
          kind: 'employee',
          name: 'Ana Pérez',
          module: 'employees',
          parent_id: 'employees',
          employee_id: 'employee-1',
          category_id: null,
          employee_code: 'EMP-001',
          employee_status: 'activo',
          document_count: 4,
          active_count: 3,
          expiring_count: 1,
          expired_count: 0,
          latest_document_at: '2026-09-02T12:00:00Z',
          can_upload: true
        }
      }
    });

    const link = screen.getByRole('link', { name: 'Abrir carpeta Ana Pérez' });
    expect(link).toHaveAttribute('href', '/documents/employees/employee-1');
    expect(link).toHaveTextContent('EMP-001');
    expect(link).toHaveTextContent('4');
    expect(link).toHaveTextContent('3 vigentes');
  });
});
