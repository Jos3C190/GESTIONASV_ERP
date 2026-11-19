import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';

const { fiscalApi } = vi.hoisted(() => ({
  fiscalApi: {
    listActivities: vi.fn(),
    setActivityRenta: vi.fn(),
    setPrimaryActivity: vi.fn(),
    addActivity: vi.fn(),
    deleteActivity: vi.fn(),
    catalog: vi.fn()
  }
}));

vi.mock('#lib/api/fiscal.ts', () => ({ fiscalApi }));

import FiscalActivitiesPanel from './FiscalActivitiesPanel.svelte';

const ACTIVITY = {
  id: 'act-1',
  code: '10712',
  description: 'Fabricación de pan',
  is_primary: true,
  renta_operation_type: null,
  renta_income_type: null
};

beforeEach(() => {
  for (const fn of Object.values(fiscalApi)) fn.mockReset();
});

it('guarda la clasificación de renta sugerida de la actividad', async () => {
  fiscalApi.listActivities
    .mockResolvedValueOnce([ACTIVITY])
    .mockResolvedValue([{ ...ACTIVITY, renta_operation_type: 1, renta_income_type: 4 }]);
  fiscalApi.setActivityRenta.mockResolvedValue({ ...ACTIVITY, renta_operation_type: 1 });
  render(FiscalActivitiesPanel, { canManage: true });

  expect(await screen.findByText(/Renta sugerida al facturar: Sin clasificar/)).toBeInTheDocument();
  const save = screen.getByRole('button', { name: 'Guardar renta' });
  expect(save).toBeDisabled();
  await fireEvent.change(screen.getByLabelText('Tipo de operación (renta)'), {
    target: { value: '1' }
  });
  await fireEvent.change(screen.getByLabelText('Tipo de ingreso (renta)'), {
    target: { value: '4' }
  });
  expect(save).toBeEnabled();
  await fireEvent.click(save);
  expect(fiscalApi.setActivityRenta).toHaveBeenCalledExactlyOnceWith('act-1', 1, 4);
  expect(
    await screen.findByText(/Renta sugerida al facturar: Gravada · Actividades industriales/)
  ).toBeInTheDocument();
});

it('no deja combinar 12 o 13 con otro código', async () => {
  fiscalApi.listActivities.mockResolvedValue([ACTIVITY]);
  render(FiscalActivitiesPanel, { canManage: true });
  await screen.findByText(/Sin clasificar/);
  await fireEvent.change(screen.getByLabelText('Tipo de operación (renta)'), {
    target: { value: '12' }
  });
  await fireEvent.change(screen.getByLabelText('Tipo de ingreso (renta)'), {
    target: { value: '3' }
  });
  expect(screen.getByRole('button', { name: 'Guardar renta' })).toBeDisabled();
});
