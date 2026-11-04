import { describe, expect, it } from 'vitest';
import {
  assessQuality,
  cameraCropSize,
  fitWithin,
  guideCrop,
  measureImage,
  QUALITY_MESSAGES,
  toGrey,
  type ImageMetrics
} from '$lib/features/document-capture/image-prep';
import {
  confirmBlocker as confirmBlockerFor,
  fieldsToReview as fieldsToReviewIn,
  issuesFor,
  isWaiting,
  mergeExtracted,
  unreadFields as unreadFieldsFor,
  warningCodes
} from '$lib/features/document-capture/review';
import type { CaptureIssue, CaptureValues } from '$lib/features/document-capture/types';
import { EMPTY_VALUES, licenseCaptureRules } from './license-config';

const fieldsToReview = (issues: CaptureIssue[]) =>
  fieldsToReviewIn(issues, licenseCaptureRules.groups);
const confirmBlocker = (state: Parameters<typeof confirmBlockerFor>[0]) =>
  confirmBlockerFor(state, licenseCaptureRules);
const unreadFields = (
  values: CaptureValues,
  issues: CaptureIssue[],
  capture: { front: { extracted: boolean }; back: { extracted: boolean } },
  touched: ReadonlySet<string>
) => unreadFieldsFor(values, issues, capture, touched, licenseCaptureRules);

/** Mostly white card with dark text in the middle, as the camera would see a license. */
function card(width = 240, height = 160, paper = 250, ink = 20): Uint8ClampedArray {
  const grey = new Uint8ClampedArray(width * height).fill(paper);
  for (let y = 12; y < height - 12; y += 6) {
    for (let x = 12; x < width - 12; x++) {
      if ((x >> 2) % 2 === 0) grey[y * width + x] = ink;
    }
  }
  return grey;
}

const GOOD: ImageMetrics = { sharpness: 2000, darkTone: 40, lightTone: 250, glare: 2, fill: 90 };

describe('fitWithin', () => {
  it('scales the long edge down keeping the proportion', () => {
    expect(fitWithin(4000, 3000, 2000)).toEqual({ width: 2000, height: 1500 });
    expect(fitWithin(3000, 4000, 2000)).toEqual({ width: 1500, height: 2000 });
  });

  it('never enlarges a small photo', () => {
    expect(fitWithin(800, 600, 2000)).toEqual({ width: 800, height: 600 });
  });
});

describe('image quality', () => {
  it('converts rgba to grey', () => {
    expect(Array.from(toGrey(new Uint8ClampedArray([255, 255, 255, 255, 0, 0, 0, 255])))).toEqual([
      255, 0
    ]);
  });

  it('accepts a good photo', () => {
    expect(assessQuality(GOOD, 2000, 1500)).toEqual([]);
  });

  it.each([
    ['too_small', { ...GOOD }, 300, 200],
    ['too_far', { ...GOOD, fill: 18 }, 2000, 1500],
    ['blurry', { ...GOOD, sharpness: 60 }, 2000, 1500],
    ['dark', { ...GOOD, lightTone: 127 }, 2000, 1500],
    ['overexposed', { ...GOOD, darkTone: 120 }, 2000, 1500],
    ['glare', { ...GOOD, glare: 16 }, 2000, 1500]
  ] as const)('detects %s and has a message for it', (issue, metrics, width, height) => {
    expect(assessQuality(metrics, width, height)).toEqual([issue]);
    expect(QUALITY_MESSAGES[issue].title).toBeTruthy();
    expect(QUALITY_MESSAGES[issue].hint).toBeTruthy();
  });

  it('does not take the blank areas of a clean back for a reflection', () => {
    expect(assessQuality({ ...GOOD, glare: 9.4 }, 1582, 994)).toEqual([]);
  });

  it('puts what matters most first, since only one instruction is shown', () => {
    const issues = assessQuality({ ...GOOD, sharpness: 1, lightTone: 50, fill: 10 }, 300, 200);

    expect(issues).toEqual(['too_small', 'too_far', 'blurry', 'dark']);
  });

  it('measures a sharp card as sharp and a flat image as having no detail', () => {
    const sharp = measureImage(card(), 240, 160);
    const flat = measureImage(new Uint8ClampedArray(240 * 160).fill(120), 240, 160);

    expect(sharp.sharpness).toBeGreaterThan(100);
    expect(sharp.fill).toBeGreaterThan(40);
    expect(flat.sharpness).toBe(0);
    expect(flat.fill).toBe(0);
  });

  it('does not take the white of the card for a reflection', () => {
    expect(measureImage(card(), 240, 160).glare).toBeLessThan(12);
  });

  it('finds a burnt-out patch over the printed data', () => {
    const grey = card();
    for (let y = 50; y < 120; y++) {
      for (let x = 70; x < 170; x++) grey[y * 240 + x] = 255;
    }

    expect(measureImage(grey, 240, 160).glare).toBeGreaterThanOrEqual(12);
  });

  it('judges sharpness at the centre, so a crisp table cannot hide a blurry card', () => {
    const grey = new Uint8ClampedArray(240 * 160).fill(200);
    for (let y = 0; y < 160; y++) {
      for (let x = 0; x < 240; x++) {
        const outside = x < 30 || x >= 210 || y < 20 || y >= 140;
        if (outside && (x + y) % 2) grey[y * 240 + x] = 0;
      }
    }

    expect(measureImage(grey, 240, 160).sharpness).toBeLessThan(100);
  });

  it('reads the tones of the light and dark ends', () => {
    const metrics = measureImage(card(240, 160, 120, 20), 240, 160);

    expect(metrics.lightTone).toBe(120);
    expect(metrics.darkTone).toBe(20);
  });

  it('tolerates images too small to measure', () => {
    expect(measureImage(new Uint8ClampedArray(4), 2, 2).sharpness).toBe(0);
  });
});

describe('cameraCropSize', () => {
  it('lifts the crop of a modest camera to the minimum, keeping the proportion', () => {
    expect(cameraCropSize(458, 289)).toEqual({ width: 640, height: 404 });
  });

  it('leaves a large crop as it is', () => {
    expect(cameraCropSize(1100, 694)).toEqual({ width: 1100, height: 694 });
  });
});

describe('guideCrop', () => {
  it('maps the guide to video pixels when the video is cropped at the sides', () => {
    // 1920x1080 mostrado en 375x500 con cover: escala 500/1080 y sobra ancho.
    const area = guideCrop(
      { width: 1920, height: 1080 },
      { x: 0, y: 100, width: 375, height: 500 },
      { x: 25, y: 250, width: 325, height: 200 }
    );
    const scale = 500 / 1080;

    expect(area.y).toBeCloseTo(150 / scale);
    expect(area.width).toBeCloseTo(325 / scale);
    expect(area.height).toBeCloseTo(200 / scale);
    expect(area.x).toBeCloseTo((1920 - 375 / scale) / 2 + 25 / scale);
  });

  it('never leaves the video', () => {
    const area = guideCrop(
      { width: 100, height: 100 },
      { x: 0, y: 0, width: 100, height: 100 },
      { x: -10, y: 90, width: 200, height: 50 }
    );

    expect(area.x).toBe(0);
    expect(area.width).toBeLessThanOrEqual(100);
    expect(area.y + area.height).toBeLessThanOrEqual(100);
  });
});

describe('unreadFields', () => {
  const read = { front: { extracted: true }, back: { extracted: true } };
  const complete = {
    ...EMPTY_VALUES,
    expires: '02-2027',
    number: '0101-010101-101-1',
    dui: '12345678-4',
    issued: '25.02.2023'
  };

  it('finds nothing when the model read everything', () => {
    expect(unreadFields(complete, [], read, new Set())).toEqual([]);
  });

  it('reports empty values, and values it read as nonsense', () => {
    const issue = {
      code: 'expiry_invalid',
      severity: 'error',
      field: 'expires',
      message: ''
    } as const;

    expect(
      unreadFields({ ...complete, expires: 'Expires', dui: null }, [issue], read, new Set())
    ).toEqual(['expires', 'dui']);
  });

  it('ignores a side that has not been read yet', () => {
    const onlyFront = { front: { extracted: true }, back: { extracted: false } };

    expect(unreadFields({ ...complete, issued: null }, [], onlyFront, new Set())).toEqual([]);
  });

  it('stops asking once the user typed the value', () => {
    expect(unreadFields({ ...complete, dui: null }, [], read, new Set(['dui'] as const))).toEqual(
      []
    );
  });
});

describe('mergeExtracted', () => {
  it('fills what the user has not touched', () => {
    const merged = mergeExtracted(
      { ...EMPTY_VALUES },
      { ...EMPTY_VALUES, number: 'A', dui: 'B' },
      new Set()
    );

    expect(merged.number).toBe('A');
    expect(merged.dui).toBe('B');
  });

  it('never overwrites what the user typed, even with a late result', () => {
    const merged = mergeExtracted(
      { ...EMPTY_VALUES, number: 'escrito' },
      { ...EMPTY_VALUES, number: 'leído', dui: 'B' },
      new Set(['number'] as const)
    );

    expect(merged.number).toBe('escrito');
    expect(merged.dui).toBe('B');
  });

  it('does not erase a value when the model returned nothing for it', () => {
    const merged = mergeExtracted(
      { ...EMPTY_VALUES, number: 'previo' },
      { ...EMPTY_VALUES },
      new Set()
    );

    expect(merged.number).toBe('previo');
  });
});

describe('review helpers', () => {
  const issues = [
    { code: 'a', severity: 'warning', field: 'dui', message: 'x' },
    { code: 'b', severity: 'mismatch', field: 'dui', message: 'y' },
    { code: 'c', severity: 'error', field: 'expires', message: 'z' }
  ] as const;

  it('groups issues by field', () => {
    expect(issuesFor([...issues], 'dui').map((item) => item.code)).toEqual(['a', 'b']);
  });

  it('acknowledges only warnings', () => {
    expect(warningCodes([...issues])).toEqual(['a']);
  });

  it('knows when the model is still working', () => {
    expect(isWaiting('pending')).toBe(true);
    expect(isWaiting('processing')).toBe(true);
    expect(isWaiting('ready')).toBe(false);
  });
});

describe('fieldsToReview', () => {
  it('lists flagged fields once, in form order', () => {
    const issues = [
      { code: 'a', severity: 'warning', field: 'expires', message: 'x' },
      { code: 'b', severity: 'warning', field: 'dui', message: 'y' },
      { code: 'c', severity: 'mismatch', field: 'dui', message: 'z' }
    ] as const;

    expect(fieldsToReview([...issues])).toEqual(['dui', 'expires']);
  });
});

describe('confirmBlocker', () => {
  const ready = {
    photosReady: true,
    issues: [],
    acknowledged: false,
    canOverride: false,
    overrideReason: ''
  };
  const issue = (severity: 'error' | 'mismatch' | 'warning') => ({
    code: severity,
    severity,
    field: 'dui',
    message: ''
  });

  it('allows confirming when nothing is pending', () => {
    expect(confirmBlocker(ready)).toBeNull();
  });

  it('explains each thing that blocks, most serious first', () => {
    expect(confirmBlocker({ ...ready, photosReady: false })).toMatch(/fotos/);
    expect(confirmBlocker({ ...ready, issues: [issue('error'), issue('warning')] })).toMatch(
      /Corrige/
    );
    expect(confirmBlocker({ ...ready, issues: [issue('mismatch')] })).toMatch(/no coinciden/);
    expect(confirmBlocker({ ...ready, issues: [issue('mismatch')], canOverride: true })).toMatch(
      /motivo/
    );
    expect(confirmBlocker({ ...ready, issues: [issue('warning')] })).toMatch(/avisos/);
  });

  it('clears once warnings are acknowledged and a reason is given', () => {
    expect(
      confirmBlocker({
        ...ready,
        issues: [issue('mismatch'), issue('warning')],
        acknowledged: true,
        canOverride: true,
        overrideReason: 'Error en expediente'
      })
    ).toBeNull();
  });
});
