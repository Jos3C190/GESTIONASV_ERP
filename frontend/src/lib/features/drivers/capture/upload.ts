import { prepareImage, type PreparedImage } from './image-prep';

export async function checksumOf(file: Blob): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
}

export function prepareForUpload(source: Blob, side: 'front' | 'back'): Promise<PreparedImage> {
  return prepareImage(source, side);
}
