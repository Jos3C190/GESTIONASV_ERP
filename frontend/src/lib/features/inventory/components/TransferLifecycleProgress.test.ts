import { cleanup, render, screen, within } from '@testing-library/svelte';
import { afterEach, expect, it } from 'vitest';
import TransferLifecycleProgress from './TransferLifecycleProgress.svelte';

afterEach(cleanup);

const labels = () =>
  within(screen.getByLabelText('Avance del traslado'))
    .getAllByRole('listitem')
    .map((item) => item.querySelector('span:nth-of-type(2)')?.textContent?.trim());

it('sin aprobación conserva los tres pasos de siempre', () => {
  render(TransferLifecycleProgress, { status: 'in_transit' });
  expect(labels()).toEqual(['Preparación', 'En tránsito', 'Recepción']);
  expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent('En tránsito');
});

it('con aprobación agrega el paso entre la preparación y el tránsito', () => {
  render(TransferLifecycleProgress, { status: 'pending_approval', withApproval: true });
  expect(labels()).toEqual(['Preparación', 'Aprobación', 'En tránsito', 'Recepción']);
  const current = screen.getByRole('listitem', { current: 'step' });
  expect(current).toHaveTextContent('Aprobación');
  expect(current).toHaveTextContent('Antes del despacho');
});

it('marca la aprobación como lograda cuando el traslado ya está aprobado', () => {
  render(TransferLifecycleProgress, { status: 'approved', withApproval: true });
  const current = screen.getByRole('listitem', { current: 'step' });
  expect(current).toHaveTextContent('Aprobado');
  expect(current).toHaveTextContent('✓');
});

it('pasa por la aprobación hasta llegar a la recepción', () => {
  render(TransferLifecycleProgress, { status: 'received', withApproval: true });
  expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent('Recepción');
  cleanup();
  render(TransferLifecycleProgress, { status: 'in_transit', withApproval: true });
  expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent('En tránsito');
});
