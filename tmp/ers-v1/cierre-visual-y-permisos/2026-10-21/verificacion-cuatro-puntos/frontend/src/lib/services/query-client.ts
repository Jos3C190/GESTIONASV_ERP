type QueryKey = readonly unknown[];

interface QueryEntry {
  key: QueryKey;
  data?: unknown;
  updatedAt: number;
  promise?: Promise<unknown>;
  controller?: AbortController;
}

interface QueryFilters {
  queryKey?: QueryKey;
  exact?: boolean;
}

interface FetchQueryOptions<T> {
  queryKey: QueryKey;
  staleTime?: number;
  queryFn: (context: { signal: AbortSignal }) => Promise<T>;
}

function serialize(key: QueryKey): string {
  return JSON.stringify(key);
}

function matches(entry: QueryEntry, filters: QueryFilters): boolean {
  if (!filters.queryKey) return true;
  if (filters.exact) return serialize(entry.key) === serialize(filters.queryKey);
  return serialize(entry.key.slice(0, filters.queryKey.length)) === serialize(filters.queryKey);
}

/**
 * Small tenant-aware server-state cache used by the ERP's imperative Svelte pages.
 * It deduplicates concurrent reads, supplies AbortSignals and supports scoped invalidation.
 */
class ServerQueryClient {
  private readonly entries = new Map<string, QueryEntry>();
  private readonly maxEntries = 250;

  async fetchQuery<T>(options: FetchQueryOptions<T>): Promise<T> {
    const id = serialize(options.queryKey);
    const existing = this.entries.get(id);
    const staleTime = options.staleTime ?? 30_000;
    if (existing?.data !== undefined && Date.now() - existing.updatedAt < staleTime) {
      return existing.data as T;
    }
    if (existing?.promise) return existing.promise as Promise<T>;

    const controller = new AbortController();
    const entry: QueryEntry = existing ?? {
      key: [...options.queryKey],
      updatedAt: 0
    };
    entry.controller = controller;
    const promise = options
      .queryFn({ signal: controller.signal })
      .then((data) => {
        // A cancelled request may still resolve when a transport ignores AbortSignal.
        // Only the request that still owns this entry is allowed to populate the cache.
        if (entry.controller === controller) {
          entry.data = data;
          entry.updatedAt = Date.now();
        }
        return data;
      })
      .finally(() => {
        if (entry.controller === controller) {
          entry.promise = undefined;
          entry.controller = undefined;
        }
      });
    entry.promise = promise;
    this.entries.set(id, entry);
    this.trim();
    return promise;
  }

  async cancelQueries(filters: QueryFilters = {}): Promise<void> {
    for (const entry of this.entries.values()) {
      if (!matches(entry, filters)) continue;
      entry.controller?.abort();
      entry.promise = undefined;
      entry.controller = undefined;
    }
  }

  async invalidateQueries(filters: QueryFilters = {}): Promise<void> {
    for (const entry of this.entries.values()) {
      if (matches(entry, filters)) entry.updatedAt = 0;
    }
  }

  setQueryData<T>(queryKey: QueryKey, data: T): void {
    this.entries.set(serialize(queryKey), {
      key: [...queryKey],
      data,
      updatedAt: Date.now()
    });
    this.trim();
  }

  getQueryData<T>(queryKey: QueryKey): T | undefined {
    return this.entries.get(serialize(queryKey))?.data as T | undefined;
  }

  clear(): void {
    for (const entry of this.entries.values()) entry.controller?.abort();
    this.entries.clear();
  }

  private trim(): void {
    while (this.entries.size > this.maxEntries) {
      const oldest = this.entries.keys().next().value as string | undefined;
      if (!oldest) return;
      this.entries.get(oldest)?.controller?.abort();
      this.entries.delete(oldest);
    }
  }
}

export const queryClient = new ServerQueryClient();

export async function clearPrivateQueryCache(): Promise<void> {
  await queryClient.cancelQueries();
  queryClient.clear();
}
