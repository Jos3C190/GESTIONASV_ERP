import { api } from '$lib/api/client';

/** Error raised when the browser refuses to create the document tab. */
export class DocumentBrowserOpenError extends Error {
  readonly code = 'document_popup_blocked';

  constructor(
    message = 'El navegador bloqueó la nueva pestaña. Permita ventanas emergentes e intente nuevamente.'
  ) {
    super(message);
    this.name = 'DocumentBrowserOpenError';
  }
}

/**
 * Opens the canonical document in the browser's own viewer.
 *
 * The blank tab is created synchronously from the user gesture so popup
 * blockers do not reject it while the signed URL is being requested. The
 * opener is detached immediately and the temporary document applies a
 * no-referrer policy. This is equivalent to `noopener,noreferrer` while
 * retaining a window handle for the asynchronous URL request. The signed URL
 * is never placed in the ERP route or persisted by the client.
 */
export async function openDocumentInBrowser(
  documentId: string,
  employeeId?: string
): Promise<void> {
  const popup = window.open('about:blank', '_blank');
  if (!popup) throw new DocumentBrowserOpenError();

  try {
    popup.opener = null;
    const referrerMeta = popup.document.createElement('meta');
    referrerMeta.name = 'referrer';
    referrerMeta.content = 'no-referrer';
    popup.document.head.appendChild(referrerMeta);

    const result = await api.documents.previewUrl(documentId, employeeId, 'original');
    popup.location.replace(result.url);
  } catch (error) {
    popup.close();
    throw error;
  }
}
