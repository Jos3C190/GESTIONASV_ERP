import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

/** Optional static QA artifact from the actual component DOM, using test fixtures. */
export function saveRetaceoPreview(name: string, container: HTMLElement) {
  const directory = process.env.RETACEO_PREVIEW_DIR;
  if (!directory) return;
  mkdirSync(directory, { recursive: true });
  const clone = container.cloneNode(true) as HTMLElement;
  const fields = container.querySelectorAll('input, select, textarea');
  clone.querySelectorAll('input, select, textarea').forEach((field, index) => {
    const source = fields[index] as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;
    if (field.tagName === 'TEXTAREA') field.textContent = source.value;
    else if (field.tagName === 'SELECT')
      field.querySelectorAll('option').forEach((option) => {
        if (option.value === source.value) option.setAttribute('selected', '');
        else option.removeAttribute('selected');
      });
    else field.setAttribute('value', source.value);
  });
  for (const theme of ['light', 'dark'])
    writeFileSync(
      join(directory, `${name}-${theme}.html`),
      `<!doctype html><html lang="es" data-theme="${theme}"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><base href="http://localhost:5173/"><link rel="stylesheet" href="http://localhost:5173/src/app.css?direct"><title>Revisión ${name} · Grupo Lorena</title></head><body class="bg-surface text-foreground font-sans"><main class="mx-auto max-w-6xl px-4 py-6 sm:px-6"><p class="mb-5 border-b border-border pb-3 text-xs text-foreground-muted">Grupo Lorena · Vista estática de prueba del componente, con datos de demostración</p>${clone.innerHTML}</main></body></html>`
    );
}
