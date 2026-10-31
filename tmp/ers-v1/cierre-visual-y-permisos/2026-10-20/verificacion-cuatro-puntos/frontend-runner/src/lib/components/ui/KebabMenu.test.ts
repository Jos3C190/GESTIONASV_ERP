import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import KebabMenu from './KebabMenu.svelte';

describe('KebabMenu', () => {
  it('muestra el icono de variantes en la acción de configuración', async () => {
    render(KebabMenu, {
      props: {
        items: [
          {
            id: 'variants',
            label: 'Configurar variantes',
            icon: 'variants',
            onClick: vi.fn()
          }
        ]
      }
    });

    await fireEvent.click(screen.getByRole('button', { name: 'Más opciones' }));

    const action = screen.getByRole('menuitem', { name: 'Configurar variantes' });
    expect(action.querySelector('svg')).toBeTruthy();
    expect(action.querySelectorAll('rect')).toHaveLength(4);
  });
});
