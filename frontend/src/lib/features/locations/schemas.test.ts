import { describe, expect, it } from 'vitest';
import { axisSize, batchCardinality, validateLocationDraft } from './schemas';
import type { LocationDraft } from './types';

const validDraft = (): LocationDraft => ({
  area: ' Picking ',
  aisle: ' A ',
  rack: '03',
  level: '02',
  position: '04',
  capacity: '25',
  notes: '',
  location_type: 'standard',
  lifecycle_status: 'active',
  pick_sequence: '10',
  putaway_sequence: '',
  external_id: '',
  barcode: '',
  verification_code: ''
});

describe('location schemas', () => {
  it('normaliza el formulario y convierte campos numéricos sin aceptar un código manual', () => {
    const result = validateLocationDraft(validDraft());
    expect(result.success).toBe(true);
    if (!result.success) return;
    expect(result.data).toMatchObject({
      area: 'Picking',
      aisle: 'A',
      capacity: 25,
      pick_sequence: 10,
      putaway_sequence: null
    });
    expect(result.data).not.toHaveProperty('code');
  });

  it('acepta los números que entregan los inputs HTML de tipo number', () => {
    const result = validateLocationDraft({
      ...validDraft(),
      capacity: 20,
      pick_sequence: 3,
      putaway_sequence: 0
    });

    expect(result.success).toBe(true);
    if (!result.success) return;
    expect(result.data).toMatchObject({ capacity: 20, pick_sequence: 3, putaway_sequence: 0 });
  });

  it('entrega errores asociados a campos para capacidad y coordenadas inválidas', () => {
    const result = validateLocationDraft({ ...validDraft(), aisle: '', capacity: '1.5' });
    expect(result.success).toBe(false);
    if (result.success) return;
    expect(result.errors.aisle).toContain('obligatorio');
    expect(result.errors.capacity).toContain('entero');
  });

  it('calcula rangos alfabéticos, numéricos y cardinalidad cartesiana', () => {
    expect(axisSize({ key: 'aisle', start: 'A', end: 'D' })).toBe(4);
    expect(axisSize({ key: 'rack', start: '1', end: '10', step: 2 })).toBe(5);
    expect(axisSize({ key: 'rack', start: 'A01', end: 'A10' })).toBe(10);
    expect(
      batchCardinality([
        { key: 'aisle', start: 'A', end: 'B' },
        { key: 'rack', start: '1', end: '10' },
        { key: 'level', start: '1', end: '4' },
        { key: 'position', values: ['1', '2'] }
      ])
    ).toBe(160);
  });

  it('rechaza rangos invertidos, valores repetidos y notación numérica ambigua', () => {
    expect(axisSize({ key: 'aisle', start: 'D', end: 'A' })).toBe(0);
    expect(axisSize({ key: 'position', values: ['01', '01', '02'] })).toBe(0);
    expect(axisSize({ key: 'position', values: ['01', '', '02'] })).toBe(0);
    expect(axisSize({ key: 'rack', start: '1e1', end: '1e3' })).toBe(0);
    expect(axisSize({ key: 'rack', start: '1.1', end: '1.9' })).toBe(0);
    expect(axisSize({ key: 'rack', start: 'A01', end: 'B10' })).toBe(0);
    expect(axisSize({ key: 'rack', start: 'A01', end: 'A10', step: 1.5 })).toBe(0);
  });
});
