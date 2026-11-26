require('dotenv').config();
const { rutaSqlite } = require('./sqlitePath');

const DTE_MODES = ['simulated', 'hacienda-test', 'production'];
const dteMode = (process.env.DTE_MODE || 'hacienda-test').trim().toLowerCase();
if (!DTE_MODES.includes(dteMode)) throw new Error(`DTE_MODE inválido: ${dteMode}`);
if (dteMode === 'simulated' && process.env.DTE_SIMULATION_ACKNOWLEDGED !== 'true') {
  throw new Error('El modo simulated requiere DTE_SIMULATION_ACKNOWLEDGED=true');
}
const simulationScenario = (process.env.DTE_SIMULATION_SCENARIO || 'success').trim();
if (dteMode === 'simulated' && simulationScenario !== 'success') {
  throw new Error('DTE_SIMULATION_SCENARIO global solo admite success; los fallos se eligen por pedido (DEC-010)');
}

/**
 * Escenarios que el backend puede pedir por documento con el header
 * X-DTE-Simulation-Scenario (DEC-010). Solo se aceptan en modo simulated;
 * fuera de él el header se rechaza antes de reservar identidad.
 */
const SIMULATION_ORDER_SCENARIOS = Object.freeze({
  emision: Object.freeze(['success', 'rejected', 'validation-failed']),
  invalidacion: Object.freeze(['success', 'invalidation-rejected']),
});

function required(name, fallback = undefined) {
  const val = process.env[name] ?? fallback;
  if (val === undefined) {
    throw new Error(`Falta la variable de entorno requerida: ${name}`);
  }
  return val;
}

function parseAllowedDocumentTypes(value) {
  const types = (value || '01,03')
    .split(',')
    .map((type) => type.trim())
    .filter(Boolean);
  if (types.length === 0 || types.some((type) => !/^\d{2}$/.test(type))) {
    throw new Error('DTE_ALLOWED_DOCUMENT_TYPES debe contener códigos de DTE de dos dígitos separados por coma');
  }
  return [...new Set(types)];
}

// `simulate` solo da acceso a /api/dte/simulacion, que existe únicamente en modo simulated.
// `issuers` administra el registro de emisores (multiemisor); lo usa el ERP.
const ALL_API_SCOPES = Object.freeze(['issue', 'read', 'invalidate', 'contingency', 'simulate', 'issuers']);

function parseApiKeyScopes(value, keyCount) {
  if (!value || !value.trim()) return Array.from({ length: keyCount }, () => ['issue', 'read']);
  const groups = value.split(';').map((group) => group.trim());
  if (groups.length !== keyCount) {
    throw new Error('MS_API_KEY_SCOPES debe tener un grupo por cada key de MS_API_KEYS, separado por punto y coma');
  }
  return groups.map((group) => {
    const scopes = [...new Set(group.split(',').map((scope) => scope.trim()).filter(Boolean))];
    if (scopes.length === 0 || scopes.some((scope) => !ALL_API_SCOPES.includes(scope))) {
      throw new Error(`MS_API_KEY_SCOPES solo admite: ${ALL_API_SCOPES.join(', ')}`);
    }
    return scopes;
  });
}

const apiKeys = (process.env.MS_API_KEYS || '')
  .split(',')
  .map((k) => k.trim())
  .filter(Boolean);
const apiKeyScopes = parseApiKeyScopes(process.env.MS_API_KEY_SCOPES, apiKeys.length);
// Hacienda y el firmador aceptan NIT de 14 dígitos o de 9 (DUI homologado).
const NIT_REGEX = /^(\d{9}|\d{14})$/;
// Multiemisor: los emisores se registran desde el ERP (tabla `emisores`). La
// lista del entorno queda para despliegues heredados de un solo emisor.
const authorizedIssuerNits = (process.env.DTE_AUTHORIZED_ISSUER_NITS || process.env.MH_NIT || '')
  .split(',').map((nit) => nit.replace(/[\s-]/g, '')).filter(Boolean);
if (authorizedIssuerNits.some((nit) => !NIT_REGEX.test(nit))) {
  throw new Error('DTE_AUTHORIZED_ISSUER_NITS debe contener NIT de 9 o 14 dígitos separados por coma');
}
// Multiemisor (V3d): cada empresa trae su emisor y sus credenciales; el del
// entorno (MH_*) solo existe en despliegues heredados de un solo emisor.
const emisorDelEntorno = Boolean(process.env.MH_NIT?.trim());

/**
 * Cada modo tiene un único ambiente y host oficial (Manual Técnico v2.0,
 * sección 4). Mezclarlos enviaría documentos de prueba a producción o al
 * revés; por eso el arranque falla ante cualquier incoherencia.
 */
const AMBIENTE_POR_MODO = Object.freeze({ 'hacienda-test': '00', production: '01' });
const HOST_POR_MODO = Object.freeze({ 'hacienda-test': 'apitest.dtes.mh.gob.sv', production: 'api.dtes.mh.gob.sv' });
const permitirHostsNoOficiales = process.env.DTE_ALLOW_NON_OFFICIAL_MH_HOSTS === 'true' && dteMode !== 'production';

function ambienteDelModo() {
  if (dteMode === 'simulated') return process.env.MH_AMBIENTE || '00';
  const esperado = AMBIENTE_POR_MODO[dteMode];
  const declarado = process.env.MH_AMBIENTE || (dteMode === 'hacienda-test' ? '00' : undefined);
  if (declarado !== esperado) {
    throw new Error(`MH_AMBIENTE=${declarado ?? '(vacío)'} no corresponde a DTE_MODE=${dteMode}; debe ser ${esperado}`);
  }
  return esperado;
}

/** Rutas oficiales de la API de Hacienda (Manual Técnico v2.0, secciones 4 y 6). */
const RUTAS_HACIENDA = Object.freeze({
  authUrl: ['MH_AUTH_URL', '/seguridad/auth'],
  recepcionUrl: ['MH_RECEPCION_URL', '/fesv/recepciondte'],
  recepcionLoteUrl: ['MH_RECEPCION_LOTE_URL', '/fesv/recepcionlote'],
  anulacionUrl: ['MH_ANULACION_URL', '/fesv/anulardte'],
  contingenciaUrl: ['MH_CONTINGENCIA_URL', '/fesv/contingencia'],
  consultaUrl: ['MH_CONSULTA_URL', '/fesv/recepcion/consultadte'],
  consultaLoteUrl: ['MH_CONSULTA_LOTE_URL', '/fesv/recepcion/consultadtelote'],
});

function urlHacienda(nombre) {
  if (dteMode === 'simulated') return null;
  // Sin la variable se usa la ruta oficial del host del modo del despliegue.
  if (!process.env[nombre]?.trim()) {
    const [, ruta] = Object.values(RUTAS_HACIENDA).find(([variable]) => variable === nombre);
    return `https://${HOST_POR_MODO[dteMode]}${ruta}`;
  }
  const valor = process.env[nombre].trim();
  let url;
  try {
    url = new URL(valor);
  } catch {
    throw new Error(`${nombre} no es una URL válida`);
  }
  if (valor.endsWith('/')) throw new Error(`${nombre} no debe terminar en "/" (Manual Técnico v2.0, sección 6.2)`);
  if (!permitirHostsNoOficiales && (url.protocol !== 'https:' || url.hostname !== HOST_POR_MODO[dteMode])) {
    throw new Error(`${nombre} debe usar https://${HOST_POR_MODO[dteMode]} en DTE_MODE=${dteMode}`);
  }
  return valor;
}

function enteroPositivo(nombre, porDefecto) {
  const valor = Number.parseInt(process.env[nombre] || String(porDefecto), 10);
  if (!Number.isInteger(valor) || valor <= 0) throw new Error(`${nombre} debe ser un entero positivo`);
  return valor;
}

/**
 * Responsable del establecimiento que firma el Evento de Contingencia
 * (Manual Funcional VIII: nombre, tipo y número de documento obligatorios).
 * Sin él, el evento se envía manualmente indicando el responsable.
 */
function responsableContingencia() {
  const nombre = process.env.MH_RESPONSABLE_NOMBRE?.trim();
  const tipoDocumento = process.env.MH_RESPONSABLE_TIPO_DOC?.trim();
  const numeroDocumento = process.env.MH_RESPONSABLE_NUM_DOC?.trim();
  if (!nombre && !tipoDocumento && !numeroDocumento) return null;
  if (!nombre || !tipoDocumento || !numeroDocumento) {
    throw new Error('MH_RESPONSABLE_NOMBRE, MH_RESPONSABLE_TIPO_DOC y MH_RESPONSABLE_NUM_DOC se configuran juntos');
  }
  if (!['36', '13', '02', '03', '37'].includes(tipoDocumento)) {
    throw new Error('MH_RESPONSABLE_TIPO_DOC debe ser un código de CAT-022 (36, 13, 02, 03 o 37)');
  }
  return { nombre, tipoDocumento, numeroDocumento };
}

function tipoContingenciaPorDefecto() {
  const tipo = Number.parseInt(process.env.DTE_CONTINGENCIA_TIPO || '1', 10);
  if (![1, 2, 3, 4].includes(tipo)) {
    throw new Error('DTE_CONTINGENCIA_TIPO debe ser 1, 2, 3 o 4 (el tipo 5 exige describir el motivo en cada caso)');
  }
  return tipo;
}

const nitEmisorEntorno = emisorDelEntorno ? required('MH_NIT').replace(/[\s-]/g, '') : null;
if (emisorDelEntorno && !NIT_REGEX.test(nitEmisorEntorno)) throw new Error('MH_NIT debe tener 9 o 14 dígitos');
if (emisorDelEntorno && !authorizedIssuerNits.includes(nitEmisorEntorno)) {
  throw new Error('MH_NIT debe estar incluido en DTE_AUTHORIZED_ISSUER_NITS (es el NIT del certificado y de las credenciales)');
}

function construirEmisorDelEntorno() {
  return {
    nit: nitEmisorEntorno,
    nrc: required('MH_NRC'),
    nombre: required('MH_NOMBRE'),
    nombreComercial: process.env.MH_NOMBRE_COMERCIAL || null,
    codActividad: required('MH_COD_ACTIVIDAD'),
    descActividad: required('MH_DESC_ACTIVIDAD'),
    telefono: required('MH_TELEFONO'),
    correo: required('MH_CORREO'),
    direccion: {
      departamento: required('MH_DIR_DEPARTAMENTO'),
      municipio: required('MH_DIR_MUNICIPIO'),
      distrito: required('MH_DIR_DISTRITO'),
      complemento: required('MH_DIR_COMPLEMENTO'),
    },
    passwordApi: dteMode === 'simulated' ? null : required('MH_PASSWORD_API'),
    passwordPri: dteMode === 'simulated' ? null : required('MH_PASSWORD_PRI'),
    ambiente: ambienteDelModo(), // 00 = pruebas, 01 = producción; derivado de DTE_MODE
    // Código interno del contribuyente (va en emisor.codEstable/codPuntoVenta
    // del cuerpo del DTE; hasta 4 y 15 caracteres respectivamente, informativo).
    codEstableInterno: process.env.MH_COD_ESTABLE_INTERNO || null,
    codPuntoVentaInterno: process.env.MH_COD_PUNTO_VENTA_INTERNO || null,
    // Códigos OFICIALES asignados por Hacienda vía Formulario F-210 (3 dígitos
    // cada uno). Estos son los que van dentro del Número de Control.
    tipoEstablecimiento: required('MH_TIPO_ESTABLECIMIENTO'), // CAT-009: 01/02/04/07
    codEstablecimientoMH: required('MH_COD_ESTABLECIMIENTO'),
    codPuntoVentaMH: required('MH_COD_PUNTO_VENTA'),
  };
}

/**
 * URLs de Hacienda para el modo de un emisor (V3d). Las del entorno valen
 * para el modo del despliegue; para otro modo se usan las oficiales de su host.
 */
function haciendaPorModo(modo) {
  if (modo === 'simulated') return null;
  if (modo === dteMode) return config.hacienda;
  const urls = Object.fromEntries(
    Object.entries(RUTAS_HACIENDA).map(([clave, [, ruta]]) => [clave, `https://${HOST_POR_MODO[modo]}${ruta}`]),
  );
  return { ...config.hacienda, ...urls };
}

const config = {
  // 00 = pruebas, 01 = producción; derivado de DTE_MODE. Común a todos los emisores del despliegue.
  ambiente: ambienteDelModo(),
  // Emisor heredado (un solo emisor por despliegue). Es null en un despliegue
  // multiemisor en modo simulado: entonces cada solicitud trae su emisor (v2).
  emisor: emisorDelEntorno ? construirEmisorDelEntorno() : null,
  hacienda: {
    authUrl: urlHacienda('MH_AUTH_URL'),
    recepcionUrl: urlHacienda('MH_RECEPCION_URL'),
    recepcionLoteUrl: urlHacienda('MH_RECEPCION_LOTE_URL'),
    anulacionUrl: urlHacienda('MH_ANULACION_URL'),
    contingenciaUrl: urlHacienda('MH_CONTINGENCIA_URL'),
    consultaUrl: urlHacienda('MH_CONSULTA_URL'),
    consultaLoteUrl: urlHacienda('MH_CONSULTA_LOTE_URL'),
    // Umbral de espera de la política de reintentos (Manual Técnico 3.3: 8 s).
    timeoutMs: enteroPositivo('MH_TIMEOUT_MS', 8000),
    userAgent: process.env.MH_USER_AGENT || 'GestionaSV-DTE/2.0',
  },
  firmador: {
    url: dteMode === 'simulated' ? null : required('FIRMADOR_URL'),
  },
  // Certificado de firma (<NIT>.crt): el microservicio solo lee su NIT y su
  // vigencia para la tarjeta «Conexión con Hacienda». Carpeta (montada de solo
  // lectura) o archivo; sin él la tarjeta indica «Certificado no disponible».
  certificado: {
    ruta: process.env.MH_CERT_PATH?.trim() || '/app/certificado',
  },
  // Credenciales de Hacienda por emisor (V3d): contraseñas cifradas con esta
  // clave (32 bytes en base64) y certificados en la carpeta del firmador.
  credenciales: {
    clave: process.env.DTE_CREDENTIALS_KEY?.trim() || null,
    directorioCertificados: process.env.DTE_CERTIFICATES_DIR?.trim() || '/app/certificados',
  },
  contingencia: {
    // Solo para las pruebas de certificación (Manual Funcional XXIV) en el ambiente de pruebas.
    forzadaPermitida: process.env.DTE_ALLOW_FORCED_CONTINGENCY === 'true' && dteMode === 'hacienda-test',
    tipoPorDefecto: tipoContingenciaPorDefecto(),
    sondeoMs: enteroPositivo('DTE_CONTINGENCIA_SONDEO_MS', 60000),
    responsable: dteMode === 'simulated' ? null : responsableContingencia(),
  },
  dteMode,
  haciendaPorModo,
  simulation: {
    acknowledged: process.env.DTE_SIMULATION_ACKNOWLEDGED === 'true',
    runId: process.env.DTE_SIMULATION_RUN_ID?.trim() || null,
    scenario: simulationScenario,
    orderScenarios: SIMULATION_ORDER_SCENARIOS,
    watermark: process.env.DTE_SIMULATION_WATERMARK || 'DOCUMENTO SIMULADO - SIN VALIDEZ FISCAL',
  },
  server: {
    port: parseInt(process.env.PORT || '3000', 10),
    logLevel: process.env.LOG_LEVEL || 'info',
  },
  db: {
    path: rutaSqlite(process.env),
  },
  // Reloj de demostración (V9b del ERP): solo desarrollo, nunca en producción.
  demoClockEnabled: process.env.DTE_DEMO_CLOCK_ENABLED === 'true' && dteMode !== 'production',
  retry: {
    maxAttempts: parseInt(process.env.RETRY_MAX_ATTEMPTS || '5', 10),
    baseDelayMs: parseInt(process.env.RETRY_BASE_DELAY_MS || '2000', 10),
  },
  security: {
    // MS_API_KEYS: una o más API keys separadas por coma, para autenticar
    // a los CONSUMIDORES de este microservicio (tu ERP/POS), NO confundir
    // con las credenciales de Hacienda (esas van en emisor.passwordApi).
    apiKeys,
    apiKeyRecords: apiKeys.map((key, index) => ({ key, scopes: apiKeyScopes[index] })),
    allScopes: ALL_API_SCOPES,
    // Opt-out EXPLÍCITO solo para desarrollo local. Si algún día esto se
    // despliega sin querer con AUTH_DESHABILITADA=true, al menos queda un
    // log de advertencia bien visible (ver server.js).
    authDeshabilitada: process.env.MS_AUTH_DESHABILITADA === 'true',
    // El checkout vigente solo necesita Factura (01) y CCF (03). Ampliar esta
    // lista requiere matriz fiscal, credencial/scopes y pruebas de Hacienda.
    allowedDocumentTypes: parseAllowedDocumentTypes(process.env.DTE_ALLOWED_DOCUMENT_TYPES),
    authorizedIssuerNits: [...new Set(authorizedIssuerNits)],
    rateLimit: {
      // Máximo de peticiones por ventana, por API key. 0 = deshabilitado.
      maxPeticiones: parseInt(process.env.MS_RATE_LIMIT_MAX || '120', 10),
      ventanaMs: parseInt(process.env.MS_RATE_LIMIT_WINDOW_MS || '60000', 10), // 1 minuto
    },
  },
};

if (config.security.apiKeys.length === 0 && !config.security.authDeshabilitada) {
  throw new Error(
    'No hay ninguna API key configurada (MS_API_KEYS) y MS_AUTH_DESHABILITADA no está en "true". ' +
      'El servidor NO arrancará así por seguridad: cualquiera podría emitir DTE con tu NIT. ' +
      'Genera una key con `node scripts/generar-api-key.js` y ponla en tu .env, o define ' +
      'MS_AUTH_DESHABILITADA=true explícitamente si es un entorno de desarrollo local sin riesgo.'
  );
}

module.exports = config;
