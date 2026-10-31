import { afterEach, describe, expect, it } from 'vitest';
import { clearPrivateQueryCache, queryClient } from '$lib/services/query-client';

afterEach(async () => {
  await clearPrivateQueryCache();
});

describe('queryClient tenant isolation', () => {
  it('clears cached private data when the company, branch or session changes', async () => {
    queryClient.setQueryData(['users', 'company-a', 'branch-a'], [{ id: 'user-a' }]);
    queryClient.setQueryData(['dashboard', 'company-a', 'branch-a'], { employees: 10 });

    await clearPrivateQueryCache();

    expect(queryClient.getQueryData(['users', 'company-a', 'branch-a'])).toBeUndefined();
    expect(queryClient.getQueryData(['dashboard', 'company-a', 'branch-a'])).toBeUndefined();
  });

  it('deduplicates concurrent reads for the same scoped key', async () => {
    let calls = 0;
    const queryFn = async () => {
      calls += 1;
      await Promise.resolve();
      return { value: 42 };
    };

    const first = queryClient.fetchQuery({ queryKey: ['roles', 'company-a'], queryFn });
    const second = queryClient.fetchQuery({ queryKey: ['roles', 'company-a'], queryFn });

    await expect(Promise.all([first, second])).resolves.toEqual([{ value: 42 }, { value: 42 }]);
    expect(calls).toBe(1);
  });

  it('aborts an in-flight read when its route scope is cancelled', async () => {
    let aborted = false;
    const pending = queryClient.fetchQuery({
      queryKey: ['audit', 'company-a', 'branch-a'],
      queryFn: ({ signal }) =>
        new Promise<never>((_, reject) => {
          signal.addEventListener('abort', () => {
            aborted = true;
            reject(new DOMException('Aborted', 'AbortError'));
          });
        })
    });

    await queryClient.cancelQueries({ queryKey: ['audit', 'company-a'], exact: false });

    await expect(pending).rejects.toMatchObject({ name: 'AbortError' });
    expect(aborted).toBe(true);
  });
});
