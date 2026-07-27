/** Helper para generar URLs de avatar de ejemplo (pravatar.cc) basadas en un seed determinístico. */

/**
 * Si el empleado ya tiene photo_url, la usa. Si no, genera una URL de ejemplo
 * determinística basada en el ID del empleado (imágenes de pravatar.cc).
 */
export function resolvePhotoUrl(photoUrl: string | null | undefined, seed: string): string {
  if (photoUrl && photoUrl.trim()) return photoUrl;
  // Genera un seed numérico determinístico (0-69) para pravatar.cc
  let hash = 0;
  for (const c of seed) hash = (hash * 31 + c.charCodeAt(0)) & 0xffffffff;
  const n = Math.abs(hash) % 70;
  return `https://i.pravatar.cc/300?u=${n}`;
}

/** Iniciales a partir de nombre + apellido. */
export function initialsOf(firstName: string, lastName: string): string {
  const a = firstName.trim()[0] ?? '';
  const b = lastName.trim()[0] ?? '';
  return (a + b).toUpperCase() || '??';
}