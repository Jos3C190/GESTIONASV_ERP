export type AsyncCollectionState = 'loading' | 'error' | 'empty' | 'partial' | 'loaded';

export function getAsyncCollectionState<T>(input: {
  loading: boolean;
  error: string | null;
  items: readonly T[];
}): AsyncCollectionState {
  if (input.loading) return 'loading';
  if (input.error && input.items.length === 0) return 'error';
  if (input.error) return 'partial';
  return input.items.length === 0 ? 'empty' : 'loaded';
}
