const catalogosRaw = require('./catalogos.json');

/**
 * Catálogos oficiales completos del Ministerio de Hacienda (El Salvador),
 * generados a partir de "Catálogos – Facturación Electrónica V1.1"
 * (Excel oficial, actualizado 1 julio 2026).
 *
 * Estructura de catalogosRaw: { "CAT-0XX": { titulo, entradas: [{codigo, valor}], ... } }
 *
 * IMPORTANTE: Hacienda actualiza estos catálogos periódicamente (ver control de
 * versiones dentro del documento oficial). Cuando publiquen una nueva versión,
 * reemplaza /src/config/catalogos.json regenerándolo desde el Excel oficial
 * (no lo edites a mano para evitar errores de transcripción).
 */

function _mapaCodigoValor(catId) {
  const cat = catalogosRaw[catId];
  if (!cat) throw new Error(`Catálogo ${catId} no encontrado`);
  const mapa = {};
  for (const { codigo, valor } of cat.entradas) mapa[codigo] = valor;
  return mapa;
}

function esCodigoValido(catId, codigo) {
  const cat = catalogosRaw[catId];
  if (!cat) return false;
  return cat.entradas.some((e) => e.codigo === String(codigo));
}

/** CAT-008 Distrito está agrupado por departamento porque los códigos se repiten entre departamentos. */
function distritosDeDepartamento(codDepartamento) {
  const cat = catalogosRaw['CAT-008'];
  return cat.entradas_por_departamento[codDepartamento] || [];
}

function esDistritoValidoParaDepartamento(codDepartamento, codDistrito) {
  return distritosDeDepartamento(codDepartamento).some((e) => e.codigo === String(codDistrito));
}

// ---- Catálogos de uso frecuente, expuestos como constantes con nombre ----
const TIPO_DTE = Object.freeze({
  FACTURA: '01',
  COMPROBANTE_CREDITO_FISCAL: '03',
  NOTA_REMISION: '04',
  NOTA_CREDITO: '05',
  NOTA_DEBITO: '06',
  COMPROBANTE_RETENCION: '07',
  COMPROBANTE_LIQUIDACION: '08',
  DOCUMENTO_CONTABLE_LIQUIDACION: '09',
  FACTURA_EXPORTACION: '11',
  FACTURA_SUJETO_EXCLUIDO: '14',
  COMPROBANTE_DONACION: '15',
  EVENTO_OPERACIONES_ESPECIALES: '17',
  EVENTO_RETORNO: '18',
});

const AMBIENTE = Object.freeze({
  PRUEBAS: '00',
  PRODUCCION: '01',
});

const MODELO_FACTURACION = Object.freeze({
  PREVIO: 1, // Antes llamado "Normal"
  DIFERIDO: 2,
});

const TIPO_TRANSMISION = Object.freeze({
  NORMAL: 1,
  CONTINGENCIA: 2,
});

const CONDICION_OPERACION = Object.freeze({
  CONTADO: 1,
  CREDITO: 2,
  OTRO: 3,
});

/** CAT-005 Tipo de Contingencia. */
const TIPO_CONTINGENCIA = Object.freeze({
  NO_DISPONIBILIDAD_HACIENDA: 1,
  NO_DISPONIBILIDAD_EMISOR: 2,
  FALLA_INTERNET_EMISOR: 3,
  FALLA_ENERGIA_EMISOR: 4,
  OTRO: 5,
});

/** CAT-024 Motivo del evento (usado como motivo.tipoAnulacion en el Evento de Invalidación). */
const TIPO_ANULACION = Object.freeze({
  ERROR_INFORMACION: 1,
  RESCINDIR_OPERACION: 2,
  OTRO: 3,
});

const TIPO_DOCUMENTO_IDENTIFICACION = Object.freeze({
  NIT: '36',
  DUI: '13',
  OTRO: '37',
  PASAPORTE: '03',
  CARNET_RESIDENTE: '02',
});

/**
 * CAT-009 Tipo de establecimiento -> letra usada en el patrón del Número de
 * Control, confirmado contra el JSON Schema oficial (regex de numeroControl):
 * ^DTE-{tt}-(M|B|S|P)([0-9]{3})(P)([0-9]{3})-[0-9]{15}
 *   M = Casa Matriz (CAT-009 código 02)
 *   B = Bodega       (CAT-009 código 04)
 *   S = Sucursal     (CAT-009 código 01)
 *   P = Patio        (CAT-009 código 07)
 */
const TIPO_ESTABLECIMIENTO_LETRA = Object.freeze({
  '01': 'S', // Sucursal
  '02': 'M', // Casa Matriz
  '04': 'B', // Bodega
  '07': 'P', // Patio
});

module.exports = {
  catalogosRaw,
  _mapaCodigoValor,
  esCodigoValido,
  distritosDeDepartamento,
  esDistritoValidoParaDepartamento,
  TIPO_DTE,
  AMBIENTE,
  MODELO_FACTURACION,
  TIPO_TRANSMISION,
  CONDICION_OPERACION,
  TIPO_CONTINGENCIA,
  TIPO_ANULACION,
  TIPO_DOCUMENTO_IDENTIFICACION,
  TIPO_ESTABLECIMIENTO_LETRA,
};

// Verificación de consistencia contra el catálogo oficial cargado: si algún
// día se regenera catalogos.json con una versión más nueva del Excel y
// Hacienda cambió CAT-024, esto debe fallar ruidosamente al arrancar en vez
// de dejar que TIPO_ANULACION quede desalineado en silencio.
(function _verificarTipoAnulacionContraCatalogoOficial() {
  const cat024 = catalogosRaw['CAT-024'];
  if (!cat024) return; // catálogo no cargado (no debería pasar), no bloquear el require
  for (const [, valorEsperado] of Object.entries(TIPO_ANULACION)) {
    const existe = cat024.entradas.some((e) => Number(e.codigo) === valorEsperado);
    if (!existe) {
      throw new Error(
        `TIPO_ANULACION quedó desalineado con CAT-024 del catálogo oficial (código ${valorEsperado} ya no existe). ` +
          'Revisa src/config/catalogos.json y actualiza TIPO_ANULACION en catalogs.js.'
      );
    }
  }
})();
