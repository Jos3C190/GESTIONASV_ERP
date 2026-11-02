import { describe, expect, it } from 'vitest';
import {
  assessQuality,
  BLUR_THRESHOLD,
  fitWithin,
  laplacianVariance,
  qualityMessages,
  toGrey
} from './image-prep';
import {
  confirmBlocker,
  EMPTY_VALUES,
  fieldsToReview,
  issuesFor,
  isWaiting,
  mergeExtracted,
  warningCodes
} from './review';

function checker(width: number, height: number): Uint8ClampedArray {
  const grey = new Uint8ClampedArray(width * height);
  for (let y = 0; y < height; y++)
    for (let x = 0; x < width; x++) grey[y * width + x] = (x + y) % 2 ? 255 : 0;
  return grey;
}

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
  it('scores sharp detail high and a flat image at zero', () => {
    expect(laplacianVariance(checker(20, 20), 20)).toBeGreaterThan(BLUR_THRESHOLD);
    expect(laplacianVariance(new Uint8ClampedArray(400).fill(120), 20)).toBe(0);
  });

  it('tolerates images too small to measure', () => {
    expect(laplacianVariance(new Uint8ClampedArray(4), 2)).toBe(0);
  });

  it('converts rgba to grey', () => {
    expect(Array.from(toGrey(new Uint8ClampedArray([255, 255, 255, 255, 0, 0, 0, 255])))).toEqual([
      255, 0
    ]);
  });

  it('flags blurry, dark and small photos with a message for each', () => {
    const quality = assessQuality(new Uint8ClampedArray(400).fill(10), 20, 300, 200);

    expect(quality).toEqual({ blurry: true, dark: true, tooSmall: true });
    expect(qualityMessages(quality)).toHaveLength(3);
  });

  it('accepts a sharp, bright, large photo', () => {
    const quality = assessQuality(checker(20, 20), 20, 2000, 1500);

    expect(quality).toEqual({ blurry: false, dark: false, tooSmall: false });
    expect(qualityMessages(quality)).toEqual([]);
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
