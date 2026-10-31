import { fireEvent, render, screen } from '@testing-library/svelte';
import { expect, it, vi } from 'vitest';
import Controls from '$lib/features/inventory/components/KardexReconciliationControls.svelte';

it('submits an explicit cut and product filter only when requested', async () => {
  const onquery = vi.fn();
  render(Controls, {
    asOf: '2026-10-29',
    query: '',
    differenceOnly: false,
    loading: false,
    onquery
  });
  await fireEvent.input(screen.getByLabelText('Corte por fecha de registro'), {
    target: { value: '2026-10-28' }
  });
  await fireEvent.input(screen.getByLabelText('Producto o código'), {
    target: { value: ' Azúcar ' }
  });
  await fireEvent.click(screen.getByRole('checkbox', { name: 'Con diferencia o sin base' }));
  expect(onquery).not.toHaveBeenCalled();
  await fireEvent.submit(screen.getByRole('button', { name: 'Consultar corte' }).closest('form')!);
  expect(onquery).toHaveBeenCalledWith({ as_of: '2026-10-28', q: 'Azúcar', difference_only: true });
});
