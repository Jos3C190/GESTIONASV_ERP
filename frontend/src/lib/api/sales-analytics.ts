import { apiFetch } from '#lib/api/client.ts';
import type { MonthGoals, SalesAnalysis } from '#lib/types/sales-analytics.ts';

function query(params: Record<string, string | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) if (value) search.set(key, value);
  const text = search.toString();
  return text ? `?${text}` : '';
}

/** Análisis comercial y metas (`sales_analytics:read`; metas con `sales_goals:manage`). */
export const salesAnalyticsApi = {
  analysis(from: string, to: string, branchId: string | null) {
    return apiFetch<SalesAnalysis>(`/sales/analytics${query({ from, to, branch_id: branchId })}`);
  },
  goals(period: string, branchId: string | null) {
    return apiFetch<MonthGoals>(`/sales/goals/${period}${query({ branch_id: branchId })}`);
  },
  saveGoals(
    period: string,
    goals: { branch_id: string; amount: string | null }[],
    branchId: string | null
  ) {
    return apiFetch<MonthGoals>(`/sales/goals/${period}${query({ branch_id: branchId })}`, {
      method: 'PUT',
      body: JSON.stringify({ goals })
    });
  }
};
