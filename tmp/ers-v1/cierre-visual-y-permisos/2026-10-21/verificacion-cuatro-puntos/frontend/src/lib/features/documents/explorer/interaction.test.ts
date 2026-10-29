import { describe, expect, it } from 'vitest';
import { documentOpenAction } from './interaction';

const baseDocument = {
  id: 'document-id',
  title: 'Archivo',
  original_filename: 'archivo',
  technical_status: 'active',
  business_status: 'current',
  size_bytes: 1,
  category_name: null
};

describe('document opening actions', () => {
  it.each(['.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg'])(
    'opens active %s files in the browser',
    (extension) => {
      expect(documentOpenAction({ ...baseDocument, extension })).toBe('open-image');
    }
  );

  it('keeps PDF opening behavior', () => {
    expect(documentOpenAction({ ...baseDocument, extension: '.pdf' })).toBe('open-pdf');
  });

  it.each(['.ppt', '.pptx', '.odp', '.rtf', '.tif', '.tiff', '.md', '.json', '.xml'])(
    'downloads active %s files because they have no browser preview',
    (extension) => {
      expect(documentOpenAction({ ...baseDocument, extension })).toBe('download');
    }
  );

  it.each(['.ppt', '.pptx', '.odp', '.rtf', '.tif', '.tiff', '.md', '.json', '.xml'])(
    'downloads active %s files because they have no browser preview',
    (extension) => {
      expect(documentOpenAction({ ...baseDocument, extension })).toBe('download');
    }
  );

  it('downloads inactive images instead of previewing them', () => {
    expect(
      documentOpenAction({ ...baseDocument, extension: '.png', technical_status: 'quarantined' })
    ).toBe('download');
  });
});
