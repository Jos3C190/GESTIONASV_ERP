import { documentContentType, isSupportedDocumentFile } from '$lib/features/documents/document-upload';
import type { GeneralImportManifestItemInput } from '$lib/api/client';

export interface FolderFile {
  file: File;
  relativePath: string;
}

export interface FolderSelection {
  files: FolderFile[];
  folders: string[];
  rootName: string;
}

interface DirectoryEntryLike {
  isFile: boolean;
  isDirectory: boolean;
  name: string;
  file?: (callback: (file: File) => void, error?: (reason: unknown) => void) => void;
  createReader?: () => {
    readEntries: (callback: (entries: DirectoryEntryLike[]) => void, error?: (reason: unknown) => void) => void;
  };
}

function cleanPath(value: string): string {
  return value.replace(/\\/g, '/').split('/').map((part) => part.trim()).filter(Boolean).join('/');
}

function addParentFolders(path: string, folders: Set<string>) {
  const parts = cleanPath(path).split('/').filter(Boolean);
  for (let index = 1; index < parts.length; index += 1) folders.add(parts.slice(0, index).join('/'));
}

export function importFileIssue(file: Pick<File, 'name' | 'size'>, maxBytes = 50 * 1024 * 1024): string | null {
  if (file.size < 1) return 'El archivo está vacío.';
  if (file.size > maxBytes) return 'Supera el límite de ' + Math.round(maxBytes / (1024 * 1024)) + ' MB.';
  if (!isSupportedDocumentFile(file, maxBytes)) return 'Formato no permitido.';
  return null;
}

export function selectionFromPicker(files: File[]): FolderSelection {
  const seen = new Set<string>();
  const entries = files.map((file) => ({
    file,
    relativePath: cleanPath((file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name)
  })).filter((entry) => {
    if (!entry.relativePath || seen.has(entry.relativePath)) return false;
    seen.add(entry.relativePath);
    return true;
  });
  const folders = new Set<string>();
  entries.forEach((entry) => addParentFolders(entry.relativePath, folders));
  return { files: entries, folders: [...folders], rootName: entries[0]?.relativePath.split('/')[0] ?? '' };
}

function readFile(entry: DirectoryEntryLike): Promise<File> {
  return new Promise((resolve, reject) => entry.file?.(resolve, reject));
}

function readDirectory(entry: DirectoryEntryLike): Promise<DirectoryEntryLike[]> {
  return new Promise((resolve, reject) => {
    const reader = entry.createReader?.();
    if (!reader) return resolve([]);
    const result: DirectoryEntryLike[] = [];
    const next = () => reader.readEntries((entries) => {
      if (entries.length === 0) resolve(result);
      else { result.push(...entries); next(); }
    }, reject);
    next();
  });
}

async function walkEntry(entry: DirectoryEntryLike, prefix: string, files: FolderFile[], folders: Set<string>): Promise<void> {
  const path = cleanPath(prefix ? prefix + '/' + entry.name : entry.name);
  if (entry.isFile) {
    const file = await readFile(entry);
    files.push({ file, relativePath: path });
    return;
  }
  if (!entry.isDirectory) return;
  folders.add(path);
  const children = await readDirectory(entry);
  await Promise.all(children.map((child) => walkEntry(child, path, files, folders)));
}

export async function selectionFromDrop(items: DataTransferItemList): Promise<FolderSelection> {
  const files: FolderFile[] = [];
  const folders = new Set<string>();
  const entries = Array.from(items).map((item) => {
    const candidate = item as DataTransferItem & { webkitGetAsEntry?: () => unknown };
    return candidate.webkitGetAsEntry?.() as DirectoryEntryLike | null;
  }).filter((entry): entry is DirectoryEntryLike => Boolean(entry));
  await Promise.all(entries.map((entry) => walkEntry(entry, '', files, folders)));
  const uniqueFiles = [...new Map(files.map((entry) => [entry.relativePath, entry])).values()];
  return { files: uniqueFiles, folders: [...folders], rootName: uniqueFiles[0]?.relativePath.split('/')[0] ?? [...folders][0]?.split('/')[0] ?? '' };
}

export function buildFolderManifest(selection: FolderSelection, maxBytes = 50 * 1024 * 1024): {
  manifest: GeneralImportManifestItemInput[];
  validFiles: FolderFile[];
  invalidFiles: Array<{ relativePath: string; reason: string }>;
  totalBytes: number;
} {
  const invalidFiles: Array<{ relativePath: string; reason: string }> = [];
  const validFiles: FolderFile[] = [];
  let totalBytes = 0;
  for (const entry of selection.files) {
    const issue = importFileIssue(entry.file, maxBytes);
    if (issue) {
      invalidFiles.push({ relativePath: entry.relativePath, reason: issue });
      continue;
    }
    validFiles.push(entry);
    totalBytes += entry.file.size;
  }
  const folderPaths = new Set(selection.folders);
  validFiles.forEach((entry) => addParentFolders(entry.relativePath, folderPaths));
  const manifest: GeneralImportManifestItemInput[] = [
    ...[...folderPaths].sort((a, b) => a.split('/').length - b.split('/').length).map((relative_path) => ({ kind: 'folder' as const, relative_path })),
    ...validFiles.map(({ file, relativePath }) => ({ kind: 'file' as const, relative_path: relativePath, size_bytes: file.size, content_type: documentContentType(file) }))
  ];
  return { manifest, validFiles, invalidFiles, totalBytes };
}

export async function sha256(file: File): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
}

export function formatImportBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return Math.max(1, Math.round(bytes / 1024)) + ' KB';
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
}
