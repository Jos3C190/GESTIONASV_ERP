import { describe, expect, it } from 'vitest';
import { getAsyncCollectionState } from '../../src/lib/features/inventory/async-collection-state';

describe('getAsyncCollectionState', () => {
  it('does not treat an unreadable collection as empty', () => {
    expect(getAsyncCollectionState({ loading: false, error: 'Fallo', items: [] })).toBe('error');
  });

  it('distinguishes an empty successful result from a failed request', () => {
    expect(getAsyncCollectionState({ loading: false, error: null, items: [] })).toBe('empty');
  });

  it('marks partial collections when some requests failed', () => {
    expect(getAsyncCollectionState({ loading: false, error: 'Parcial', items: ['HU-1'] })).toBe(
      'partial'
    );
  });

  it('keeps loading state while a request is pending', () => {
    expect(getAsyncCollectionState({ loading: true, error: null, items: [] })).toBe('loading');
  });
});
