import { describe, expect, it } from 'vitest';
import { documentFileLabel, documentFileTone } from './file-types';

describe('document file types', () => {
  it.each([
    ['.pdf', 'pdf'],
    ['DOCX', 'doc'],
    ['.csv', 'sheet'],
    ['.pptx', 'slides'],
    ['.ppt', 'slides'],
    ['.odp', 'slides'],
    ['.zip', 'archive'],
    ['.txt', 'text'],
    ['.md', 'text'],
    ['.json', 'text'],
    ['.xml', 'text'],
    ['.png', 'image'],
    ['.jpg', 'image'],
    ['.webp', 'image'],
    ['.gif', 'image'],
    ['.svg', 'image'],
    ['.tif', 'image'],
    ['.tiff', 'image'],
    ['.rtf', 'doc'],
    ['.bin', 'file']
  ] as const)('maps %s to the %s artwork tone', (extension, tone) => {
    expect(documentFileTone(extension)).toBe(tone);
  });

  it('uses concise labels for Office and document formats', () => {
    expect(documentFileLabel('.docx')).toBe('DOC');
    expect(documentFileLabel('.xlsx')).toBe('XLS');
    expect(documentFileLabel('.pptx')).toBe('PPT');
    expect(documentFileLabel('.ppt')).toBe('PPT');
    expect(documentFileLabel('.odp')).toBe('ODP');
    expect(documentFileLabel('.rtf')).toBe('RTF');
    expect(documentFileLabel('.tiff')).toBe('TIF');
  });
});
