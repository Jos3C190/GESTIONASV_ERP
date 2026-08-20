import { render, screen } from '@testing-library/svelte';
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
});
