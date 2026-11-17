const dns = require('node:dns');
const http = require('node:http');
const https = require('node:https');
const net = require('node:net');
const tls = require('node:tls');
const logger = require('../utils/logger');

/**
 * Bloqueo de salida de red para el modo simulated (DEC-010, plan §7 capa 4).
 *
 * El microservicio simulado no necesita ninguna conexión saliente: solo
 * recibe peticiones del backend y usa SQLite local. Por eso, al activarse,
 * toda conexión o resolución DNS hacia un destino que no sea loopback falla
 * en el acto con SIMULATION_EGRESS_BLOCKED, antes de resolver el nombre.
 * Cubre http/https (axios), net/tls (fetch de Node) y dns.lookup.
 *
 * No reemplaza las otras capas (sin URLs ni secretos de Hacienda, rutas no
 * montadas, red Docker interna): es la que falla aunque todas las demás se
 * hayan configurado mal.
 */

let activo = false;
let bloqueadas = 0;

function esLoopback(host) {
  const limpio = String(host ?? '').trim().toLowerCase().replace(/^\[|\]$/g, '');
  if (limpio === 'localhost' || limpio === '::1') return true;
  const ipv4 = limpio.startsWith('::ffff:') ? limpio.slice('::ffff:'.length) : limpio;
  return /^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(ipv4);
}

function bloquear(operacion, host) {
  bloqueadas += 1;
  logger.error({ operacion, host: String(host).slice(0, 255), bloqueadas }, 'Salida de red bloqueada en modo simulado');
  return Object.assign(new Error(`Salida de red bloqueada en modo simulado: ${operacion} ${host}`), {
    code: 'SIMULATION_EGRESS_BLOCKED',
  });
}

/** Host de destino de http(s).request/get: (url[, options][, cb]) u (options[, cb]). */
function destinoHttp(args) {
  let host = null;
  for (const argumento of args) {
    if (typeof argumento === 'string') {
      try { host = new URL(argumento).hostname; } catch { /* lo valida Node */ }
    } else if (argumento instanceof URL) {
      host = argumento.hostname;
    } else if (argumento && typeof argumento === 'object') {
      if (argumento.socketPath) return { local: true };
      host = argumento.hostname ?? argumento.host ?? host;
    }
  }
  return { local: false, host: host ?? 'localhost' };
}

/** Host de net/tls.connect: (options[, cb]), (port[, host][, cb]) o (path[, cb]). */
function destinoSocket(args) {
  const [primero, segundo] = args;
  if (primero && typeof primero === 'object') {
    if (primero.path) return { local: true };
    return { local: false, host: primero.host ?? primero.servername ?? 'localhost' };
  }
  if (typeof primero === 'string' && !/^\d+$/.test(primero)) return { local: true }; // socket de dominio Unix
  return { local: false, host: typeof segundo === 'string' ? segundo : 'localhost' };
}

function envolver(modulo, nombre, destino, operacion) {
  const original = modulo[nombre];
  modulo[nombre] = function guardado(...args) {
    const { local, host } = destino(args);
    if (!local && !esLoopback(host)) throw bloquear(operacion, host);
    return original.apply(this, args);
  };
}

function activar() {
  if (activo) return;
  activo = true;
  for (const [modulo, nombre] of [[http, 'request'], [http, 'get'], [https, 'request'], [https, 'get']]) {
    envolver(modulo, nombre, destinoHttp, `${modulo === https ? 'https' : 'http'}.${nombre}`);
  }
  for (const [modulo, nombre] of [[net, 'connect'], [net, 'createConnection'], [tls, 'connect']]) {
    envolver(modulo, nombre, destinoSocket, `${modulo === tls ? 'tls' : 'net'}.${nombre}`);
  }

  const lookup = dns.lookup;
  dns.lookup = function lookupGuardado(hostname, ...resto) {
    if (esLoopback(hostname)) return lookup.call(this, hostname, ...resto);
    const error = bloquear('dns.lookup', hostname);
    const callback = resto.find((argumento) => typeof argumento === 'function');
    if (!callback) throw error;
    process.nextTick(callback, error);
    return undefined;
  };
  const lookupPromesa = dns.promises.lookup;
  dns.promises.lookup = async function lookupPromesaGuardado(hostname, ...resto) {
    if (esLoopback(hostname)) return lookupPromesa.call(this, hostname, ...resto);
    throw bloquear('dns.promises.lookup', hostname);
  };
}

function estado() {
  return { activo, bloqueadas };
}

module.exports = { activar, estado, esLoopback };
