const { catalogosRaw, distritosDeDepartamento, TIPO_ESTABLECIMIENTO_LETRA } = require('../config/catalogs');

/**
 * Nombres legibles de los códigos de catálogo para la representación gráfica.
 * Son funciones puras: nunca lanzan, y si un código no existe en el catálogo
 * oficial devuelven el código tal cual (el PDF debe generarse aunque Hacienda
 * agregue un código nuevo antes de que se regenere catalogos.json).
 */

const _mapas = new Map();

function _normalizar(texto) {
  return String(texto ?? '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toUpperCase()
    .replace(/\s+/g, ' ')
    .trim();
}

function _vacio(codigo) {
  return codigo === null || codigo === undefined || String(codigo).trim() === '';
}

function _mapaDe(catId) {
  if (!_mapas.has(catId)) {
    const mapa = new Map();
    // Si un código aparece repetido (CAT-015 repite D4), gana la primera entrada.
    for (const { codigo, valor } of catalogosRaw[catId]?.entradas || []) {
      if (!mapa.has(String(codigo))) mapa.set(String(codigo), valor);
    }
    _mapas.set(catId, mapa);
  }
  return _mapas.get(catId);
}

function nombreEnCatalogo(catId, codigo) {
  if (_vacio(codigo)) return null;
  return _mapaDe(catId).get(String(codigo)) ?? String(codigo);
}

const nombreTipoDte = (codigo) => nombreEnCatalogo('CAT-002', codigo);
const nombreDepartamento = (codigo) => nombreEnCatalogo('CAT-012', codigo);
const nombreTipoDocumentoIdentificacion = (codigo) => nombreEnCatalogo('CAT-022', codigo);
const nombreFormaPago = (codigo) => nombreEnCatalogo('CAT-017', codigo);
const nombreTipoGeneracion = (codigo) => nombreEnCatalogo('CAT-007', codigo);
const nombreDocumentoAsociado = (codigo) => nombreEnCatalogo('CAT-021', codigo);
const nombreTributo = (codigo) => nombreEnCatalogo('CAT-015', codigo);
const nombreContingencia = (codigo) => nombreEnCatalogo('CAT-005', codigo);
const nombreCondicionOperacion = (codigo) => nombreEnCatalogo('CAT-016', codigo);
const nombreRetencionIva = (codigo) => nombreEnCatalogo('CAT-006', codigo);
const nombreTipoDonacion = (codigo) => nombreEnCatalogo('CAT-026', codigo);
const nombrePais = (codigo) => nombreEnCatalogo('CAT-020', codigo);
const nombreTipoInvalidacion = (codigo) => nombreEnCatalogo('CAT-024', codigo);

/** CAT-014 trae llamadas a notas al pie pegadas al nombre ("Galón 1, 4", "Otra 6"). */
function nombreUnidadMedida(codigo) {
  const nombre = nombreEnCatalogo('CAT-014', codigo);
  if (nombre === null || nombre === String(codigo)) return nombre;
  return nombre.replace(/\s+\d+(?:,\s*\d+)*$/, '');
}

/**
 * CAT-013 es una lista plana donde los códigos de municipio se repiten entre
 * departamentos ("23" es LA LIBERTAD NORTE, SAN SALVADOR CENTRO y LA PAZ
 * OESTE). Todos los nombres empiezan con el nombre de su departamento, así
 * que se desambigua comparando ese prefijo sin tildes.
 */
function nombreMunicipio(codDepartamento, codMunicipio) {
  if (_vacio(codMunicipio)) return null;
  const departamento = _normalizar(nombreDepartamento(codDepartamento));
  const candidato = (catalogosRaw['CAT-013']?.entradas || []).find((entrada) => {
    if (entrada.codigo !== String(codMunicipio)) return false;
    const nombre = _normalizar(entrada.valor);
    return departamento !== '' && (nombre === departamento || nombre.startsWith(`${departamento} `));
  });
  return candidato ? candidato.valor : String(codMunicipio);
}

/** CAT-008 agrupa los distritos por departamento porque sus códigos se repiten. */
function nombreDistrito(codDepartamento, codDistrito) {
  if (_vacio(codDistrito)) return null;
  const entrada = distritosDeDepartamento(String(codDepartamento ?? '')).find((e) => e.codigo === String(codDistrito));
  return entrada ? entrada.valor : String(codDistrito);
}

/** "Complemento, DISTRITO, MUNICIPIO, DEPARTAMENTO" con los códigos ya traducidos. */
function direccionLegible(direccion) {
  if (!direccion) return null;
  const { departamento, municipio, distrito, complemento } = direccion;
  const partes = [
    complemento,
    nombreDistrito(departamento, distrito),
    nombreMunicipio(departamento, municipio),
    _vacio(departamento) ? null : nombreDepartamento(departamento).toUpperCase(),
  ].map((parte) => (parte === null || parte === undefined ? '' : String(parte).trim())).filter(Boolean);
  return partes.length > 0 ? partes.join(', ') : null;
}

/**
 * El emisor no trae tipoEstablecimiento en el JSON, pero el número de control
 * lo codifica: DTE-01-M001P001-... donde M/S/B/P corresponde a CAT-009.
 */
function tipoEstablecimientoDesdeNumeroControl(numeroControl) {
  const coincidencia = /^DTE-\d{2}-([MSBP])\d{3}P\d{3}-\d{15}$/.exec(String(numeroControl ?? ''));
  if (!coincidencia) return null;
  const codigo = Object.keys(TIPO_ESTABLECIMIENTO_LETRA).find((cod) => TIPO_ESTABLECIMIENTO_LETRA[cod] === coincidencia[1]);
  return codigo ? nombreEnCatalogo('CAT-009', codigo) : null;
}

module.exports = {
  nombreEnCatalogo,
  nombreTipoDte,
  nombreDepartamento,
  nombreMunicipio,
  nombreDistrito,
  direccionLegible,
  nombreUnidadMedida,
  nombreTipoDocumentoIdentificacion,
  nombreFormaPago,
  nombreTipoGeneracion,
  nombreDocumentoAsociado,
  nombreTributo,
  nombreContingencia,
  nombreCondicionOperacion,
  nombreRetencionIva,
  nombreTipoDonacion,
  nombrePais,
  nombreTipoInvalidacion,
  tipoEstablecimientoDesdeNumeroControl,
};
