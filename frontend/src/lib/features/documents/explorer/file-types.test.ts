import { describe, expect, it } from 'vitest';
import { documentFileLabel, documentFileTone } from './file-types';

describe('document file types', () => {
  it.each([
    ['.pdf', 'pdf'],
    ['DOCX', 'doc'],
    ['.csv', 'sheet'],
    ['.pptx', 'slides'],
    ['.zip', 'archive'],
    ['.txt', 'text'],
    ['.png', 'image'],
    ['.jpg', 'image'],
    ['.webp', 'image'],
    ['.gif', 'image'],
    ['.svg', 'image'],
    ['.bin', 'file']
  ] as const)('maps %s to the %s artwork tone', (extension, tone) => {
    expect(documentFileTone(extension)).toBe(tone);
  });

  it('uses concise labels for Office formats', () => {
    expect(documentFileLabel('.docx')).toBe('DOC');
    expect(documentFileLabel('.xlsx')).toBe('XLS');
    expect(documentFileLabel('.pptx')).toBe('PPT');
  });
});
