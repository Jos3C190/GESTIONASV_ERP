const fs = require('fs');
const path = require('path');
const { X509Certificate } = require('crypto');
const config = require('../config');
const logger = require('../utils/logger');
const authService = require('./authService');
const { AuthError } = require('./authService');
const { firmarDocumento, FirmadorError } = require('./firmadorClient');
const { ultimoAccesoExitoso, registrarAccesoExitoso } = require('./accesoHacienda');

/**
 * Tarjeta «Conexión con Hacienda» del panel (mejora 14). Lee la
 * configuración y el certificado SIN devolver secretos: de las credenciales
 * solo dice si están configuradas, y del certificado solo su NIT y su
 * vigencia. El archivo del certificado trae también la llave privada: se lee
 * en memoria, se extraen esos tres datos y no se guarda, registra ni devuelve
 * nada más.
 */

const DIAS_AVISO_VENCIMIENTO = 30;
const DIA_MS = 24 * 60 * 60 * 1000;
const ESPERA_ENTRE_PRUEBAS_MS = 30 * 1000;
let ultimaPrueba = 0;

const ETIQUETAS_AMBIENTE = { simulated: 'Simulado', 'hacienda-test': 'Pruebas de Hacienda', production: 'Producción' };

/** Fecha de un campo del certificado: ISO, o milisegundos/segundos desde 1970. */
function fecha(valor) {
  const texto = String(valor ?? '').trim();
  if (!texto) return null;
  if (/^\d{10}$/.test(texto)) return new Date(Number(texto) * 1000);
  if (/^\d{12,14}$/.test(texto)) return new Date(Number(texto));
  const instante = Date.parse(texto);
  return Number.isNaN(instante) ? null : new Date(instante);
}

/** Primer valor de una etiqueta XML sin atributos ni anidamiento: <nit>…</nit>. */
function etiqueta(xml, nombre) {
  const coincidencia = new RegExp(`<${nombre}>\\s*([^<]{1,64}?)\\s*</${nombre}>`).exec(xml);
  return coincidencia ? coincidencia[1] : null;
}

/**
 * NIT y vigencia de un certificado: el XML <CertificadoMH> que entrega
 * Hacienda (etiquetas <nit>, <notBefore> y <notAfter>) o un X.509 en PEM.
 * Devuelve null si no reconoce el formato.
 */
function leerDatosCertificado(contenido) {
  if (contenido.includes('-----BEGIN CERTIFICATE-----')) {
    const pem = /-----BEGIN CERTIFICATE-----[\s\S]+?-----END CERTIFICATE-----/.exec(contenido)[0];
    const certificado = new X509Certificate(pem);
    const nit = /\b(\d{14}|\d{9})\b/.exec(certificado.subject)?.[1] ?? null;
    return { nit, validoDesde: new Date(certificado.validFrom), validoHasta: new Date(certificado.validTo) };
  }
  const validoHasta = fecha(etiqueta(contenido, 'notAfter'));
  if (!validoHasta) return null;
  const nit = etiqueta(contenido, 'nit')?.replace(/[\s-]/g, '') ?? null;
  return { nit: nit && /^(\d{9}|\d{14})$/.test(nit) ? nit : null, validoDesde: fecha(etiqueta(contenido, 'notBefore')), validoHasta };
}

function rutaCertificado() {
  const ruta = config.certificado.ruta;
  try {
    const info = fs.statSync(ruta);
    return info.isDirectory() ? path.join(ruta, `${config.emisor.nit}.crt`) : ruta;
  } catch {
    return null;
  }
}

/** Estado del certificado de firma, sin secretos. */
function estadoCertificado(ahora = new Date()) {
  if (config.dteMode === 'simulated') return { estado: 'NO_APLICA' };
  const ruta = rutaCertificado();
  if (!ruta || !fs.existsSync(ruta)) return { estado: 'NO_DISPONIBLE' };
  let datos;
  try {
    datos = leerDatosCertificado(fs.readFileSync(ruta, 'utf8'));
  } catch (err) {
    // Sin el contenido: solo el tipo de error.
    logger.warn({ error: err.name }, 'No se pudo leer el certificado de firma');
    datos = null;
  }
  if (!datos) return { estado: 'ILEGIBLE' };
  const diasParaVencer = Math.floor((datos.validoHasta.getTime() - ahora.getTime()) / DIA_MS);
  const estado = datos.validoHasta.getTime() <= ahora.getTime()
    ? 'VENCIDO'
    : diasParaVencer < DIAS_AVISO_VENCIMIENTO ? 'POR_VENCER' : 'VIGENTE';
  return {
    estado,
    nit: datos.nit,
    coincideConNitConfigurado: datos.nit ? datos.nit === config.emisor.nit : null,
    validoDesde: datos.validoDesde ? datos.validoDesde.toISOString() : null,
    validoHasta: datos.validoHasta.toISOString(),
    diasParaVencer: Math.max(diasParaVencer, 0),
  };
}

/** Qué está configurado, por nombre de variable; nunca su valor. */
function credenciales() {
  if (config.dteMode === 'simulated') return { aplica: false, faltan: [] };
  const presentes = {
    MH_NIT: Boolean(config.emisor.nit),
    MH_PASSWORD_API: Boolean(config.emisor.passwordApi),
    MH_PASSWORD_PRI: Boolean(config.emisor.passwordPri),
    FIRMADOR_URL: Boolean(config.firmador.url),
  };
  return { aplica: true, ...presentes, faltan: Object.keys(presentes).filter((nombre) => !presentes[nombre]) };
}

function estado(ahora = new Date()) {
  return {
    modo: config.dteMode,
    ambiente: config.emisor.ambiente,
    ambienteEtiqueta: ETIQUETAS_AMBIENTE[config.dteMode] ?? config.dteMode,
    nitConfigurado: config.dteMode === 'simulated' ? null : config.emisor.nit,
    credenciales: credenciales(),
    certificado: estadoCertificado(ahora),
    ultimoAccesoExitoso: ultimoAccesoExitoso(),
    diasAvisoVencimiento: DIAS_AVISO_VENCIMIENTO,
  };
}

/** Resultado de un paso de la prueba, con un código estable y un mensaje en español. */
function paso(nombre, ok, codigo, mensaje) {
  return { paso: nombre, ok, codigo, mensaje };
}

async function probarFirmador() {
  try {
    await firmarDocumento({ pruebaConexion: true, generado: new Date().toISOString() });
    return paso('firmador', true, 'OK', 'El firmador firmó un documento de prueba con el certificado.');
  } catch (err) {
    if (err instanceof FirmadorError && err.configuracion) {
      const detalle = err.codigoFirmador === '812'
        ? 'el firmador no encuentra el archivo del certificado'
        : 'la contraseña de la llave privada (MH_PASSWORD_PRI) no corresponde al certificado';
      return paso('firmador', false, 'CERTIFICADO_INVALIDO', `Certificado inválido: ${detalle}.`);
    }
    if (err instanceof FirmadorError && err.codigoFirmador) {
      return paso('firmador', false, 'CERTIFICADO_INVALIDO', `El firmador rechazó el certificado (código ${err.codigoFirmador}).`);
    }
    return paso('firmador', false, 'FIRMADOR_NO_RESPONDE', 'El firmador no responde.');
  }
}

async function probarHacienda() {
  try {
    await authService.probarAutenticacion();
    return paso('hacienda', true, 'OK', 'Hacienda aceptó las credenciales del API.');
  } catch (err) {
    if (err instanceof AuthError && err.credenciales) {
      return paso('hacienda', false, 'CREDENCIALES_INVALIDAS', 'Hacienda rechazó el usuario (NIT) o la contraseña del API (MH_PASSWORD_API).');
    }
    return paso('hacienda', false, 'HACIENDA_NO_RESPONDE', 'Hacienda no responde.');
  }
}

/**
 * Prueba de conexión: firma un documento de prueba con el firmador local y
 * se autentica en Hacienda. No transmite ni emite nada. En simulado no
 * contacta a nadie. Una prueba cada 30 s como máximo.
 */
async function probarConexion(ahora = Date.now()) {
  if (config.dteMode === 'simulated') {
    return { estado: 200, cuerpo: { ok: false, simulado: true, codigo: 'SIMULADO', mensaje: 'Modo simulado: no hay conexión con Hacienda', pasos: [] } };
  }
  if (ahora - ultimaPrueba < ESPERA_ENTRE_PRUEBAS_MS) {
    const segundos = Math.ceil((ESPERA_ENTRE_PRUEBAS_MS - (ahora - ultimaPrueba)) / 1000);
    return { estado: 429, cuerpo: { error: `Espera ${segundos} s para volver a probar la conexión`, code: 'CONNECTION_TEST_TOO_SOON', retryAfterSeconds: segundos } };
  }
  ultimaPrueba = ahora;
  const firmador = await probarFirmador();
  const hacienda = await probarHacienda();
  if (hacienda.ok) registrarAccesoExitoso('autenticacion');
  const pasos = [firmador, hacienda];
  const fallo = pasos.find((resultado) => !resultado.ok);
  return {
    estado: 200,
    cuerpo: {
      ok: !fallo,
      simulado: false,
      codigo: fallo ? fallo.codigo : 'OK',
      mensaje: fallo ? fallo.mensaje : 'Conexión correcta',
      pasos,
      probadoEn: new Date(ahora).toISOString(),
    },
  };
}

/** Solo para pruebas: permite otra prueba de conexión enseguida. */
function _reiniciarLimite() {
  ultimaPrueba = 0;
}

module.exports = { estado, estadoCertificado, leerDatosCertificado, probarConexion, DIAS_AVISO_VENCIMIENTO, _reiniciarLimite };
