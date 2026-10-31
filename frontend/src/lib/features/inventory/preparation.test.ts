import { describe, expect, it } from 'vitest';
import { preparationQuantityIssue } from './preparation';
describe('cantidad de preparación', () => {
  it.each(['', '0', '-1', '51', 'NaN', '1.1234567', '1,5'])(
    'rechaza cantidad inválida %s',
    (value) => {
      expect(preparationQuantityIssue(value, 50)).not.toBeNull();
    }
  );
  it.each(['30', '50', '0.000001'])('acepta una cantidad válida %s', (value) => {
    expect(preparationQuantityIssue(value, 50)).toBeNull();
  });
});
