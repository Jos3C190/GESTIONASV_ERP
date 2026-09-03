import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  previewUrl: vi.fn()
}));

vi.mock('$lib/api/client', () => ({
  api: {
    documents: {
      previewUrl: mocks.previewUrl
    }
  }
}));

import {
  DocumentBrowserOpenError,
  openDocumentInBrowser
} from '$lib/features/documents/open-document';

describe('openDocumentInBrowser', () => {
  beforeEach(() => {
    mocks.previewUrl.mockReset();
    vi.restoreAllMocks();
  });

  it('opens a blank tab immediately and navigates it to the canonical URL', async () => {
    const replace = vi.fn();
    const head = { appendChild: vi.fn() } as unknown as HTMLHeadElement;
    const popup = {
      location: { replace },
      close: vi.fn(),
      document: {
        createElement: vi.fn(() => ({ name: '', content: '' })),
        head
      }
    } as unknown as Window;
    const open = vi.spyOn(window, 'open').mockReturnValue(popup);
    mocks.previewUrl.mockResolvedValue({
      url: 'https://rustfs.test/signed.pdf',
      expires_at: 'later'
    });

    await openDocumentInBrowser('document-1', 'employee-1');

    expect(open).toHaveBeenCalledWith('about:blank', '_blank');
    expect(mocks.previewUrl).toHaveBeenCalledWith('document-1', 'employee-1', 'original');
    expect(replace).toHaveBeenCalledWith('https://rustfs.test/signed.pdf');
  });

  it('reports a blocked popup without requesting a signed URL', async () => {
    vi.spyOn(window, 'open').mockReturnValue(null);

    await expect(openDocumentInBrowser('document-1')).rejects.toBeInstanceOf(
      DocumentBrowserOpenError
    );
    expect(mocks.previewUrl).not.toHaveBeenCalled();
  });

  it('closes the temporary tab when URL authorization fails', async () => {
    const close = vi.fn();
    const popup = {
      location: { replace: vi.fn() },
      close,
      document: {
        createElement: vi.fn(() => ({ name: '', content: '' })),
        head: { appendChild: vi.fn() }
      }
    } as unknown as Window;
    vi.spyOn(window, 'open').mockReturnValue(popup);
    const failure = new Error('request failed');
    mocks.previewUrl.mockRejectedValue(failure);

    await expect(openDocumentInBrowser('document-1')).rejects.toBe(failure);
    expect(close).toHaveBeenCalledOnce();
  });
});
