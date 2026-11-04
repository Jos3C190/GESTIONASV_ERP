export const DOCUMENT_MAX_BYTES = 50 * 1024 * 1024;

/** Solo se registran con su captura guiada; el backend rechaza cualquier otra vía. */
export const CAPTURE_ONLY_CATEGORY_CODES: ReadonlySet<string> = new Set([
  'driver_license',
  'driver_license_back',
  'circulation_card',
  'circulation_card_back'
]);

/** Estos documentos no se editan ni reemplazan: un cambio exige una nueva captura. */
export function isCaptureOnly(document: { category_code?: string | null }): boolean {
  return CAPTURE_ONLY_CATEGORY_CODES.has(document.category_code ?? '');
}

/**
 * A YYYY-MM-DD is a calendar day. `new Date` reads it as midnight UTC, which in
 * El Salvador is still the previous day.
 */
export function formatDocumentDate(value: string): string {
  const [year, month, day] = value.slice(0, 10).split('-').map(Number);
  return new Date(year ?? 0, (month ?? 1) - 1, day ?? 1).toLocaleDateString('es-SV');
}

export const DOCUMENT_ACCEPT =
  '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.csv,.txt,.md,.json,.xml,.rtf,.odt,.ods,.odp,.jpg,.jpeg,.png,.webp,.gif,.svg,.tif,.tiff';

const DOCUMENT_EXTENSIONS = new Set([
  'pdf',
  'doc',
  'docx',
  'xls',
  'xlsx',
  'ppt',
  'pptx',
  'csv',
  'txt',
  'md',
  'json',
  'xml',
  'rtf',
  'odt',
  'ods',
  'odp',
  'jpg',
  'jpeg',
  'png',
  'webp',
  'gif',
  'svg',
  'tif',
  'tiff'
]);

const FALLBACK_CONTENT_TYPES: Record<string, string> = {
  ppt: 'application/vnd.ms-powerpoint',
  pptx: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  odp: 'application/vnd.oasis.opendocument.presentation',
  rtf: 'application/rtf',
  md: 'text/markdown',
  json: 'application/json',
  xml: 'application/xml'
};

const IMAGE_CONTENT_TYPES: Record<string, string> = {
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  png: 'image/png',
  webp: 'image/webp',
  gif: 'image/gif',
  svg: 'image/svg+xml',
  tif: 'image/tiff',
  tiff: 'image/tiff'
};

export function documentExtension(filename: string): string {
  return filename.split('.').pop()?.trim().toLowerCase() ?? '';
}

export function isSupportedDocumentFile(
  file: Pick<File, 'name' | 'size'>,
  maxBytes = DOCUMENT_MAX_BYTES
): boolean {
  const extension = documentExtension(file.name);
  return file.size >= 1 && file.size <= maxBytes && DOCUMENT_EXTENSIONS.has(extension);
}

export function documentContentType(file: Pick<File, 'name' | 'type'>): string {
  const extension = documentExtension(file.name);
  return (
    file.type ||
    IMAGE_CONTENT_TYPES[extension] ||
    FALLBACK_CONTENT_TYPES[extension] ||
    'application/octet-stream'
  );
}
