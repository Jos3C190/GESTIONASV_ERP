import { apiFetch } from '#lib/api/client.ts';
import type { PromotionInput, SalesPromotion } from '#lib/types/sales-promotions.ts';

export const salesPromotionsApi = {
  list(params: { branch_id?: string | null; include_ended?: boolean } = {}) {
    const query = new URLSearchParams();
    if (params.branch_id) query.set('branch_id', params.branch_id);
    if (params.include_ended) query.set('include_ended', 'true');
    const suffix = query.toString() ? `?${query.toString()}` : '';
    return apiFetch<SalesPromotion[]>(`/sales/promotions${suffix}`);
  },
  create(input: PromotionInput) {
    return apiFetch<SalesPromotion>('/sales/promotions', {
      method: 'POST',
      body: JSON.stringify(input)
    });
  },
  end(id: string) {
    return apiFetch<SalesPromotion>(`/sales/promotions/${id}/end`, { method: 'POST' });
  }
};
