import { apiFetch } from '$lib/api/client';
import type {
  Channel,
  Consent,
  ConsentPurpose,
  Incident,
  IncidentInput,
  NoticeTemplate,
  PrivacyNotice,
  RequestAction,
  SubjectRequest,
  SubjectRequestInput,
  UserOption
} from '$lib/types/privacy';

function json(method: string, payload: unknown): RequestInit {
  return { method, body: JSON.stringify(payload) };
}

export const privacyApi = {
  currentNotice() {
    return apiFetch<PrivacyNotice | null>('/privacy/notice');
  },
  notices() {
    return apiFetch<PrivacyNotice[]>('/privacy/notices');
  },
  noticeTemplate() {
    return apiFetch<NoticeTemplate>('/privacy/notice-template');
  },
  publishNotice(payload: { title: string; body: string; covered_elements: string[] }) {
    return apiFetch<PrivacyNotice>('/privacy/notices', json('POST', payload));
  },

  consents(customerId: string) {
    return apiFetch<Consent[]>(`/customers/${customerId}/consents`);
  },
  grantConsent(
    customerId: string,
    payload: { purpose: ConsentPurpose; channel: Channel; notes: string | null }
  ) {
    return apiFetch<Consent>(`/customers/${customerId}/consents`, json('POST', payload));
  },
  revokeConsent(customerId: string, consentId: string, channel: Channel) {
    return apiFetch<Consent>(
      `/customers/${customerId}/consents/${consentId}/revoke`,
      json('POST', { channel })
    );
  },

  requests(scope: 'open' | 'closed' | 'all' = 'open') {
    return apiFetch<SubjectRequest[]>(`/privacy/requests?scope=${scope}`);
  },
  createRequest(payload: SubjectRequestInput) {
    return apiFetch<SubjectRequest>('/privacy/requests', json('POST', payload));
  },
  actOnRequest(
    requestId: string,
    payload: { action: RequestAction; text?: string | null; extension_reason?: string | null }
  ) {
    return apiFetch<SubjectRequest>(
      `/privacy/requests/${requestId}/actions`,
      json('POST', payload)
    );
  },
  assignRequest(requestId: string, assigneeId: string | null) {
    return apiFetch<SubjectRequest>(
      `/privacy/requests/${requestId}/assignee`,
      json('PUT', { assignee_id: assigneeId })
    );
  },
  assigneeOptions() {
    return apiFetch<UserOption[]>('/privacy/assignee-options');
  },
  exportCustomer(customerId: string) {
    return apiFetch<Record<string, unknown>>(`/privacy/customers/${customerId}/export`);
  },
  anonymizeCustomer(customerId: string, requestId: string) {
    return apiFetch<void>(
      `/privacy/customers/${customerId}/anonymize`,
      json('POST', { request_id: requestId })
    );
  },

  incidents() {
    return apiFetch<Incident[]>('/privacy/incidents');
  },
  createIncident(payload: IncidentInput) {
    return apiFetch<Incident>('/privacy/incidents', json('POST', payload));
  },
  updateIncident(incidentId: string, payload: IncidentInput) {
    return apiFetch<Incident>(`/privacy/incidents/${incidentId}`, json('PUT', payload));
  },
  closeIncident(incidentId: string) {
    return apiFetch<Incident>(`/privacy/incidents/${incidentId}/close`, { method: 'POST' });
  }
};
