/** Protección de datos personales (API `/privacy`). */

export type RightType =
  | 'access'
  | 'rectification'
  | 'cancellation'
  | 'opposition'
  | 'portability'
  | 'erasure'
  | 'restriction';
export type RequestStatus =
  | 'received'
  | 'in_progress'
  | 'awaiting_correction'
  | 'extended'
  | 'resolved'
  | 'denied'
  | 'returned'
  | 'archived';
export type RequestAction =
  | 'start'
  | 'request_correction'
  | 'correction_received'
  | 'extend'
  | 'resolve'
  | 'deny'
  | 'return'
  | 'archive';
export type ConsentPurpose = 'marketing' | 'profiling' | 'third_party_sharing';
export type Channel = 'in_person' | 'phone' | 'email' | 'web' | 'written';

export interface NoticeElement {
  key: string;
  description: string;
}

export interface PrivacyNotice {
  id: string;
  version: number;
  title: string;
  body: string;
  covered_elements: string[];
  published_at: string;
  published_by_name: string | null;
}

export interface NoticeTemplate {
  title: string;
  body: string;
  elements: NoticeElement[];
}

export interface Consent {
  id: string;
  customer_id: string;
  purpose: ConsentPurpose;
  channel: Channel;
  notice_version: number;
  granted_at: string;
  granted_by_name: string | null;
  revoked_at: string | null;
  revocation_channel: Channel | null;
  notes: string | null;
}

export interface SubjectRequest {
  id: string;
  code: string;
  customer_id: string | null;
  customer_name: string | null;
  requester_name: string;
  requester_document: string | null;
  response_channel: string;
  right_type: RightType;
  description: string;
  status: RequestStatus;
  received_on: string;
  due_on: string;
  effective_due_on: string;
  correction_due_on: string | null;
  extended_due_on: string | null;
  extension_reason: string | null;
  overdue: boolean;
  assignee_id: string | null;
  assignee_name: string | null;
  resolution: string | null;
  closed_at: string | null;
  created_at: string;
}

export interface SubjectRequestInput {
  customer_id: string | null;
  requester_name: string;
  requester_document: string | null;
  response_channel: string;
  right_type: RightType;
  description: string;
  received_on: string;
  assignee_id: string | null;
}

export interface Incident {
  id: string;
  code: string;
  discovered_at: string;
  occurred_at: string | null;
  notification_deadline: string;
  description: string;
  data_categories: string;
  affected_count: number | null;
  measures: string | null;
  notified_ace_at: string | null;
  ace_reference: string | null;
  notified_prosecutor_at: string | null;
  prosecutor_reference: string | null;
  notified_subjects_at: string | null;
  subjects_reference: string | null;
  subjects_not_required_reason: string | null;
  status: 'open' | 'closed';
  closed_at: string | null;
}

export type IncidentInput = Omit<
  Incident,
  'id' | 'code' | 'notification_deadline' | 'status' | 'closed_at'
>;

export interface UserOption {
  id: string;
  name: string;
}
