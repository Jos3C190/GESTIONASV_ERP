import type { DocumentUploadTicket } from '$lib/api/client';
import type { QualityIssue } from './image-prep';

export type CaptureSide = 'front' | 'back';
export type CaptureStatus =
  'draft' | 'pending' | 'processing' | 'ready' | 'failed' | 'confirmed' | 'cancelled' | 'expired';
export type CaptureValues = Record<string, string | null>;

export interface CaptureIssue {
  code: string;
  severity: 'error' | 'mismatch' | 'warning';
  field: string;
  message: string;
}

export interface CaptureSideState {
  document_id: string | null;
  status: string | null;
  extracted: boolean;
}

export interface CaptureState {
  id: string;
  status: CaptureStatus;
  failure_code: string | null;
  extraction_available: boolean;
  front: CaptureSideState;
  back: CaptureSideState;
  values: CaptureValues;
  issues: CaptureIssue[];
  /** Fields a confirmation would copy to the record that owns the document. */
  fills?: readonly string[];
}

export interface CaptureCheck {
  issues: CaptureIssue[];
  fills?: readonly string[];
}

export interface CaptureField {
  label: string;
  hint?: string;
  /** Takes the whole row of the form. */
  wide?: boolean;
  /** Only digits: a phone can show its number keyboard. */
  numeric?: boolean;
}

export interface CaptureFieldGroup {
  title: string;
  fields: string[];
}

/** What differs between one guided capture and another: the document, its rules, its API. */
export interface CaptureRules {
  groups: CaptureFieldGroup[];
  /** Fields each side should yield; a miss suggests a bad photo. */
  expected: Record<CaptureSide, readonly string[]>;
  /** Codes meaning the model returned something, but not a usable value. */
  unreadableCodes: ReadonlySet<string>;
  missingPhotos: string;
  mismatchBlocked: string;
  /** What to say when an issue cannot be solved by fixing a typo. */
  blockingCodes?: Readonly<Record<string, string>>;
}

export interface CaptureApi<R> {
  open(): Promise<CaptureState>;
  get(captureId: string): Promise<CaptureState>;
  startUpload(
    captureId: string,
    side: CaptureSide,
    data: { content_type: string; size_bytes: number; checksum_sha256: string }
  ): Promise<DocumentUploadTicket>;
  completeUpload(captureId: string, side: CaptureSide): Promise<CaptureState>;
  preview(captureId: string, side: CaptureSide): Promise<{ url: string; expires_at: string }>;
  check(captureId: string, values: CaptureValues): Promise<CaptureCheck>;
  confirm(
    captureId: string,
    data: {
      values: CaptureValues;
      acknowledged_warnings: string[];
      override_reason?: string | null;
    }
  ): Promise<R>;
  cancel(captureId: string): Promise<void>;
}

export interface CaptureConfig<R> extends CaptureRules {
  dialogTitle: string;
  /** Name of the document on its own, for titles. */
  title: string;
  /** With its article, to build sentences: "la licencia". */
  documentName: string;
  filePrefix: string;
  /**
   * Checks a side's design would trip by itself, such as glare on a large blank area.
   * A real reflection over the text still shows up as a value the model could not read.
   */
  ignoredQuality?: Partial<Record<CaptureSide, readonly QualityIssue[]>>;
  fields: Record<string, CaptureField>;
  /** Permission that may confirm a mismatch; null when none can. */
  overridePermission: string | null;
  mismatchStop: string;
  acknowledge: string;
  confirmLabel: string;
  confirmError: string;
  fillNote?: string;
  api: CaptureApi<R>;
}
