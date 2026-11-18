import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';

const { contingenciesApi, fiscalApi } = vi.hoisted(() => ({
  contingenciesApi: {
    overview: vi.fn(),
    activate: vi.fn(),
    close: vi.fn(),
    sendEvent: vi.fn(),
    saveResponsible: vi.fn()
  },
  fiscalApi: { listEstablishments: vi.fn() }
}));

vi.mock('#lib/api/sales-contingencies.ts', () => ({ contingenciesApi }));
vi.mock('#lib/api/fiscal.ts', () => ({ fiscalApi }));
vi.mock('#lib/api/client.ts', () => ({
  HttpError: class HttpError extends Error {
    constructor(
      readonly code: string,
      message: string,
      readonly status: number
    ) {
      super(message);
    }
  }
}));

import { HttpError } from '#lib/api/client.ts';
import { formatMoment } from '#lib/features/sales/fiscal-labels.ts';
import { confirmation } from '#lib/stores/confirmation.svelte.ts';
import type { ContingencyWindow } from '#lib/types/sales-contingencies.ts';
import ContingencyPanel from './ContingencyPanel.svelte';

const ESTABLISHMENT = {
  id: 'est-1',
  branch_id: 'branch-1',
  branch_name: 'Tienda Centro',
  code: 'M001',
  is_active: true
};

function window(overrides: Partial<ContingencyWindow> = {}): ContingencyWindow {
  return {
    id: 7,
    establishment_code: 'M001',
    branch_name: 'Tienda Centro',
    status: 'ACTIVA',
    contingency_type: 4,
    contingency_label: 'Falla en el suministro de servicio de energía eléctrica del emisor',
    reason: null,
    forced: true,
    started_at: '2026-11-17T16:00:00Z',
    ended_at: null,
    documents: {
      total: 2,
      in_contingency: 2,
      pending_transmission: 0,
      transmitted: 0,
      rejected: 0
    },
    event_status: null,
    event_seal: null,
    event_sealed_at: null,
    event_deadline: null,
    event_overdue: false,
    transmission_deadline: null,
    transmission_overdue: false,
    last_error: null,
    ...overrides
  };
}

const RESPONSIBLE = { name: 'Ana Rivas', document_type: '13', document_number: '01234567-8' };

beforeEach(() => {
  for (const fn of [...Object.values(contingenciesApi), ...Object.values(fiscalApi)]) {
    fn.mockReset();
  }
  fiscalApi.listEstablishments.mockResolvedValue([ESTABLISHMENT]);
  confirmation.reset();
});

it('muestra el estado vacío y activa la contingencia de un establecimiento', async () => {
  contingenciesApi.overview
    .mockResolvedValueOnce({ windows: [], responsible: RESPONSIBLE, active: false })
    .mockResolvedValue({ windows: [window()], responsible: RESPONSIBLE, active: true });
  contingenciesApi.activate.mockResolvedValue(window());
  render(ContingencyPanel, { canOperate: true });

  expect(
    await screen.findByText('Todos los establecimientos emiten con normalidad.')
  ).toBeInTheDocument();
  await fireEvent.click(screen.getByRole('button', { name: 'Activar contingencia' }));
  await fireEvent.change(screen.getByLabelText('Establecimiento'), {
    target: { value: 'est-1' }
  });
  await fireEvent.change(screen.getByLabelText('Tipo de contingencia'), {
    target: { value: '4' }
  });
  await fireEvent.click(screen.getByRole('button', { name: 'Activar' }));

  expect(contingenciesApi.activate).toHaveBeenCalledExactlyOnceWith({
    establishment_id: 'est-1',
    contingency_type: 4,
    reason: null
  });
  expect(await screen.findByText(/Contingencia activa en Tienda Centro/)).toBeInTheDocument();
  expect(await screen.findByText('Tienda Centro (M001)')).toBeInTheDocument();
  expect(screen.getByText('Activa')).toBeInTheDocument();
});

it('cierra con confirmación y reenvía el evento de una ventana cerrada', async () => {
  contingenciesApi.overview
    .mockResolvedValueOnce({ windows: [window()], responsible: RESPONSIBLE, active: true })
    .mockResolvedValue({
      windows: [
        window({
          status: 'CERRADA',
          ended_at: '2026-11-17T18:00:00Z',
          event_deadline: '2026-11-18T18:00:00Z',
          last_error: 'Hacienda no respondió'
        })
      ],
      responsible: RESPONSIBLE,
      active: false
    });
  contingenciesApi.close.mockResolvedValue(window({ status: 'CERRADA' }));
  contingenciesApi.sendEvent.mockResolvedValue(window({ status: 'REPORTADA' }));
  render(ContingencyPanel, { canOperate: true });

  await fireEvent.click(await screen.findByRole('button', { name: 'Cerrar contingencia' }));
  await confirmation.proceed();
  expect(contingenciesApi.close).toHaveBeenCalledExactlyOnceWith(7);
  expect(await screen.findByText(/falta informar el evento\.$/)).toBeInTheDocument();
  expect(
    await screen.findByText(`Evento hasta ${formatMoment('2026-11-18T18:00:00Z')}`)
  ).toBeInTheDocument();
  expect(screen.getByText('Hacienda no respondió')).toBeInTheDocument();

  await fireEvent.click(screen.getByRole('button', { name: 'Informar evento' }));
  expect(contingenciesApi.sendEvent).toHaveBeenCalledExactlyOnceWith(7);
});

it('guarda el responsable y muestra el error de validación', async () => {
  contingenciesApi.overview.mockResolvedValue({ windows: [], responsible: null, active: false });
  contingenciesApi.saveResponsible
    .mockRejectedValueOnce(
      new HttpError(
        'sales_contingency_responsible_invalid',
        'Escribe el nombre del responsable.',
        422
      )
    )
    .mockResolvedValue(RESPONSIBLE);
  render(ContingencyPanel, { canOperate: true });

  expect(
    await screen.findByText(
      /Sin responsable registrado: el evento de contingencia no se puede informar/
    )
  ).toBeInTheDocument();
  await fireEvent.input(screen.getByLabelText('Nombre'), { target: { value: 'Ana Rivas' } });
  await fireEvent.input(screen.getByLabelText('Número de documento'), {
    target: { value: '01234567-8' }
  });
  await fireEvent.click(screen.getByRole('button', { name: 'Guardar responsable' }));
  await waitFor(() =>
    expect(screen.getByRole('alert')).toHaveTextContent('Escribe el nombre del responsable.')
  );
  await fireEvent.click(screen.getByRole('button', { name: 'Guardar responsable' }));
  expect(contingenciesApi.saveResponsible).toHaveBeenLastCalledWith(RESPONSIBLE);
  expect(await screen.findByText(/Se guardó el responsable/)).toBeInTheDocument();
});

it('sin permiso solo consulta, y muestra el error al cargar', async () => {
  contingenciesApi.overview.mockResolvedValueOnce({
    windows: [window()],
    responsible: RESPONSIBLE,
    active: true
  });
  const { unmount } = render(ContingencyPanel, { canOperate: false });
  expect(await screen.findByText('Tienda Centro (M001)')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Activar contingencia' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Cerrar contingencia' })).not.toBeInTheDocument();
  expect(screen.getByLabelText('Nombre')).toBeDisabled();
  unmount();

  contingenciesApi.overview.mockRejectedValue(new Error('caído'));
  render(ContingencyPanel, { canOperate: true });
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'No se pudo cargar la contingencia de la empresa.'
  );
});

it('formatea fecha y hora de El Salvador', () => {
  expect(formatMoment('2026-11-17T16:05:00Z')).toBe('17/11/2026 10:05');
  expect(formatMoment(null)).toBe('—');
});
