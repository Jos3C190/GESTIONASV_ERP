import { apiFetch } from '#lib/api/client.ts';
import type {
  ContingencyActivation,
  ContingencyOverview,
  ContingencyResponsible,
  ContingencyWindow
} from '#lib/types/sales-contingencies.ts';

const BASE = '/sales/contingencies';

function post<T>(path: string, body?: unknown) {
  return apiFetch<T>(path, {
    method: 'POST',
    body: body === undefined ? undefined : JSON.stringify(body)
  });
}

export const contingenciesApi = {
  overview() {
    return apiFetch<ContingencyOverview>(BASE);
  },
  activate(payload: ContingencyActivation) {
    return post<ContingencyWindow>(BASE, payload);
  },
  close(windowId: number) {
    return post<ContingencyWindow>(`${BASE}/${windowId}/close`);
  },
  sendEvent(windowId: number) {
    return post<ContingencyWindow>(`${BASE}/${windowId}/event`);
  },
  saveResponsible(payload: ContingencyResponsible) {
    return apiFetch<ContingencyResponsible>(`${BASE}/responsible`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
  }
};
