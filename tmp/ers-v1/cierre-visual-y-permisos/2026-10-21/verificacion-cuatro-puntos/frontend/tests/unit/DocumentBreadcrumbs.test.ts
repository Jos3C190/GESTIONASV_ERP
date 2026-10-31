import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import DocumentBreadcrumbs from '$lib/features/documents/components/DocumentBreadcrumbs.svelte';

describe('DocumentBreadcrumbs', () => {
  it('marks the current folder and keeps ancestor navigation', () => {
    render(DocumentBreadcrumbs, {
      props: {
        items: [
          { label: 'Documentos', href: '/documents' },
          { label: 'Empleados', href: '/documents/employees' }
        ],
        current: 'Ana Pérez'
      }
    });

    expect(screen.getByRole('link', { name: 'Documentos' })).toHaveAttribute('href', '/documents');
    expect(screen.getByRole('link', { name: 'Empleados' })).toHaveAttribute(
      'href',
      '/documents/employees'
    );
    expect(screen.getByText('Ana Pérez')).toHaveAttribute('aria-current', 'page');
  });
});
