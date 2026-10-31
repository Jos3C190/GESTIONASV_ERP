import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import ButtonHost from './ButtonHost.svelte';

describe('Button (via host)', () => {
  it('renders its children', () => {
    render(ButtonHost, { props: { label: 'Guardar cambios' } });
    expect(screen.getByRole('button', { name: 'Guardar cambios' })).toBeInTheDocument();
  });

  it('applies the primary variant by default', () => {
    render(ButtonHost, { props: { label: 'Click' } });
    const btn = screen.getByRole('button', { name: 'Click' });
    expect(btn.className).toContain('bg-foreground');
  });

  it('disables when disabled prop is true', () => {
    render(ButtonHost, { props: { label: 'Click', disabled: true } });
    expect(screen.getByRole('button', { name: 'Click' })).toBeDisabled();
  });

  it('applies the danger variant', () => {
    render(ButtonHost, { props: { label: 'Eliminar', variant: 'danger' } });
    const btn = screen.getByRole('button', { name: 'Eliminar' });
    expect(btn.className).toContain('bg-danger');
  });
});