require('../setup-env');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const { describe, test } = require('node:test');
const { validateIssuerV2 } = require('../../src/services/issuerContractV2');
const { construirFactura } = require('../../src/services/dteBuilder');

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, canonicalize(item)]));
  return value;
}

function fixture() {
  const canonical = { legalName: 'Mi Empresa de Pruebas S.A. de C.V.', tradeName: 'Mi Empresa', nit: process.env.MH_NIT, nrc: '1234567', economicActivityCode: '62010', economicActivityDescription: 'Programación informática', activityCatalogVersion: 'CAT-019', address: { departmentCode: '06', departmentName: 'San Salvador', municipalityCode: '23', municipalityName: 'San Salvador Centro', districtCode: '14', districtName: 'San Salvador', complement: 'Calle Principal #123', geoCatalogVersion: 'GEO-1' }, phone: '22221111', email: 'facturacion@miempresa.com', establishmentType: '02', mhEstablishmentCode: '001', mhPointOfSaleCode: '001', internalEstablishmentCode: 'CASA', internalPointOfSaleCode: null };
  return { revisionId: 'revision-1', snapshotSha256: crypto.createHash('sha256').update(JSON.stringify(canonicalize(canonical))).digest('hex'), nit: canonical.nit, nrc: canonical.nrc, nombre: canonical.legalName, nombreComercial: canonical.tradeName, codActividad: canonical.economicActivityCode, descActividad: canonical.economicActivityDescription, activityCatalogVersion: canonical.activityCatalogVersion, direccion: { departamento: '06', departmentName: 'San Salvador', municipio: '23', municipalityName: 'San Salvador Centro', distrito: '14', districtName: 'San Salvador', complemento: 'Calle Principal #123', geoCatalogVersion: 'GEO-1' }, telefono: canonical.phone, correo: canonical.email, tipoEstablecimiento: '02', codEstablecimientoMH: '001', codPuntoVentaMH: '001', codEstable: 'CASA', codPuntoVenta: null };
}

describe('issuerContractV2', () => {
  test('acepta un snapshot autorizado cuyo hash coincide', () => { const issuer = fixture(); assert.equal(validateIssuerV2(issuer), issuer); });
  test('rechaza cambios posteriores al snapshot', () => { assert.throws(() => validateIssuerV2({ ...fixture(), nombre: 'Alterado' }), (error) => error.code === 'ISSUER_HASH_MISMATCH'); });
  test('rechaza un NIT fuera de la allowlist', () => { const issuer = fixture(); assert.throws(() => validateIssuerV2({ ...issuer, nit: '06140000000000' }), (error) => error.code === 'UNAUTHORIZED_ISSUER'); });
  test('el builder 01 usa el emisor del snapshot y produce un DTE válido', () => {
    const issuer = fixture();
    const { dte } = construirFactura({ emisor: issuer, receptor: null, items: [{ descripcion: 'Producto', cantidad: 1, precioUni: 10, ventaGravada: 10 }] });
    assert.equal(dte.emisor.nombre, issuer.nombre);
    assert.equal(dte.identificacion.numeroControl.slice(7, 15), 'M001P001');
  });
});
