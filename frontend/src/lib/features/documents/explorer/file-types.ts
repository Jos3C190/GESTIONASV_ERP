export type DocumentFileTone =
  | 'pdf'
  | 'doc'
  | 'sheet'
  | 'slides'
  | 'archive'
  | 'text'
  | 'image'
  | 'file';

const GROUPS: Record<Exclude<DocumentFileTone, 'file'>, ReadonlySet<string>> = {
  pdf: new Set(['pdf']),
  doc: new Set(['doc', 'docx', 'odt', 'rtf']),
  sheet: new Set(['xls', 'xlsx', 'csv', 'ods']),
  slides: new Set(['ppt', 'pptx', 'odp']),
  archive: new Set(['zip', 'rar', '7z', 'tar', 'gz']),
  text: new Set(['txt', 'md', 'json', 'xml', 'yaml', 'yml']),
  image: new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'])
};

export function normalizeDocumentExtension(extension: string | undefined): string {
  return extension?.replace('.', '').trim().toLowerCase() ?? '';
}

export function documentFileTone(extension: string | undefined): DocumentFileTone {
  const normalized = normalizeDocumentExtension(extension);
  for (const [tone, extensions] of Object.entries(GROUPS) as Array<
    [Exclude<DocumentFileTone, 'file'>, ReadonlySet<string>]
  >) {
    if (extensions.has(normalized)) return tone;
  }
  return 'file';
}

export function documentFileLabel(extension: string | undefined): string {
  const normalized = normalizeDocumentExtension(extension);
  if (normalized === 'docx') return 'DOC';
  if (normalized === 'xlsx') return 'XLS';
  if (normalized === 'pptx') return 'PPT';
  return normalized.slice(0, 4).toUpperCase() || 'FILE';
}
