const { test, describe } = require('node:test');
const assert = require('node:assert/strict');
require('../_setup');

const catalogs = require('../../src/config/catalogs');

describe('catalogs.js', () => {
  test('carga los 33 catálogos oficiales', () => {
    const ids = Object.keys(catalogs.catalogosRaw);
    assert.equal(ids.length, 33);
  });

  test('coincide con los conteos limpios del Excel oficial del 1 de julio', () => {
    const expectedCounts = {
      'CAT-001': 2, 'CAT-002': 13, 'CAT-003': 2, 'CAT-004': 2, 'CAT-005': 5,
      'CAT-006': 3, 'CAT-007': 2, 'CAT-008': 263, 'CAT-009': 4, 'CAT-010': 6,
      'CAT-011': 4, 'CAT-012': 15, 'CAT-013': 45, 'CAT-014': 40, 'CAT-015': 49,
      'CAT-016': 3, 'CAT-017': 12, 'CAT-018': 3, 'CAT-019': 774, 'CAT-020': 249,
      'CAT-021': 4, 'CAT-022': 5, 'CAT-023': 2, 'CAT-024': 3, 'CAT-025': 5,
      'CAT-026': 3, 'CAT-027': 48, 'CAT-028': 90, 'CAT-029': 2, 'CAT-030': 6,
      'CAT-031': 11, 'CAT-032': 2, 'CAT-033': 4,
    };
    const actualCounts = Object.fromEntries(
      Object.entries(catalogs.catalogosRaw).map(([id, catalog]) => [id, catalog.entradas.length])
    );
    assert.deepEqual(actualCounts, expectedCounts);
    assert.equal(Object.values(actualCounts).reduce((total, count) => total + count, 0), 1681);
  });

  test('no conserva encabezados, notas ni códigos vacíos como entradas', () => {
    for (const [id, catalog] of Object.entries(catalogs.catalogosRaw)) {
      for (const entry of catalog.entradas) {
        assert.ok(entry.codigo.trim(), `${id} contiene código vacío`);
        assert.ok(entry.valor.trim(), `${id} contiene valor vacío`);
      }
    }
    assert.equal(catalogs.esCodigoValido('CAT-019', ''), false);
    assert.equal(catalogs.esCodigoValido('CAT-014', '1: Unidad de medida que se utilizará según el Reglamento Técnico Salvadoreño RTS. 01.02.01:18 Metrología (SI).'), false);
  });

  test('preserva NA como código oficial de Namibia', () => {
    assert.equal(catalogs.esCodigoValido('CAT-020', 'NA'), true);
    assert.equal(catalogs._mapaCodigoValor('CAT-020').NA, 'Namibia');
  });

  test('esCodigoValido reconoce un código real de CAT-002 (tipo de DTE)', () => {
    assert.equal(catalogs.esCodigoValido('CAT-002', '01'), true);
    assert.equal(catalogs.esCodigoValido('CAT-002', '99'), false);
  });

  test('esCodigoValido devuelve false para un catálogo inexistente', () => {
    assert.equal(catalogs.esCodigoValido('CAT-999', '01'), false);
  });

  test('distritosDeDepartamento agrupa correctamente por departamento', () => {
    // San Salvador (06) tiene 19 municipios/distritos según CAT-013/CAT-008.
    const distritosSanSalvador = catalogs.distritosDeDepartamento('06');
    assert.equal(distritosSanSalvador.length, 19);
    assert.ok(distritosSanSalvador.some((d) => d.valor === 'SAN SALVADOR'));
  });

  test('distritosDeDepartamento no repite entre departamentos distintos', () => {
    const ahuachapan = catalogs.distritosDeDepartamento('01');
    const chalatenango = catalogs.distritosDeDepartamento('04');
    // Ambos catálogos tienen un código "01" pero deben significar municipios distintos.
    const d1 = ahuachapan.find((d) => d.codigo === '01');
    const d2 = chalatenango.find((d) => d.codigo === '01');
    assert.notEqual(d1.valor, d2.valor);
  });

  test('TIPO_ESTABLECIMIENTO_LETRA mapea correctamente CAT-009', () => {
    assert.equal(catalogs.TIPO_ESTABLECIMIENTO_LETRA['01'], 'S'); // Sucursal
    assert.equal(catalogs.TIPO_ESTABLECIMIENTO_LETRA['02'], 'M'); // Casa Matriz
    assert.equal(catalogs.TIPO_ESTABLECIMIENTO_LETRA['04'], 'B'); // Bodega
    assert.equal(catalogs.TIPO_ESTABLECIMIENTO_LETRA['07'], 'P'); // Patio
  });

  test('TIPO_DTE cubre los 11 tipos de documento implementados', () => {
    const codigos = Object.values(catalogs.TIPO_DTE);
    for (const c of ['01', '03', '04', '05', '06', '07', '08', '09', '11', '14', '15']) {
      assert.ok(codigos.includes(c), `falta el código ${c} en TIPO_DTE`);
    }
  });
});
