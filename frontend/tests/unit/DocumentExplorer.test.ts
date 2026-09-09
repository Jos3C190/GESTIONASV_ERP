import { describe, expect, it } from 'vitest';
import {
  defaultExplorerQuery,
  parseExplorerQuery,
  serializeExplorerQuery
} from '../../src/lib/features/documents/explorer/query';
import {
  activationForClick,
  documentOpenAction,
  keyboardAction,
  canExplorerAction
} from '../../src/lib/features/documents/explorer/interaction';

describe('document explorer query', () => {
  it('parses and serializes the URL contract', () => {
    const query = parseExplorerQuery(
      new URL(
        'http://localhost/documents/general?folder=f1&search=contrato&sort=updated&view=grid&page=2'
      )
    );
    expect(query).toMatchObject({
      folder: 'f1',
      search: 'contrato',
      sort: 'updated',
      view: 'grid',
      page: 2
    });
    expect(serializeExplorerQuery(query)).toContain('folder=f1');
    expect(serializeExplorerQuery(query)).toContain('view=grid');
  });

  it('falls back to safe defaults for malformed parameters', () => {
    expect(parseExplorerQuery(new URLSearchParams('page=-3&sort=unknown&view=unknown'))).toEqual(
      defaultExplorerQuery
    );
  });
});

describe('document explorer interactions', () => {
  it('opens only on a real double click for mouse input', () => {
    expect(activationForClick(1, 'mouse')).toBe('select');
    expect(activationForClick(2, 'mouse')).toBe('open');
    expect(activationForClick(1, 'touch')).toBe('open');
  });

  it('maps keyboard actions without duplicate semantics', () => {
    expect(keyboardAction('Enter')).toBe('open');
    expect(keyboardAction(' ')).toBe('open');
    expect(keyboardAction('F2')).toBe('rename');
    expect(keyboardAction('F10', { shift: true })).toBe('context-menu');
    expect(keyboardAction('a', { ctrl: true })).toBe('select-all');
  });

  it('keeps PDF and non-PDF opening behavior explicit', () => {
    expect(
      documentOpenAction({
        id: '1',
        title: 'Contrato',
        original_filename: 'contrato.pdf',
        extension: '.pdf',
        technical_status: 'active',
        business_status: 'current',
        size_bytes: 10,
        category_name: null
      })
    ).toBe('open-pdf');
    expect(
      documentOpenAction({
        id: '2',
        title: 'Manual',
        original_filename: 'manual.docx',
        extension: '.docx',
        technical_status: 'active',
        business_status: 'current',
        size_bytes: 10,
        category_name: null
      })
    ).toBe('download');
  });

  it('requires the dedicated permission for structural operations', () => {
    expect(canExplorerAction('create-folder', (code) => code === 'documents:manage_folders')).toBe(
      true
    );
    expect(canExplorerAction('move', () => false)).toBe(false);
    expect(canExplorerAction('upload', (code) => code === 'documents:upload')).toBe(true);
  });
});
