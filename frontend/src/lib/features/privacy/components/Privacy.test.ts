import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { privacyApi } = vi.hoisted(() => ({
  privacyApi: {
    notices: vi.fn(),
    noticeTemplate: vi.fn(),
    publishNotice: vi.fn(),
    consents: vi.fn(),
    grantConsent: vi.fn(),
    revokeConsent: vi.fn(),
    requests: vi.fn(),
    assigneeOptions: vi.fn(),
    createRequest: vi.fn(),
    actOnRequest: vi.fn(),
    assignRequest: vi.fn(),
    exportCustomer: vi.fn(),
    anonymizeCustomer: vi.fn(),
    incidents: vi.fn(),
    createIncident: vi.fn(),
    updateIncident: vi.fn(),
    closeIncident: vi.fn()
  }
}));

vi.mock('#lib/api/privacy.ts', () => ({ privacyApi }));
vi.mock('#lib/api/customers.ts', () => ({ customersApi: { list: vi.fn() } }));
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
import { fromLocalInput, todayInElSalvador, toLocalInput } from '#lib/features/privacy/labels.ts';
import { permissions } from '#lib/stores/permissions.svelte.ts';
import type { Consent, Incident, SubjectRequest } from '#lib/types/privacy.ts';
import CustomerConsentsPanel from './CustomerConsentsPanel.svelte';
import PrivacyIncidentsPanel from './PrivacyIncidentsPanel.svelte';
import PrivacyNoticePanel from './PrivacyNoticePanel.svelte';
import PrivacyRequestsPanel from './PrivacyRequestsPanel.svelte';

const ELEMENTS = [
  { key: 'controller_address', description: 'Identidad y domicilio del responsable' },
  { key: 'purposes', description: 'Finalidades del tratamiento' }
];

const request: SubjectRequest = {
  id: 'request-1',
  code: 'SOL-00001',
  customer_id: 'customer-1',
  customer_name: 'Cliente ficticio',
  requester_name: 'Ana Pérez',
  requester_document: null,
  response_channel: 'ana@example.com',
  right_type: 'access',
  description: 'Quiere saber qué datos suyos se guardan.',
  status: 'received',
  received_on: '2026-11-02',
  due_on: '2026-11-30',
  effective_due_on: '2026-11-30',
  correction_due_on: null,
  extended_due_on: null,
  extension_reason: null,
  overdue: false,
  assignee_id: null,
  assignee_name: null,
  resolution: null,
  closed_at: null,
  created_at: '2026-11-02T15:00:00Z'
};

const incident: Incident = {
  id: 'incident-1',
  code: 'INC-00001',
  discovered_at: '2026-11-10T15:00:00Z',
  occurred_at: null,
  notification_deadline: '2026-11-13T15:00:00Z',
  description: 'Se envió una lista de clientes al correo equivocado.',
  data_categories: 'Nombres y teléfonos',
  affected_count: 12,
  measures: null,
  notified_ace_at: null,
  ace_reference: null,
  notified_prosecutor_at: null,
  prosecutor_reference: null,
  notified_subjects_at: null,
  subjects_reference: null,
  subjects_not_required_reason: null,
  status: 'open',
  closed_at: null
};

const consent: Consent = {
  id: 'consent-1',
  customer_id: 'customer-1',
  purpose: 'marketing',
  channel: 'in_person',
  notice_version: 1,
  granted_at: '2026-11-01T15:00:00Z',
  granted_by_name: 'Vendedora',
  revoked_at: null,
  revocation_channel: null,
  notes: null
};

beforeEach(() => {
  for (const fn of Object.values(privacyApi)) fn.mockReset();
  permissions.set(['privacy:read', 'privacy:manage', 'sales_customers:manage'], false);
  privacyApi.assigneeOptions.mockResolvedValue([{ id: 'user-1', name: 'Encargada' }]);
});

describe('privacy labels', () => {
  it('converts datetime-local values using El Salvador time', () => {
    expect(fromLocalInput('2026-11-10T09:00')).toBe('2026-11-10T15:00:00.000Z');
    expect(toLocalInput('2026-11-10T15:00:00Z')).toBe('2026-11-10T09:00');
    expect(fromLocalInput('')).toBeNull();
    expect(todayInElSalvador(new Date('2026-11-17T03:00:00Z'))).toBe('2026-11-16');
  });
});

describe('PrivacyNoticePanel', () => {
  it('shows the empty state and only publishes after every element is confirmed', async () => {
    privacyApi.notices.mockResolvedValue([]);
    privacyApi.noticeTemplate.mockResolvedValue({
      title: 'Aviso de privacidad',
      body: 'Texto del aviso '.repeat(20),
      elements: ELEMENTS
    });
    privacyApi.publishNotice.mockResolvedValue({});
    render(PrivacyNoticePanel, { canManage: true });

    expect(await screen.findByText('Aún no hay aviso de privacidad publicado')).toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: 'Redactar el aviso' }));
    const publish = await screen.findByRole('button', { name: 'Publicar' });
    expect(publish).toBeDisabled();

    for (const element of ELEMENTS) {
      await fireEvent.click(screen.getByLabelText(element.description));
    }
    expect(publish).toBeEnabled();
    await fireEvent.click(publish);
    expect(privacyApi.publishNotice).toHaveBeenCalledWith(
      expect.objectContaining({ covered_elements: ['controller_address', 'purposes'] })
    );
  });

  it('shows a readable error when the notice cannot load', async () => {
    privacyApi.notices.mockRejectedValue(new HttpError('forbidden', 'Sin permiso.', 403));
    render(PrivacyNoticePanel, { canManage: false });
    expect(await screen.findByRole('alert')).toHaveTextContent('Sin permiso.');
  });
});

describe('PrivacyRequestsPanel', () => {
  it('denies a request with a motivated text', async () => {
    privacyApi.requests.mockResolvedValue([request]);
    privacyApi.actOnRequest.mockResolvedValue({ ...request, status: 'denied' });
    render(PrivacyRequestsPanel, { canManage: true });

    await fireEvent.click(await screen.findByRole('button', { name: /SOL-00001/ }));
    await fireEvent.click(screen.getByRole('button', { name: 'Denegar' }));
    await fireEvent.input(screen.getByLabelText('Motivo de la negativa (resolución motivada)'), {
      target: { value: 'No se acreditó la identidad del titular.' }
    });
    const buttons = screen.getAllByRole('button', { name: 'Denegar' });
    await fireEvent.click(buttons.at(-1)!);

    expect(privacyApi.actOnRequest).toHaveBeenCalledWith('request-1', {
      action: 'deny',
      text: 'No se acreditó la identidad del titular.',
      extension_reason: null
    });
  });

  it('sends the extension reason in its own field', async () => {
    privacyApi.requests.mockResolvedValue([request]);
    privacyApi.actOnRequest.mockResolvedValue({ ...request, status: 'extended' });
    render(PrivacyRequestsPanel, { canManage: true });

    await fireEvent.click(await screen.findByRole('button', { name: /SOL-00001/ }));
    await fireEvent.click(screen.getByRole('button', { name: 'Prorrogar 20 días hábiles' }));
    await fireEvent.input(screen.getByLabelText('Causa justificada de la prórroga'), {
      target: { value: 'Hay que revisar archivos de varias sucursales.' }
    });
    const buttons = screen.getAllByRole('button', { name: 'Prorrogar 20 días hábiles' });
    await fireEvent.click(buttons.at(-1)!);

    expect(privacyApi.actOnRequest).toHaveBeenCalledWith('request-1', {
      action: 'extend',
      text: null,
      extension_reason: 'Hay que revisar archivos de varias sucursales.'
    });
  });

  it('shows the empty state and hides actions without manage', async () => {
    privacyApi.requests.mockResolvedValue([]);
    render(PrivacyRequestsPanel, { canManage: false });
    expect(await screen.findByText('No hay solicitudes en trámite.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Registrar solicitud' })).not.toBeInTheDocument();
  });
});

describe('PrivacyIncidentsPanel', () => {
  it('blocks closing while notifications are missing', async () => {
    privacyApi.incidents.mockResolvedValue([incident]);
    render(PrivacyIncidentsPanel, { canManage: true });

    expect(await screen.findByText(/Falta notificar a:/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cerrar' })).toBeDisabled();
  });

  it('allows closing once every notification is recorded', async () => {
    privacyApi.incidents.mockResolvedValue([
      {
        ...incident,
        notified_ace_at: '2026-11-11T15:00:00Z',
        notified_prosecutor_at: '2026-11-11T16:00:00Z',
        subjects_not_required_reason: 'Los datos estaban cifrados.'
      }
    ]);
    render(PrivacyIncidentsPanel, { canManage: true });
    expect(await screen.findByRole('button', { name: 'Cerrar' })).toBeEnabled();
    expect(screen.queryByText(/Falta notificar a:/)).not.toBeInTheDocument();
  });
});

describe('CustomerConsentsPanel', () => {
  it('grants only purposes that are not already active', async () => {
    privacyApi.consents.mockResolvedValue([consent]);
    privacyApi.grantConsent.mockResolvedValue({});
    render(CustomerConsentsPanel, { customerId: 'customer-1', canManage: true });

    expect(await screen.findByText('Vigente')).toBeInTheDocument();
    await fireEvent.click(screen.getByRole('button', { name: 'Registrar consentimiento' }));
    const purpose = screen.getByLabelText('Uso autorizado') as HTMLSelectElement;
    expect(Array.from(purpose.options).map((o) => o.value)).toEqual([
      'profiling',
      'third_party_sharing'
    ]);

    await fireEvent.click(screen.getByRole('button', { name: 'Registrar' }));
    expect(privacyApi.grantConsent).toHaveBeenCalledWith('customer-1', {
      purpose: 'profiling',
      channel: 'in_person',
      notes: null
    });
  });

  it('revokes with the channel the customer used', async () => {
    privacyApi.consents.mockResolvedValue([consent]);
    privacyApi.revokeConsent.mockResolvedValue({});
    render(CustomerConsentsPanel, { customerId: 'customer-1', canManage: true });

    await fireEvent.click(await screen.findByRole('button', { name: 'Revocar' }));
    const channel = screen.getByLabelText('Cómo lo pidió') as HTMLSelectElement;
    await fireEvent.change(channel, { target: { value: 'email' } });
    expect(channel.value).toBe('email');
    const buttons = screen.getAllByRole('button', { name: 'Revocar' });
    await fireEvent.click(buttons.at(-1)!);
    expect(privacyApi.revokeConsent).toHaveBeenCalledWith('customer-1', 'consent-1', 'email');
  });

  it('explains the empty state without manage actions', async () => {
    privacyApi.consents.mockResolvedValue([]);
    render(CustomerConsentsPanel, { customerId: 'customer-1', canManage: false });
    expect(await screen.findByText(/no ha dado consentimientos/)).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Registrar consentimiento' })
    ).not.toBeInTheDocument();
  });
});
