import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import ConfirmActionDialog from '$lib/components/ui/ConfirmActionDialog.svelte';
import { confirmation } from '$lib/stores/confirmation.svelte';

describe('ConfirmActionDialog', () => {
  beforeEach(() => confirmation.reset());
  afterEach(() => {
    confirmation.reset();
    cleanup();
  });

  it('renders the action context and gives initial focus to the safe option', async () => {
    render(ConfirmActionDialog);
    confirmation.request({
      kind: 'delete',
      title: 'Eliminar empleado',
      description: 'El empleado dejará de estar disponible.',
      resourceName: 'Ada Lovelace',
      confirmLabel: 'Eliminar empleado',
      execute: vi.fn()
    });

    expect(await screen.findByRole('alertdialog')).toBeInTheDocument();
    expect(screen.getByText('Ada Lovelace')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Cancelar' })).toHaveFocus());
  });

  it('does not execute the action when cancelled', async () => {
    const execute = vi.fn();
    render(ConfirmActionDialog);
    confirmation.request({
      kind: 'deactivate',
      title: 'Desactivar almacén',
      description: 'El almacén dejará de aceptar operaciones.',
      confirmLabel: 'Desactivar almacén',
      execute
    });

    await fireEvent.click(await screen.findByRole('button', { name: 'Cancelar' }));

    expect(execute).not.toHaveBeenCalled();
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  });

  it('executes once and closes after a successful operation', async () => {
    const execute = vi.fn().mockResolvedValue(undefined);
    render(ConfirmActionDialog);
    confirmation.request({
      kind: 'delete',
      title: 'Eliminar rol',
      description: 'El rol dejará de estar disponible.',
      confirmLabel: 'Eliminar rol',
      execute
    });

    const action = await screen.findByRole('button', { name: 'Eliminar rol' });
    await Promise.all([fireEvent.click(action), fireEvent.click(action)]);

    await waitFor(() => expect(execute).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument());
  });

  it('keeps the dialog open and displays a business error', async () => {
    render(ConfirmActionDialog);
    confirmation.request({
      kind: 'deactivate',
      title: 'Desactivar categoría',
      description: 'La categoría dejará de estar disponible.',
      confirmLabel: 'Desactivar categoría',
      execute: vi
        .fn()
        .mockRejectedValue(
          new Error('No puede desactivar una categoría utilizada por almacenes activos.')
        )
    });

    await fireEvent.click(await screen.findByRole('button', { name: 'Desactivar categoría' }));

    expect(
      await screen.findByText('No puede desactivar una categoría utilizada por almacenes activos.')
    ).toHaveAttribute('role', 'alert');
    expect(screen.getByRole('alertdialog')).toBeInTheDocument();
  });

  it('requires and forwards a deletion reason before executing', async () => {
    const execute = vi.fn().mockResolvedValue(undefined);
    render(ConfirmActionDialog);
    confirmation.request({
      kind: 'delete',
      title: 'Eliminar producto',
      description: 'El producto se enviará a la Papelera.',
      confirmLabel: 'Eliminar producto',
      requireReason: true,
      execute
    });

    const action = await screen.findByRole('button', { name: 'Eliminar producto' });
    await fireEvent.click(action);

    expect(execute).not.toHaveBeenCalled();
    expect(await screen.findByText('Indique un motivo de al menos 3 caracteres.')).toHaveAttribute(
      'role',
      'alert'
    );

    await fireEvent.input(screen.getByLabelText('Motivo de eliminación'), {
      target: { value: 'Registro creado por error' }
    });
    await fireEvent.click(action);

    await waitFor(() => expect(execute).toHaveBeenCalledWith('Registro creado por error'));
    await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument());
  });
});
