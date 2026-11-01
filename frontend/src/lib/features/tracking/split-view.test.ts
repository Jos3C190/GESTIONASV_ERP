import { describe, expect, it } from 'vitest';
import { assignPane, initialAssignments, reconcileAssignments } from './split-view';

describe('split tracking assignments', () => {
  it('prioritizes the selected unit and never invents extra vehicles', () => {
    expect(initialAssignments(['a', 'b', 'a', 'c'], 'b')).toEqual(['b', 'a', 'c', null]);
    expect(initialAssignments([], null)).toEqual([null, null, null, null]);
  });

  it('removes duplicate, missing and unauthorized keys', () => {
    expect(reconcileAssignments(['a', 'a', 'hidden', 'b'], ['a', 'b'])).toEqual([
      'a',
      null,
      null,
      'b'
    ]);
  });

  it('refuses duplicates in visible panes and unknown devices', () => {
    const assigned = ['a', 'b', null, null];
    expect(assignPane(assigned, 1, 'a', ['a', 'b'])).toBe(assigned);
    expect(assignPane(assigned, 1, 'unknown', ['a', 'b'])).toBe(assigned);
    expect(assignPane(assigned, 4, 'a', ['a', 'b'])).toBe(assigned);
  });

  it('lets a visible pane reuse a hidden pane vehicle without duplicating it', () => {
    expect(assignPane(['a', 'b', 'c', 'd'], 0, 'c', ['a', 'b', 'c', 'd'], 2)).toEqual([
      'c',
      'b',
      null,
      'd'
    ]);
  });
});
