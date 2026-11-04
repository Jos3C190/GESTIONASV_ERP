/** Checks and prepares a document photo in the browser, before anything is uploaded. */

export const MAX_EDGE = 2000;
export const MIN_EDGE = 640;
export const JPEG_QUALITY = 0.88;
export const ANALYSIS_EDGE = 640;

/**
 * Calibrated on degraded copies of sample licenses, each threshold sitting between
 * the good and bad values measured. Real phone photos may still move them.
 */
export const BLUR_THRESHOLD = 100;
export const DARK_THRESHOLD = 140;
export const OVEREXPOSED_THRESHOLD = 100;
// El reverso limpio deja huecos blancos de hasta 9.4 %; un reflejo menor lo cubre "No pudimos leer".
export const GLARE_THRESHOLD = 12;
export const MIN_FILL = 40;

const GRID_COLUMNS = 24;
const CLIPPED_TONE = 245;
const DETAIL_RANGE = 40;
/** Sharpness is read from the centre, so a crisp table cannot make up for a blurry card. */
const CENTER_MARGIN = 0.15;

export type QualityIssue = 'too_small' | 'too_far' | 'blurry' | 'dark' | 'overexposed' | 'glare';

export interface ImageMetrics {
  sharpness: number;
  /** Tone of the darkest 5 %: it rises when too much light washes the text out. */
  darkTone: number;
  /** Tone of the brightest 5 %: a white card stays low only when the light is poor. */
  lightTone: number;
  /** Largest burnt-out patch away from the edges, as a percentage of the frame. */
  glare: number;
  /** Share of the frame between the outermost areas with detail. */
  fill: number;
}

export interface PreparedImage {
  file: File;
  issues: QualityIssue[];
}

/** Most important first: only one instruction is shown at a time. */
export const QUALITY_MESSAGES: Record<QualityIssue, { title: string; hint: string }> = {
  too_small: {
    title: 'Foto muy pequeña',
    hint: 'Acércate o usa una imagen de mayor tamaño.'
  },
  too_far: { title: 'Estás muy lejos', hint: 'Acércate: el documento debe llenar el marco.' },
  blurry: { title: 'Foto borrosa', hint: 'Sostén firme la cámara e inténtalo de nuevo.' },
  dark: { title: 'Poca luz', hint: 'Busca un lugar más iluminado.' },
  overexposed: { title: 'Demasiada luz', hint: 'Aléjate de la lámpara o del sol.' },
  glare: { title: 'Hay un reflejo sobre el documento', hint: 'Inclínalo un poco.' }
};

/** Scale down only; a small photo is not improved by enlarging it here. */
export function fitWithin(
  width: number,
  height: number,
  maxEdge: number
): { width: number; height: number } {
  const longest = Math.max(width, height);
  if (longest <= maxEdge) return { width, height };
  const ratio = maxEdge / longest;
  return { width: Math.round(width * ratio), height: Math.round(height * ratio) };
}

/**
 * Size for a camera crop. The guide already frames the card, so a small crop means a
 * modest camera, which moving closer cannot fix; sharpness is still judged on the result.
 */
export function cameraCropSize(width: number, height: number): { width: number; height: number } {
  const grow = Math.max(1, MIN_EDGE / Math.max(width, height));
  return { width: Math.round(width * grow), height: Math.round(height * grow) };
}

export function toGrey(rgba: Uint8ClampedArray): Uint8ClampedArray {
  const grey = new Uint8ClampedArray(rgba.length / 4);
  for (let index = 0; index < grey.length; index++) {
    const at = index * 4;
    grey[index] = 0.299 * rgba[at]! + 0.587 * rgba[at + 1]! + 0.114 * rgba[at + 2]!;
  }
  return grey;
}

/** Variance of a 4-neighbour Laplacian over the central area: sharp edges score high. */
function centerSharpness(grey: Uint8ClampedArray, width: number, height: number): number {
  const fromY = Math.max(1, Math.floor(height * CENTER_MARGIN));
  const toY = Math.min(height - 1, Math.ceil(height * (1 - CENTER_MARGIN)));
  const fromX = Math.max(1, Math.floor(width * CENTER_MARGIN));
  const toX = Math.min(width - 1, Math.ceil(width * (1 - CENTER_MARGIN)));
  let sum = 0;
  let squares = 0;
  let count = 0;
  for (let y = fromY; y < toY; y++) {
    for (let x = fromX; x < toX; x++) {
      const at = y * width + x;
      const value =
        grey[at - width]! + grey[at + width]! + grey[at - 1]! + grey[at + 1]! - 4 * grey[at]!;
      sum += value;
      squares += value * value;
      count++;
    }
  }
  if (count === 0) return 0;
  const mean = sum / count;
  return squares / count - mean * mean;
}

function percentile(grey: Uint8ClampedArray, share: number): number {
  const histogram = new Uint32Array(256);
  for (const value of grey) histogram[value]!++;
  const target = grey.length * share;
  let seen = 0;
  for (let tone = 0; tone < 256; tone++) {
    seen += histogram[tone]!;
    if (seen >= target) return tone;
  }
  return 255;
}

/**
 * Largest burnt-out patch that does not touch the frame. A license is mostly white,
 * so counting bright pixels says nothing; a reflection is a solid island inside it.
 */
function largestInnerPatch(clipped: boolean[], columns: number, rows: number): number {
  const seen = new Uint8Array(clipped.length);
  let largest = 0;
  for (let start = 0; start < clipped.length; start++) {
    if (!clipped[start] || seen[start]) continue;
    const stack = [start];
    seen[start] = 1;
    let size = 0;
    let touchesEdge = false;
    while (stack.length > 0) {
      const cell = stack.pop()!;
      const row = Math.floor(cell / columns);
      const column = cell % columns;
      size++;
      if (row === 0 || row === rows - 1 || column === 0 || column === columns - 1) {
        touchesEdge = true;
      }
      const neighbours = [
        row > 0 ? cell - columns : -1,
        row < rows - 1 ? cell + columns : -1,
        column > 0 ? cell - 1 : -1,
        column < columns - 1 ? cell + 1 : -1
      ];
      for (const next of neighbours) {
        if (next >= 0 && clipped[next] && !seen[next]) {
          seen[next] = 1;
          stack.push(next);
        }
      }
    }
    if (!touchesEdge) largest = Math.max(largest, size);
  }
  return largest;
}

export function measureImage(grey: Uint8ClampedArray, width: number, height: number): ImageMetrics {
  const columns = GRID_COLUMNS;
  const rows = Math.max(1, Math.round((GRID_COLUMNS * height) / width));
  const clipped = new Array<boolean>(columns * rows).fill(false);
  let top = rows;
  let bottom = -1;
  let left = columns;
  let right = -1;
  for (let row = 0; row < rows; row++) {
    const fromY = Math.floor((row * height) / rows);
    const toY = Math.floor(((row + 1) * height) / rows);
    for (let column = 0; column < columns; column++) {
      const fromX = Math.floor((column * width) / columns);
      const toX = Math.floor(((column + 1) * width) / columns);
      let low = 255;
      let high = 0;
      for (let y = fromY; y < toY; y++) {
        for (let x = fromX; x < toX; x++) {
          const value = grey[y * width + x]!;
          if (value < low) low = value;
          if (value > high) high = value;
        }
      }
      clipped[row * columns + column] = low >= CLIPPED_TONE;
      if (high - low >= DETAIL_RANGE) {
        top = Math.min(top, row);
        bottom = Math.max(bottom, row);
        left = Math.min(left, column);
        right = Math.max(right, column);
      }
    }
  }
  const total = columns * rows;
  return {
    sharpness: centerSharpness(grey, width, height),
    darkTone: percentile(grey, 0.05),
    lightTone: percentile(grey, 0.95),
    glare: (largestInnerPatch(clipped, columns, rows) * 100) / total,
    fill: bottom < 0 ? 0 : ((bottom - top + 1) * (right - left + 1) * 100) / total
  };
}

export function assessQuality(
  metrics: ImageMetrics,
  sourceWidth: number,
  sourceHeight: number
): QualityIssue[] {
  const issues: QualityIssue[] = [];
  if (Math.max(sourceWidth, sourceHeight) < MIN_EDGE) issues.push('too_small');
  if (metrics.fill < MIN_FILL) issues.push('too_far');
  if (metrics.sharpness < BLUR_THRESHOLD) issues.push('blurry');
  if (metrics.lightTone < DARK_THRESHOLD) issues.push('dark');
  if (metrics.darkTone > OVEREXPOSED_THRESHOLD) issues.push('overexposed');
  if (metrics.glare >= GLARE_THRESHOLD) issues.push('glare');
  return issues;
}

function canvasFor(
  width: number,
  height: number
): { canvas: HTMLCanvasElement; context: CanvasRenderingContext2D } {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext('2d', { willReadFrequently: true });
  if (!context) throw new Error('canvas_unavailable');
  return { canvas, context };
}

/** Assess anything drawable: a decoded photo, or a live camera frame. */
export function assessDrawable(
  source: CanvasImageSource,
  width: number,
  height: number
): QualityIssue[] {
  const size = fitWithin(width, height, ANALYSIS_EDGE);
  const { context } = canvasFor(size.width, size.height);
  context.drawImage(source, 0, 0, size.width, size.height);
  const pixels = context.getImageData(0, 0, size.width, size.height);
  return assessQuality(measureImage(toGrey(pixels.data), size.width, size.height), width, height);
}

/**
 * Part of the video behind the on-screen guide. The video fills its box with
 * `object-fit: cover`, so screen coordinates must be mapped back to video pixels.
 */
export function guideCrop(
  video: { width: number; height: number },
  view: { x: number; y: number; width: number; height: number },
  guide: { x: number; y: number; width: number; height: number }
): { x: number; y: number; width: number; height: number } {
  const scale = Math.max(view.width / video.width, view.height / video.height);
  const hiddenX = (video.width * scale - view.width) / 2;
  const hiddenY = (video.height * scale - view.height) / 2;
  const x = Math.max(0, (guide.x - view.x + hiddenX) / scale);
  const y = Math.max(0, (guide.y - view.y + hiddenY) / scale);
  return {
    x,
    y,
    width: Math.min(video.width - x, guide.width / scale),
    height: Math.min(video.height - y, guide.height / scale)
  };
}

/**
 * Re-encoding always yields a clean JPEG: it drops EXIF data such as the GPS
 * position, avoids the trailing bytes some phones add, and keeps uploads small.
 */
export async function prepareImage(
  source: Blob,
  side: 'front' | 'back',
  filePrefix: string
): Promise<PreparedImage> {
  // `from-image` respeta la orientación con que el teléfono guardó la foto.
  const bitmap = await createImageBitmap(source, { imageOrientation: 'from-image' });
  try {
    const size = fitWithin(bitmap.width, bitmap.height, MAX_EDGE);
    const { canvas, context } = canvasFor(size.width, size.height);
    context.drawImage(bitmap, 0, 0, size.width, size.height);
    const issues = assessDrawable(bitmap, bitmap.width, bitmap.height);
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, 'image/jpeg', JPEG_QUALITY)
    );
    if (!blob) throw new Error('image_encode_failed');
    return { file: new File([blob], `${filePrefix}-${side}.jpg`, { type: 'image/jpeg' }), issues };
  } finally {
    bitmap.close();
  }
}
