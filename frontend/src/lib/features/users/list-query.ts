export type UserStatusFilter = 'active' | 'inactive' | 'superuser';

export function buildUserListQuery(
  params: { page?: number; size?: number; search?: string; status?: UserStatusFilter },
  context: { companyId?: string | null; branchId?: string | null }
): string {
  const query = new URLSearchParams();
  if (params.page) query.set('page', String(params.page));
  if (params.size) query.set('size', String(params.size));
  if (params.search) query.set('search', params.search);
  if (params.status) query.set('status', params.status);
  if (context.companyId) query.set('company_id', context.companyId);
  if (context.branchId) query.set('branch_id', context.branchId);
  return query.toString();
}
