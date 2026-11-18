import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';

const { fiscalApi } = vi.hoisted(() => ({
  fiscalApi: {
    getHaciendaCredentials: vi.fn(),
    saveHaciendaCredentials: vi.fn(),
    deleteHaciendaCredentials: vi.fn(),
    testHaciendaCredentials: vi.fn()
  }
}));

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
import type { HaciendaCredentials } from '#lib/types/fiscal.ts';
import FiscalHaciendaPanel from './FiscalHaciendaPanel.svelte';

const EMPTY: HaciendaCredentials = {
  configured: false,
  certificate_nit: null,
  certificate_sha256: null,
  last_test_at: null,
  last_test_ok: null,
  last_test_error: null,
  updated_at: null
};

const SAVED: HaciendaCredentials = {
  ...EMPTY,
  configured: true,
  certificate_nit: '06142803901121',
  certificate_sha256: 'a'.repeat(64)
};

beforeEach(() => {
  for (const fn of Object.values(fiscalApi)) fn.mockReset();
});

it('sube el certificado en base64 con las contraseñas y no las vuelve a mostrar', async () => {
  fiscalApi.getHaciendaCredentials.mockResolvedValue(EMPTY);
  fiscalApi.saveHaciendaCredentials.mockResolvedValue(SAVED);
  render(FiscalHaciendaPanel, { canManage: true });
  expect(await screen.findByText('Sin cargar')).toBeInTheDocument();

  const file = new File(['<CertificadoMH/>'], '06142803901121.crt', { type: 'application/xml' });
  await fireEvent.change(screen.getByLabelText(/Certificado/), { target: { files: [file] } });
  expect(await screen.findByText('Seleccionado: 06142803901121.crt')).toBeInTheDocument();
  await fireEvent.input(screen.getByLabelText('Contraseña de la API'), {
    target: { value: 'api' }
  });
  await fireEvent.input(screen.getByLabelText('Contraseña de la llave privada'), {
    target: { value: 'privada' }
  });
  await fireEvent.click(screen.getByRole('button', { name: 'Guardar' }));
  expect(fiscalApi.saveHaciendaCredentials).toHaveBeenCalledExactlyOnceWith({
    api_password: 'api',
    private_key_password: 'privada',
    certificate_base64: btoa('<CertificadoMH/>')
  });
  expect(await screen.findByText(/Se guardaron las credenciales/)).toBeInTheDocument();
  expect(screen.getByText('Sin probar')).toBeInTheDocument();
  expect(screen.getByText('06142803901121')).toBeInTheDocument();
  expect((screen.getByLabelText('Contraseña de la API') as HTMLInputElement).value).toBe('');
});

it('prueba la conexión y muestra cada parte del resultado', async () => {
  fiscalApi.getHaciendaCredentials.mockResolvedValueOnce(SAVED).mockResolvedValue({
    ...SAVED,
    last_test_at: '2026-11-17T10:00:00-06:00',
    last_test_ok: false,
    last_test_error: 'Hacienda rechazó la autenticación'
  });
  fiscalApi.testHaciendaCredentials.mockResolvedValue({
    ok: false,
    authentication_ok: false,
    authentication_message: 'Hacienda rechazó la autenticación',
    signature_ok: true,
    signature_message: 'El firmador firmó con el certificado del emisor'
  });
  render(FiscalHaciendaPanel, { canManage: true });
  await fireEvent.click(await screen.findByRole('button', { name: 'Probar conexión' }));
  expect(await screen.findByText(/Autenticación: Hacienda rechazó/)).toBeInTheDocument();
  expect(screen.getByText(/Firma: El firmador firmó/)).toBeInTheDocument();
  expect(await screen.findByText(/Última prueba el 17\/11\/2026/)).toBeInTheDocument();
});

it('muestra el error de validación y el modo de solo lectura', async () => {
  fiscalApi.getHaciendaCredentials.mockResolvedValue(EMPTY);
  fiscalApi.saveHaciendaCredentials.mockRejectedValue(
    new HttpError(
      'hacienda_certificate_nit_mismatch',
      'El certificado es del NIT 06140101900011, no del de la empresa.',
      422
    )
  );
  const { unmount } = render(FiscalHaciendaPanel, { canManage: true });
  await fireEvent.click(await screen.findByRole('button', { name: 'Guardar' }));
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('no del de la empresa'));
  unmount();

  fiscalApi.getHaciendaCredentials.mockResolvedValue({ ...SAVED, last_test_ok: true });
  render(FiscalHaciendaPanel, { canManage: false });
  expect(await screen.findByText('Probadas')).toBeInTheDocument();
  expect(screen.getByLabelText('Contraseña de la API')).toBeDisabled();
  expect(screen.queryByRole('button', { name: 'Probar conexión' })).not.toBeInTheDocument();
});

it('muestra el error al cargar', async () => {
  fiscalApi.getHaciendaCredentials.mockRejectedValue(new Error('caído'));
  render(FiscalHaciendaPanel, { canManage: true });
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'No se pudieron cargar las credenciales de Hacienda.'
  );
});
