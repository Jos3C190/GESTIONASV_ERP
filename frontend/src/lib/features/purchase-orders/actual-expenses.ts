import { apiFetch } from '$lib/api/client';

export interface ActualPurchaseExpense {
  id: string;
  company_id: string;
  purchase_order_id: string;
  expense_type_id: string;
  amount: string;
  incurred_on: string;
  reference: string;
  description: string;
  allocated_amount: string;
  unallocated_amount: string;
  created_at: string | null;
}
export interface ActualExpenseAvailability {
  can_record: boolean;
  reason: string | null;
  closed_retaceo_id: string | null;
  closed_retaceo_code: string | null;
}
export type ActualExpenseInput = Pick<
  ActualPurchaseExpense,
  'expense_type_id' | 'amount' | 'incurred_on' | 'reference' | 'description'
>;
export const actualExpensesApi = {
  availability: (orderId: string) =>
    apiFetch<ActualExpenseAvailability>(`/purchase-orders/${orderId}/actual-expenses/availability`),
  list: (orderId: string) =>
    apiFetch<ActualPurchaseExpense[]>(`/purchase-orders/${orderId}/actual-expenses`),
  create: (orderId: string, payload: ActualExpenseInput) =>
    apiFetch<ActualPurchaseExpense>(`/purchase-orders/${orderId}/actual-expenses`, {
      method: 'POST',
      body: JSON.stringify(payload)
    })
};
