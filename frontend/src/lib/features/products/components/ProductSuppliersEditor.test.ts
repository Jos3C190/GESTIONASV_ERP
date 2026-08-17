import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import ProductSuppliersEditor from './ProductSuppliersEditor.svelte';

vi.mock('$lib/api/suppliers', () => ({
  suppliersApi: {
    listSuppliers: vi.fn().mockResolvedValue({
      items: [{ id_supplier: 7, code: 'SUP-007', name: 'Proveedor de prueba' }],
      meta: { page: 1, size: 100, total: 1, pages: 1 }
    }),
    currencies: vi.fn().mockResolvedValue([
      {
        code: 'USD',
        name: 'Dólar estadounidense',
        symbol: '$',
        decimal_places: 2,
        is_active: true
      }
    ])
  }
}));

describe('ProductSuppliersEditor', () => {
  it('permite agregar una relación y muestra el proveedor preferido', async () => {
    render(ProductSuppliersEditor, { props: { relations: [] } });
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Agregar proveedor' })).toBeEnabled()
    );

    await fireEvent.click(screen.getByRole('button', { name: 'Agregar proveedor' }));

    expect(screen.getByText('Proveedor 1')).toBeInTheDocument();
    expect(screen.getByText('Preferido')).toBeInTheDocument();
    expect(screen.getByLabelText('Proveedor')).toBeInTheDocument();
  });

  it('oculta controles de edición sin permiso', async () => {
    render(ProductSuppliersEditor, { props: { relations: [], editable: false } });
    await waitFor(() =>
      expect(screen.getByText(/No hay proveedores vinculados/)).toBeInTheDocument()
    );

    expect(screen.queryByRole('button', { name: 'Agregar proveedor' })).not.toBeInTheDocument();
  });
});
