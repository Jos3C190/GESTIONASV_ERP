import type { ExplorerDocument } from './types';
import { isBrowserPreviewable } from '$lib/features/documents/open-document';

export type ExplorerAction = 'open' | 'select' | 'rename' | 'move' | 'delete' | 'restore';
export function canDropIntoFolder(
  item: { id: string; kind: 'folder' | 'file'; parentId: string | null },
  folderId: string | null
): boolean {
  return item.parentId !== folderId && !(item.kind === 'folder' && item.id === folderId);
}

export function activationForClick(
  detail: number,
  pointer: 'mouse' | 'touch' | 'keyboard' = 'mouse'
): ExplorerAction {
  if (pointer === 'touch' || pointer === 'keyboard' || detail >= 2) return 'open';
  return 'select';
}

export function keyboardAction(
  key: string,
  modifiers: { ctrl?: boolean; meta?: boolean; shift?: boolean } = {}
): ExplorerAction | 'select-all' | 'close' | 'context-menu' | 'none' {
  const command = Boolean(modifiers.ctrl || modifiers.meta);
  if (key === 'Enter' || key === ' ') return 'open';
  if (key === 'F2') return 'rename';
  if (key === 'Delete' || key === 'Backspace') return 'delete';
  if (key === 'Escape') return 'close';
  if (command && key.toLowerCase() === 'a') return 'select-all';
  if (key === 'F10' && modifiers.shift) return 'context-menu';
  return 'none';
}

export function documentOpenAction(document: ExplorerDocument): 'open-pdf' | 'open-image' | 'download' {
  if (!isBrowserPreviewable(document.extension, document.technical_status)) return 'download';
  return document.extension.toLowerCase() === '.pdf' ? 'open-pdf' : 'open-image';
}

export function canExplorerAction(
  action: 'rename' | 'move' | 'delete' | 'restore' | 'upload' | 'create-folder',
  permissions: (code: string) => boolean
): boolean {
  if (action === 'create-folder' || action === 'move')
    return permissions('documents:manage_folders');
  if (action === 'rename')
    return permissions('documents:manage_folders');
  if (action === 'delete') return permissions('documents:delete');
  if (action === 'restore') return permissions('documents:manage_folders');
  return permissions('documents:upload');
}
