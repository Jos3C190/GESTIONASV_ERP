import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';

const { fiscalApi } = vi.hoisted(() => ({
  fiscalApi: {
    getEmailSettings: vi.fn(),
    saveEmailSettings: vi.fn(),
    deleteEmailSettings: vi.fn(),
    testEmailSettings: vi.fn()
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
import type { EmailSettings } from '#lib/types/fiscal.ts';
import FiscalEmailPanel from './FiscalEmailPanel.svelte';

const EMPTY: EmailSettings = {
  configured: false,
  host: null,
  port: null,
  security: null,
  username: null,
  has_password: false,
  from_address: null,
  from_name: null,
  is_enabled: false,
  last_test_at: null,
  last_test_ok: null,
  last_test_error: null,
  server_fallback: false
};

const SAVED: EmailSettings = {
  ...EMPTY,
  configured: true,
  host: 'smtp.gmail.com',
  port: 587,
  security: 'starttls',
  username: 'facturacion@lorena.com.sv',
  has_password: true,
  from_address: 'facturacion@lorena.com.sv',
  from_name: 'Pastelería Lorena',
  is_enabled: true
};

beforeEach(() => {
  for (const fn of Object.values(fiscalApi)) fn.mockReset();
});

it('guarda la configuración con la contraseña y avisa si no hay respaldo del servidor', async () => {
  fiscalApi.getEmailSettings.mockResolvedValue(EMPTY);
  fiscalApi.saveEmailSettings.mockResolvedValue(SAVED);
  render(FiscalEmailPanel, { canManage: true });
  expect(await screen.findByText('Sin configurar')).toBeInTheDocument();
  expect(screen.getByText(/no se envían por correo/)).toBeInTheDocument();

  await fireEvent.input(screen.getByLabelText('Servidor SMTP'), {
    target: { value: ' smtp.gmail.com ' }
  });
  await fireEvent.input(screen.getByLabelText('Usuario'), {
    target: { value: 'facturacion@lorena.com.sv' }
  });
  await fireEvent.input(screen.getByLabelText('Contraseña'), { target: { value: 'clave-app' } });
  await fireEvent.input(screen.getByLabelText('Correo del remitente'), {
    target: { value: 'facturacion@lorena.com.sv' }
  });
  await fireEvent.click(screen.getByRole('button', { name: 'Guardar' }));
  expect(fiscalApi.saveEmailSettings).toHaveBeenCalledExactlyOnceWith({
    host: 'smtp.gmail.com',
    port: 587,
    security: 'starttls',
    username: 'facturacion@lorena.com.sv',
    password: 'clave-app',
    from_address: 'facturacion@lorena.com.sv',
    from_name: null,
    is_enabled: true
  });
  expect(await screen.findByText(/Se guardó el correo saliente/)).toBeInTheDocument();
  expect(screen.getByText('Activo')).toBeInTheDocument();
  // La contraseña guardada no vuelve: el campo queda vacío con su aviso.
  const passwordField = screen.getByLabelText('Contraseña') as HTMLInputElement;
  expect(passwordField.value).toBe('');
  expect(passwordField.placeholder).toMatch(/Guardada/);
});

it('al cambiar la seguridad propone el puerto que le corresponde', async () => {
  fiscalApi.getEmailSettings.mockResolvedValue(SAVED);
  render(FiscalEmailPanel, { canManage: true });
  const portField = (await screen.findByLabelText('Puerto')) as HTMLInputElement;
  expect(portField.value).toBe('587');
  await fireEvent.change(screen.getByLabelText('Seguridad'), { target: { value: 'ssl' } });
  expect(portField.value).toBe('465');
});

it('envía la prueba y muestra el error del servidor de correo', async () => {
  fiscalApi.getEmailSettings.mockResolvedValueOnce(SAVED).mockResolvedValue({
    ...SAVED,
    last_test_at: '2026-11-17T10:00:00-06:00',
    last_test_ok: false,
    last_test_error: 'El servidor de correo rechazó las credenciales.'
  });
  fiscalApi.testEmailSettings.mockResolvedValue({
    ok: false,
    message: 'El servidor de correo rechazó las credenciales.'
  });
  render(FiscalEmailPanel, { canManage: true });
  expect(
    await screen.findByText('Todavía no se ha probado esta configuración.')
  ).toBeInTheDocument();
  await fireEvent.input(screen.getByLabelText('Enviar la prueba a'), {
    target: { value: 'yo@lorena.com.sv' }
  });
  await fireEvent.click(screen.getByRole('button', { name: 'Enviar correo de prueba' }));
  expect(fiscalApi.testEmailSettings).toHaveBeenCalledWith('yo@lorena.com.sv');
  expect(await screen.findByRole('alert')).toHaveTextContent('rechazó las credenciales');
  expect(await screen.findByText(/Última prueba el 17\/11\/2026/)).toBeInTheDocument();
});

it('muestra el error al guardar y el modo de solo lectura', async () => {
  fiscalApi.getEmailSettings.mockResolvedValue({ ...EMPTY, server_fallback: true });
  fiscalApi.saveEmailSettings.mockRejectedValue(
    new HttpError(
      'email_settings_password_required',
      'Escribe la contraseña del usuario SMTP.',
      422
    )
  );
  const { unmount } = render(FiscalEmailPanel, { canManage: true });
  expect(await screen.findByText(/salen con el correo del servidor/)).toBeInTheDocument();
  await fireEvent.input(screen.getByLabelText('Servidor SMTP'), { target: { value: 'smtp.x.sv' } });
  await fireEvent.input(screen.getByLabelText('Usuario'), { target: { value: 'ventas' } });
  await fireEvent.input(screen.getByLabelText('Correo del remitente'), {
    target: { value: 'ventas@x.sv' }
  });
  await fireEvent.click(screen.getByRole('button', { name: 'Guardar' }));
  await waitFor(() =>
    expect(screen.getByRole('alert')).toHaveTextContent('Escribe la contraseña del usuario SMTP.')
  );
  unmount();

  fiscalApi.getEmailSettings.mockResolvedValue(SAVED);
  render(FiscalEmailPanel, { canManage: false });
  expect(await screen.findByLabelText('Servidor SMTP')).toBeDisabled();
  expect(screen.queryByRole('button', { name: 'Guardar' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Enviar correo de prueba' })).not.toBeInTheDocument();
});

it('muestra el error al cargar', async () => {
  fiscalApi.getEmailSettings.mockRejectedValue(new Error('caído'));
  render(FiscalEmailPanel, { canManage: true });
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'No se pudo cargar el correo saliente.'
  );
});
