import receiptCss from './receipt.css?raw';

function escapeHtml(text: string): string {
  return text
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

/**
 * Imprime un elemento en rollo de 80 mm con el diálogo del navegador. Se arma una hoja aparte (un
 * marco oculto) con solo el comprobante y sus estilos: sin la barra ni los colores de la aplicación.
 */
export function printReceipt(node: HTMLElement, title: string): void {
  const frame = document.createElement('iframe');
  frame.setAttribute('aria-hidden', 'true');
  frame.tabIndex = -1;
  Object.assign(frame.style, {
    position: 'fixed',
    right: '0',
    bottom: '0',
    width: '0',
    height: '0',
    border: '0',
    visibility: 'hidden'
  });
  frame.srcdoc = `<!doctype html><html lang="es"><head><meta charset="utf-8"><title>${escapeHtml(
    title
  )}</title><style>@page{size:80mm auto;margin:0}html,body{margin:0;padding:0;background:#fff}${receiptCss}</style></head><body>${
    node.outerHTML
  }</body></html>`;
  frame.onload = () => {
    const view = frame.contentWindow;
    if (!view) {
      frame.remove();
      return;
    }
    view.addEventListener('afterprint', () => frame.remove(), { once: true });
    view.focus();
    view.print();
    // Algunos navegadores no avisan al cerrar el diálogo: la hoja se retira igual.
    window.setTimeout(() => frame.isConnected && frame.remove(), 60_000);
  };
  document.body.appendChild(frame);
}
