import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Modal from './Modal.svelte';

afterEach(cleanup);

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
    render(Modal, {
      props: { open: true, title: 'Importando carpeta', onclose, preventClose: true }
    });

    await fireEvent.keyDown(window, { key: 'Escape' });
    expect(onclose).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Cerrar' })).toBeDisabled();
  });
  it('gives stacked dialogs unique names and keeps only the top dialog handling Escape', async () => {
    const chrome = document.createElement('header');
    chrome.dataset.appGlobalChrome = 'true';
    document.body.append(chrome);
    const parentClose = vi.fn();
    const childClose = vi.fn();
    const parent = render(Modal, {
      open: true,
      title: 'Resumen del conductor',
      onclose: parentClose
    });
    const child = render(Modal, { open: true, title: 'Cargar licencia', onclose: childClose });
    const parentId = screen
      .getByRole('dialog', { name: 'Resumen del conductor' })
      .getAttribute('aria-labelledby');
    const childId = screen
      .getByRole('dialog', { name: 'Cargar licencia' })
      .getAttribute('aria-labelledby');
    expect(parentId).not.toBe(childId);
    await fireEvent.keyDown(window, { key: 'Escape' });
    expect(childClose).toHaveBeenCalledOnce();
    expect(parentClose).not.toHaveBeenCalled();
    child.unmount();
    expect(chrome).toHaveProperty('inert', true);
    expect(chrome).toHaveAttribute('aria-hidden', 'true');
    await fireEvent.keyDown(window, { key: 'Escape' });
    expect(parentClose).toHaveBeenCalledOnce();
    parent.unmount();
    expect(chrome).toHaveProperty('inert', false);
    chrome.remove();
  });
  it('does not close the parent while the top dialog prevents closing', async () => {
    const parentClose = vi.fn();
    const childClose = vi.fn();
    render(Modal, { open: true, title: 'Expediente', onclose: parentClose });
    render(Modal, {
      open: true,
      title: 'Subiendo licencia',
      onclose: childClose,
      preventClose: true
    });
    await fireEvent.keyDown(window, { key: 'Escape' });
    expect(parentClose).not.toHaveBeenCalled();
    expect(childClose).not.toHaveBeenCalled();
  });
});
