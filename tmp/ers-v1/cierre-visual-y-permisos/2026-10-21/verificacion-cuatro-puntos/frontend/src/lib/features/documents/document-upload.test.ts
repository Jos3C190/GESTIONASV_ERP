import { describe, expect, it } from 'vitest';
import { DOCUMENT_ACCEPT, documentContentType, isSupportedDocumentFile } from './document-upload';

describe('document upload formats', () => {
  it.each([
    'photo.jpg',
    'photo.JPEG',
    'photo.png',
    'photo.webp',
    'photo.gif',
    'photo.svg',
    'deck.pptx',
    'deck.PPT',
    'deck.odp',
    'note.rtf',
    'scan.tiff',
    'readme.md',
    'data.json',
    'data.xml'
  ])('accepts %s', (name) => {
    expect(isSupportedDocumentFile({ name, size: 1024 })).toBe(true);
  });

  it.each(['photo.bmp', 'photo.heic', 'photo.exe', 'deck.key'])('rejects %s', (name) => {
    expect(isSupportedDocumentFile({ name, size: 1024 })).toBe(false);
  });

  it('infers an image MIME when the browser leaves File.type empty', () => {
    expect(documentContentType({ name: 'photo.jpg', type: '' })).toBe('image/jpeg');
    expect(documentContentType({ name: 'photo.webp', type: '' })).toBe('image/webp');
    expect(documentContentType({ name: 'photo.gif', type: '' })).toBe('image/gif');
    expect(documentContentType({ name: 'photo.svg', type: '' })).toBe('image/svg+xml');
    expect(documentContentType({ name: 'scan.tiff', type: '' })).toBe('image/tiff');
  });

  it('infers structured and presentation MIME types when File.type is empty', () => {
    expect(documentContentType({ name: 'deck.pptx', type: '' })).toBe(
      'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    );
    expect(documentContentType({ name: 'deck.ppt', type: '' })).toBe(
      'application/vnd.ms-powerpoint'
    );
    expect(documentContentType({ name: 'deck.odp', type: '' })).toBe(
      'application/vnd.oasis.opendocument.presentation'
    );
    expect(documentContentType({ name: 'note.rtf', type: '' })).toBe('application/rtf');
    expect(documentContentType({ name: 'readme.md', type: '' })).toBe('text/markdown');
    expect(documentContentType({ name: 'data.json', type: '' })).toBe('application/json');
    expect(documentContentType({ name: 'data.xml', type: '' })).toBe('application/xml');
  });

  it('keeps the browser MIME when it is available', () => {
    expect(documentContentType({ name: 'photo.png', type: 'image/png' })).toBe('image/png');
  });

  it('publishes the accepted extensions to the native picker', () => {
    for (const extension of [
      '.jpg',
      '.jpeg',
      '.png',
      '.webp',
      '.gif',
      '.svg',
      '.tif',
      '.tiff',
      '.ppt',
      '.pptx',
      '.odp',
      '.rtf',
      '.md',
      '.json',
      '.xml'
    ]) {
      expect(DOCUMENT_ACCEPT).toContain(extension);
    }
  });
});
