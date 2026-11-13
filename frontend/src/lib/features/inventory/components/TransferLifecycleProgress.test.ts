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

it('en recepción parcial la etapa Recepción sigue activa y en tono de advertencia', () => {
  render(TransferLifecycleProgress, { status: 'partially_received', withApproval: true });
  const current = screen.getByRole('listitem', { current: 'step' });
  expect(current).toHaveTextContent('Recepción');
  expect(current).toHaveTextContent('Recepción parcial');
  expect(current).toHaveAttribute('data-tone', 'warning');
  // Not a completed step: it shows its number, not a check.
  expect(current).not.toHaveTextContent('✓');
  expect(screen.getAllByRole('listitem').filter((item) => item.dataset.tone)).toHaveLength(1);
});

it('con discrepancia la etapa Recepción queda activa y en advertencia', () => {
  render(TransferLifecycleProgress, { status: 'discrepancy' });
  const current = screen.getByRole('listitem', { current: 'step' });
  expect(current).toHaveTextContent('Recepción');
  expect(current).toHaveTextContent('Con discrepancia');
  expect(current).toHaveAttribute('data-tone', 'warning');
  expect(labels()).toEqual(['Preparación', 'En tránsito', 'Recepción']);
});

it('cerrado con ajuste deja todas las etapas completas y ninguna activa', () => {
  render(TransferLifecycleProgress, { status: 'closed_with_adjustment', withApproval: true });
  expect(screen.queryByRole('listitem', { current: 'step' })).not.toBeInTheDocument();
  const items = screen.getAllByRole('listitem');
  expect(items).toHaveLength(4);
  for (const item of items) expect(item).toHaveTextContent('✓');
});

it('una incidencia marca la etapa de tránsito, no la de recepción', () => {
  render(TransferLifecycleProgress, { status: 'incident' });
  const current = screen.getByRole('listitem', { current: 'step' });
  expect(current).toHaveTextContent('En tránsito');
  expect(current).toHaveAttribute('data-tone', 'warning');
});
