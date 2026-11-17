import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, expect, it, vi } from 'vitest';
import { permissions } from '#lib/stores/permissions.svelte.ts';
import type { FiscalDocument, FiscalEmail } from '#lib/types/sales-invoices.ts';
import FiscalDocumentEmails from './FiscalDocumentEmails.svelte';

const { salesInvoicesApi } = vi.hoisted(() => ({
  salesInvoicesApi: { emails: vi.fn(), sendEmail: vi.fn() }
}));
vi.mock('#lib/api/sales-invoices.ts', () => ({ salesInvoicesApi }));

const DOCUMENT = {
  id: 'doc-1',
  status: 'simulated',
  customer_email: 'cliente@example.com'
} as FiscalDocument;

function email(values: Partial<FiscalEmail> = {}): FiscalEmail {
  return {
    id: 'mail-1',
    document_id: 'doc-1',
    recipients: ['cliente@example.com'],
    origin: 'auto',
    status: 'sent',
    attempts: 1,
    error_code: null,
    error_message: null,
    requested_by_name: null,
    sent_at: '2026-11-17T10:00:00-06:00',
    created_at: '2026-11-17T10:00:00-06:00',
    ...values
  };
}

beforeEach(() => {
  permissions.set(['sales_invoices:read', 'sales_invoices:issue'], false);
  salesInvoicesApi.emails.mockReset();
  salesInvoicesApi.sendEmail.mockReset();
});

it('propone el correo del cliente y envía a varios destinatarios', async () => {
  salesInvoicesApi.emails
    .mockResolvedValueOnce({ enabled: true, customer_email: 'cliente@example.com', items: [] })
    .mockResolvedValue({
      enabled: true,
      customer_email: 'cliente@example.com',
      items: [email({ origin: 'manual', status: 'sent', requested_by_name: 'Ana López' })]
    });
  salesInvoicesApi.sendEmail.mockResolvedValue(
    email({
      origin: 'manual',
      status: 'pending',
      recipients: ['cliente@example.com', 'conta@x.sv']
    })
  );
  render(FiscalDocumentEmails, { document: DOCUMENT });
  const input = (await screen.findByLabelText('Enviar a')) as HTMLInputElement;
  expect(input.value).toBe('cliente@example.com');
  expect(screen.getByText('Todavía no se ha enviado por correo.')).toBeInTheDocument();
  await fireEvent.input(input, { target: { value: 'cliente@example.com; conta@x.sv' } });
  await fireEvent.click(screen.getByRole('button', { name: 'Enviar por correo' }));
  expect(salesInvoicesApi.sendEmail).toHaveBeenCalledExactlyOnceWith('doc-1', [
    'cliente@example.com',
    'conta@x.sv'
  ]);
  expect(
    await screen.findByText('Se enviará a cliente@example.com, conta@x.sv.')
  ).toBeInTheDocument();
  expect(await screen.findByText(/Enviado por Ana López/)).toBeInTheDocument();
  expect(screen.getByText('Enviado')).toBeInTheDocument();
});

it('muestra el historial con el envío automático y el error de uno fallido', async () => {
  salesInvoicesApi.emails.mockResolvedValue({
    enabled: true,
    customer_email: null,
    items: [
      email(),
      email({
        id: 'mail-2',
        origin: 'manual',
        status: 'failed',
        requested_by_name: 'Ana López',
        error_message: 'El servidor de correo rechazó los destinatarios.'
      })
    ]
  });
  render(FiscalDocumentEmails, { document: DOCUMENT });
  expect(await screen.findByText(/Automático al emitirse/)).toBeInTheDocument();
  expect(screen.getByText('No se envió')).toBeInTheDocument();
  expect(screen.getByText('El servidor de correo rechazó los destinatarios.')).toBeInTheDocument();
});

it('sigue el envío pendiente hasta que se entrega', async () => {
  salesInvoicesApi.emails
    .mockResolvedValueOnce({
      enabled: true,
      customer_email: null,
      items: [email({ status: 'pending', sent_at: null })]
    })
    .mockResolvedValue({ enabled: true, customer_email: null, items: [email()] });
  render(FiscalDocumentEmails, { document: DOCUMENT, pollMs: 10 });
  expect(await screen.findByText('Enviando')).toBeInTheDocument();
  expect(await screen.findByText('Enviado')).toBeInTheDocument();
  await waitFor(() => expect(salesInvoicesApi.emails).toHaveBeenCalledTimes(2));
});

it('avisa si el servidor no envía correos y oculta el formulario a quien solo consulta', async () => {
  salesInvoicesApi.emails.mockResolvedValue({ enabled: false, customer_email: null, items: [] });
  const { unmount } = render(FiscalDocumentEmails, { document: DOCUMENT });
  expect(await screen.findByText(/no tiene configurado su correo saliente/)).toBeInTheDocument();
  unmount();
  permissions.set(['sales_invoices:read'], false);
  salesInvoicesApi.emails.mockResolvedValue({ enabled: true, customer_email: null, items: [] });
  render(FiscalDocumentEmails, { document: DOCUMENT });
  expect(await screen.findByText('Todavía no se ha enviado por correo.')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Enviar por correo' })).not.toBeInTheDocument();
});

it('pide un correo y muestra el error del servidor al enviar', async () => {
  salesInvoicesApi.emails.mockResolvedValue({ enabled: true, customer_email: null, items: [] });
  salesInvoicesApi.sendEmail.mockRejectedValue(new Error('caído'));
  render(FiscalDocumentEmails, { document: DOCUMENT });
  await fireEvent.click(await screen.findByRole('button', { name: 'Enviar por correo' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Escribe al menos un correo.');
  await fireEvent.input(screen.getByLabelText('Enviar a'), { target: { value: 'a@b.sv' } });
  await fireEvent.click(screen.getByRole('button', { name: 'Enviar por correo' }));
  await waitFor(() =>
    expect(screen.getByRole('alert')).toHaveTextContent('No se pudo enviar el correo.')
  );
});
