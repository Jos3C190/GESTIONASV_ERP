import { describe, expect, it } from 'vitest';
import {
  DOCUMENT_ACCEPT,
  documentContentType,
  isSupportedDocumentFile
} from './document-upload';

describe('document upload formats', () => {
  it.each(['photo.jpg', 'photo.JPEG', 'photo.png', 'photo.webp', 'photo.gif', 'photo.svg'])(
    'accepts %s',
    (name) => {
      expect(isSupportedDocumentFile({ name, size: 1024 })).toBe(true);
    }
  );

  it.each(['photo.bmp', 'photo.exe'])('rejects %s', (name) => {
    expect(isSupportedDocumentFile({ name, size: 1024 })).toBe(false);
  });

  it('infers an image MIME when the browser leaves File.type empty', () => {
    expect(documentContentType({ name: 'photo.jpg', type: '' })).toBe('image/jpeg');
    expect(documentContentType({ name: 'photo.webp', type: '' })).toBe('image/webp');
    expect(documentContentType({ name: 'photo.gif', type: '' })).toBe('image/gif');
    expect(documentContentType({ name: 'photo.svg', type: '' })).toBe('image/svg+xml');
  });

  it('keeps the browser MIME when it is available', () => {
    expect(documentContentType({ name: 'photo.png', type: 'image/png' })).toBe('image/png');
  });

  it('publishes the accepted image extensions to the native picker', () => {
    expect(DOCUMENT_ACCEPT).toContain('.jpg');
    expect(DOCUMENT_ACCEPT).toContain('.jpeg');
    expect(DOCUMENT_ACCEPT).toContain('.png');
    expect(DOCUMENT_ACCEPT).toContain('.webp');
    expect(DOCUMENT_ACCEPT).toContain('.gif');
    expect(DOCUMENT_ACCEPT).toContain('.svg');
  });
});
