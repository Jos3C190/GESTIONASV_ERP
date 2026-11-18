/** Contingencia de facturación por establecimiento (bloque V4a). */

export type ContingencyStatus = 'ACTIVA' | 'CERRADA' | 'REPORTADA' | 'COMPLETADA';

export interface ContingencyWindow {
  id: number;
  establishment_code: string | null;
  branch_name: string | null;
  status: ContingencyStatus;
  contingency_type: number;
  contingency_label: string;
  reason: string | null;
  forced: boolean;
  started_at: string;
  ended_at: string | null;
  documents: {
    total: number;
    in_contingency: number;
    pending_transmission: number;
    transmitted: number;
    rejected: number;
  };
  event_status: string | null;
  event_seal: string | null;
  event_sealed_at: string | null;
  event_deadline: string | null;
  event_overdue: boolean;
  transmission_deadline: string | null;
  transmission_overdue: boolean;
  last_error: string | null;
}

export interface ContingencyResponsible {
  name: string;
  document_type: string;
  document_number: string;
}

export interface ContingencyOverview {
  windows: ContingencyWindow[];
  responsible: ContingencyResponsible | null;
  active: boolean;
}

export interface ContingencyActivation {
  establishment_id: string;
  contingency_type: number;
  reason: string | null;
}
