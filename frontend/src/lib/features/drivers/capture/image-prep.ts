/** Prepares a license photo in the browser before it is uploaded. */

export const MAX_EDGE = 2000;
export const MIN_EDGE = 640;
export const JPEG_QUALITY = 0.88;
/** Below this variance of the Laplacian the text is usually too soft to read. */
export const BLUR_THRESHOLD = 40;
export const DARK_THRESHOLD = 45;
export const ANALYSIS_EDGE = 640;

export interface ImageQuality {
  blurry: boolean;
  dark: boolean;
  tooSmall: boolean;
}

export interface PreparedImage {
  file: File;
  quality: ImageQuality;
}

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

/** Variance of a 4-neighbour Laplacian over grey values: sharp edges score high. */
export function laplacianVariance(grey: Uint8ClampedArray, width: number): number {
  const height = Math.floor(grey.length / width);
  if (width < 3 || height < 3) return 0;
  let sum = 0;
  let squares = 0;
  let count = 0;
  for (let y = 1; y < height - 1; y++) {
    for (let x = 1; x < width - 1; x++) {
      const at = y * width + x;
      const value =
        grey[at - width]! + grey[at + width]! + grey[at - 1]! + grey[at + 1]! - 4 * grey[at]!;
      sum += value;
      squares += value * value;
      count++;
    }
  }
  const mean = sum / count;
  return squares / count - mean * mean;
}

export function toGrey(rgba: Uint8ClampedArray): Uint8ClampedArray {
  const grey = new Uint8ClampedArray(rgba.length / 4);
  for (let index = 0; index < grey.length; index++) {
    const at = index * 4;
    grey[index] = 0.299 * rgba[at]! + 0.587 * rgba[at + 1]! + 0.114 * rgba[at + 2]!;
  }
  return grey;
}

export function assessQuality(
  grey: Uint8ClampedArray,
  analysisWidth: number,
  sourceWidth: number,
  sourceHeight: number
): ImageQuality {
  let total = 0;
  for (const value of grey) total += value;
  return {
    blurry: laplacianVariance(grey, analysisWidth) < BLUR_THRESHOLD,
    dark: total / grey.length < DARK_THRESHOLD,
    tooSmall: Math.max(sourceWidth, sourceHeight) < MIN_EDGE
  };
}

export function qualityMessages(quality: ImageQuality): string[] {
  const messages: string[] = [];
  if (quality.tooSmall) messages.push('La foto es muy pequeña; acércate o usa otra imagen.');
  if (quality.blurry) messages.push('La foto se ve borrosa; sostén firme la cámara.');
  if (quality.dark) messages.push('La foto está oscura; busca mejor luz.');
  return messages;
}

function canvasFor(
  width: number,
  height: number
): {
  canvas: HTMLCanvasElement;
  context: CanvasRenderingContext2D;
} {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext('2d', { willReadFrequently: true });
  if (!context) throw new Error('canvas_unavailable');
  return { canvas, context };
}

/**
 * Re-encoding always yields a clean JPEG: it drops EXIF data such as the GPS
 * position, avoids the trailing bytes some phones add, and keeps uploads small.
 */
export async function prepareImage(source: Blob, side: 'front' | 'back'): Promise<PreparedImage> {
  // `from-image` respeta la orientación con que el teléfono guardó la foto.
  const bitmap = await createImageBitmap(source, { imageOrientation: 'from-image' });
  try {
    const size = fitWithin(bitmap.width, bitmap.height, MAX_EDGE);
    const { canvas, context } = canvasFor(size.width, size.height);
    context.drawImage(bitmap, 0, 0, size.width, size.height);

    const analysisSize = fitWithin(bitmap.width, bitmap.height, ANALYSIS_EDGE);
    const analysis = canvasFor(analysisSize.width, analysisSize.height);
    analysis.context.drawImage(bitmap, 0, 0, analysisSize.width, analysisSize.height);
    const pixels = analysis.context.getImageData(0, 0, analysisSize.width, analysisSize.height);
    const quality = assessQuality(
      toGrey(pixels.data),
      analysisSize.width,
      bitmap.width,
      bitmap.height
    );

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, 'image/jpeg', JPEG_QUALITY)
    );
    if (!blob) throw new Error('image_encode_failed');
    return { file: new File([blob], `licencia-${side}.jpg`, { type: 'image/jpeg' }), quality };
  } finally {
    bitmap.close();
  }
}
