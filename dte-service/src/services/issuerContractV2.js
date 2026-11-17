const crypto = require('node:crypto');
const config = require('../config');

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, canonicalize(item)]));
  }
  return value;
}

function fail(code, message) {
  const error = new Error(message);
  error.code = code;
  throw error;
}

function validateIssuerV2(emisor) {
  if (!emisor || typeof emisor !== 'object') fail('INVALID_ISSUER', 'El contrato v2 requiere emisor');
  const required = ['revisionId', 'snapshotSha256', 'nit', 'nrc', 'nombre', 'codActividad', 'descActividad', 'telefono', 'correo', 'tipoEstablecimiento', 'codEstablecimientoMH', 'codPuntoVentaMH'];
  if (required.some((field) => typeof emisor[field] !== 'string' || !emisor[field].trim())) fail('INVALID_ISSUER', 'El emisor v2 está incompleto');
  if (!emisor.direccion || ['departamento', 'municipio', 'distrito', 'complemento'].some((field) => typeof emisor.direccion[field] !== 'string' || !emisor.direccion[field].trim())) {
    fail('INVALID_ISSUER', 'La dirección del emisor v2 está incompleta');
  }
  if (!/^(\d{9}|\d{14})$/.test(emisor.nit) || !/^\d{2,8}$/.test(emisor.nrc)) fail('INVALID_ISSUER', 'NIT o NRC del emisor inválido');
  // Se requiere aquí para evitar el ciclo config -> db -> registro al cargar.
  if (!require('./issuerRegistry').autorizado(emisor.nit)) fail('UNAUTHORIZED_ISSUER', 'El NIT del emisor no está autorizado en este ambiente');
  // El firmador firma con el certificado {MH_NIT}.crt y Hacienda autentica con
  // ese NIT: un snapshot con otro NIT produciría una firma que no corresponde.
  if (config.dteMode !== 'simulated' && emisor.nit !== config.emisor?.nit) {
    fail('UNAUTHORIZED_ISSUER', 'El NIT del emisor no coincide con el NIT del certificado configurado (MH_NIT)');
  }

  const canonical = {
    legalName: emisor.nombre, tradeName: emisor.nombreComercial ?? null, nit: emisor.nit, nrc: emisor.nrc,
    economicActivityCode: emisor.codActividad, economicActivityDescription: emisor.descActividad,
    activityCatalogVersion: emisor.activityCatalogVersion,
    address: {
      departmentCode: emisor.direccion.departamento, departmentName: emisor.direccion.departmentName,
      municipalityCode: emisor.direccion.municipio, municipalityName: emisor.direccion.municipalityName,
      districtCode: emisor.direccion.distrito, districtName: emisor.direccion.districtName,
      complement: emisor.direccion.complemento, geoCatalogVersion: emisor.direccion.geoCatalogVersion,
    },
    phone: emisor.telefono, email: emisor.correo, establishmentType: emisor.tipoEstablecimiento,
    mhEstablishmentCode: emisor.codEstablecimientoMH, mhPointOfSaleCode: emisor.codPuntoVentaMH,
    internalEstablishmentCode: emisor.codEstable ?? null, internalPointOfSaleCode: emisor.codPuntoVenta ?? null,
  };
  const actual = crypto.createHash('sha256').update(JSON.stringify(canonicalize(canonical))).digest('hex');
  if (actual !== emisor.snapshotSha256) fail('ISSUER_HASH_MISMATCH', 'El hash del snapshot del emisor no coincide');
  return emisor;
}

module.exports = { validateIssuerV2 };
