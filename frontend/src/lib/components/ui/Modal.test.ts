import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import Modal from './Modal.svelte';

describe('Modal', () => {
  it('puede renderizarse integrado en una página sin backdrop ni diálogo modal', () => {
    render(Modal, {
      props: {
        open: true,
        inline: true,
        title: 'Nueva ubicación',
        onclose: vi.fn()
      }
    });

    expect(screen.getByRole('region', { name: 'Nueva ubicación' })).toBeVisible();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
  it('aísla el chrome global y cierra un modal real con Escape', async () => {
    const chrome = document.createElement('header');
    chrome.dataset.appGlobalChrome = 'true';
    document.body.append(chrome);
    const onclose = vi.fn();
    const trigger = document.createElement('button');
    trigger.textContent = 'Abrir';
    document.body.append(trigger);
    trigger.focus();

    const view = render(Modal, { props: { open: true, title: 'Confirmar acción', onclose } });
    await waitFor(() => expect(chrome).toHaveAttribute('aria-hidden', 'true'));
    expect(chrome).toHaveProperty('inert', true);
    expect(screen.getByRole('dialog', { name: 'Confirmar acción' })).toBeVisible();

    await fireEvent.keyDown(window, { key: 'Escape' });
    expect(onclose).toHaveBeenCalledTimes(1);

    view.unmount();
    expect(chrome).not.toHaveAttribute('aria-hidden');
    expect(chrome).toHaveProperty('inert', false);
    trigger.remove();
    chrome.remove();
  });
  it('bloquea el cierre mientras una operación está activa', async () => {
    const onclose = vi.fn();
    render(Modal, { props: { open: true, title: 'Importando carpeta', onclose, preventClose: true } });

    await fireEvent.keyDown(window, { key: 'Escape' });
    expect(onclose).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Cerrar' })).toBeDisabled();
  });
});
