import { describe, expect, it } from 'vitest';
import { buildUserListQuery } from './list-query';

describe('buildUserListQuery', () => {
  it('preserva paginación, filtro y contexto operativo', () => {
    const query = new URLSearchParams(buildUserListQuery(
      { page: 2, size: 10, search: 'ana', status: 'inactive' },
      { companyId: 'company-1', branchId: 'branch-2' }
    ));
    expect(Object.fromEntries(query)).toEqual({
      page: '2', size: '10', search: 'ana', status: 'inactive',
      company_id: 'company-1', branch_id: 'branch-2'
    });
  });

  it('omite filtros vacíos sin introducir valores inválidos', () => {
    expect(buildUserListQuery({}, {})).toBe('');
  });
});
