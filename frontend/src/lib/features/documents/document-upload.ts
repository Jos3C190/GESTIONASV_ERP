export const DOCUMENT_MAX_BYTES = 50 * 1024 * 1024;

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
