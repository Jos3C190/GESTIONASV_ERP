import type { RetaceoCostClass, RetaceoCostDocument } from '$lib/types/retaceo';

export type EditableRetaceoCost = {
  expenseTypeId?: string | null;
  incurredOn?: string;
  key: string;
  id?: string;
  sourcePurchaseOrderExpenseId: string | null;
  classification: RetaceoCostClass;
  title: string;
  description: string;
  amount: string;
  allocations: Record<string, string>;
  documents: RetaceoCostDocument[];
  expanded: boolean;
};
