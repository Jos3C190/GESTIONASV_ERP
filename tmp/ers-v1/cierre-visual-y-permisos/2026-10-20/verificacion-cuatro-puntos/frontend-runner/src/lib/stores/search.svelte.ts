/**
 * Shared search store — the header has a single search bar that feeds
 * whatever view is active. Each view reads `searchQuery` and reacts via $effect.
 */
function createSearchStore() {
  let query = $state('');
  let timer: ReturnType<typeof setTimeout> | null = null;

  return {
    get query(): string {
      return query;
    },
    set(v: string) {
      query = v;
    },
    /** Debounced setter — views that need debounce can use this. */
    setDebounced(v: string, ms = 300) {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => { query = v; }, ms);
    },
    clear() {
      query = '';
      if (timer) clearTimeout(timer);
    }
  };
}

export const search = createSearchStore();