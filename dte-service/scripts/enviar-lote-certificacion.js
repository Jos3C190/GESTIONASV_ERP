/**
 * Pruebas de certificación en el ambiente de pruebas de Hacienda (Manual
 * Funcional v2.0, XXIV): mínimos de 90 Facturas, 75 CCF, 5 invalidaciones y
 * 5 contingencias con sello de recepción.
 *
 * Usa la API del microservicio en modo hacienda-test (contrato v1: el emisor
 * sale de MH_* del microservicio). Es reanudable: cada documento usa una
 * Idempotency-Key estable por corrida, así que volver a ejecutar con el mismo
 * CERT_RUN_ID retoma lo pendiente sin duplicar DTE.
 *
 * Requisitos:
 *   - Microservicio con DTE_MODE=hacienda-test, firmador y credenciales de pruebas.
 *   - Para las contingencias: DTE_ALLOW_FORCED_CONTINGENCY=true en el microservicio.
 *
 * Variables:
 *   MICROSERVICIO_URL        (default http://localhost:3000)
 *   MICROSERVICIO_API_KEY    key con scopes issue,read
 *   MICROSERVICIO_FISCAL_KEY key con scopes read,invalidate,contingency
 *   CERT_RUN_ID              identificador de la corrida (default: fecha de hoy)
 *   CERT_FACTURAS=90 CERT_CCF=75 CERT_INVALIDACIONES=5 CERT_CONTINGENCIAS=5
 *   CERT_RECEPTOR_NIT, CERT_RECEPTOR_NRC, CERT_RECEPTOR_NOMBRE, CERT_RECEPTOR_ACTIVIDAD,
 *   CERT_RECEPTOR_ACTIVIDAD_DESC, CERT_RECEPTOR_CORREO   receptor de los CCF
 *   CERT_RESPONSABLE_NOMBRE, CERT_RESPONSABLE_TIPO_DOC, CERT_RESPONSABLE_NUM_DOC
 *   CERT_DELAY_MS=1500
 *
 * Uso: node scripts/enviar-lote-certificacion.js
 */
const fs = require('node:fs');
const path = require('node:path');
// La corrida por defecto se nombra con la fecha de El Salvador (de noche, la fecha UTC ya es mañana).
const { fechaHoraSV } = require('../src/utils/fechaHoraSV');

const BASE_URL = (process.env.MICROSERVICIO_URL || 'http://localhost:3000').replace(/\/+$/, '');
const API_KEY = process.env.MICROSERVICIO_API_KEY;
const FISCAL_KEY = process.env.MICROSERVICIO_FISCAL_KEY;
const RUN_ID = (process.env.CERT_RUN_ID || fechaHoraSV().fecha).replace(/[^A-Za-z0-9_-]/g, '');
const DELAY_MS = Number(process.env.CERT_DELAY_MS || 1500);
const MINIMOS = {
  factura: Number(process.env.CERT_FACTURAS ?? 90),
  ccf: Number(process.env.CERT_CCF ?? 75),
  invalidacion: Number(process.env.CERT_INVALIDACIONES ?? 5),
  contingencia: Number(process.env.CERT_CONTINGENCIAS ?? 5),
};
const REPORTE = path.join(process.cwd(), `certificacion-${RUN_ID}.json`);
const MAX_FALLOS_SEGUIDOS = 5;

if (!API_KEY) {
  console.error('Falta MICROSERVICIO_API_KEY (key con scopes issue,read).');
  process.exit(1);
}
if ((MINIMOS.invalidacion > 0 || MINIMOS.contingencia > 0) && !FISCAL_KEY) {
  console.error('Falta MICROSERVICIO_FISCAL_KEY (scopes read,invalidate,contingency) para invalidaciones y contingencias.');
  process.exit(1);
}

const responsable = {
  nombre: process.env.CERT_RESPONSABLE_NOMBRE || process.env.MH_RESPONSABLE_NOMBRE,
  tipoDocumento: process.env.CERT_RESPONSABLE_TIPO_DOC || process.env.MH_RESPONSABLE_TIPO_DOC || '13',
  numeroDocumento: process.env.CERT_RESPONSABLE_NUM_DOC || process.env.MH_RESPONSABLE_NUM_DOC,
};
if ((MINIMOS.invalidacion > 0 || MINIMOS.contingencia > 0) && (!responsable.nombre || !responsable.numeroDocumento)) {
  console.error('Falta el responsable de los eventos: CERT_RESPONSABLE_NOMBRE y CERT_RESPONSABLE_NUM_DOC (o MH_RESPONSABLE_*).');
  process.exit(1);
}

const receptorCcf = {
  nit: process.env.CERT_RECEPTOR_NIT,
  nrc: process.env.CERT_RECEPTOR_NRC,
  nombre: process.env.CERT_RECEPTOR_NOMBRE || 'Cliente de pruebas de certificación',
  codActividad: process.env.CERT_RECEPTOR_ACTIVIDAD || '62010',
  descActividad: process.env.CERT_RECEPTOR_ACTIVIDAD_DESC || 'Programación informática',
  direccion: { departamento: '06', municipio: '23', distrito: '14', complemento: 'Dirección de pruebas de certificación' },
  telefono: '22223333',
  correo: process.env.CERT_RECEPTOR_CORREO || 'certificacion@example.com',
};
if (MINIMOS.ccf > 0 && (!receptorCcf.nit || !receptorCcf.nrc)) {
  console.error('Falta el receptor de los CCF: CERT_RECEPTOR_NIT y CERT_RECEPTOR_NRC.');
  process.exit(1);
}

function cargarReporte() {
  try {
    return JSON.parse(fs.readFileSync(REPORTE, 'utf8'));
  } catch {
    return { runId: RUN_ID, inicio: new Date().toISOString(), documentos: {}, invalidaciones: {}, contingencias: {} };
  }
}

const reporte = cargarReporte();
function guardar() {
  reporte.actualizado = new Date().toISOString();
  fs.writeFileSync(REPORTE, JSON.stringify(reporte, null, 2));
}

const esperar = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function llamar(metodo, ruta, { body, clave, fiscal = false } = {}) {
  const headers = { Authorization: `Bearer ${fiscal ? FISCAL_KEY : API_KEY}` };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (clave) headers['Idempotency-Key'] = clave;
  const res = await fetch(`${BASE_URL}${ruta}`, { method: metodo, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  return { status: res.status, body: await res.json().catch(() => ({})) };
}

// ---- Documentos variados: precios con IVA en Factura y sin IVA en CCF ----

function redondear(valor) {
  return Math.round(valor * 100) / 100;
}

function payloadFactura(n) {
  const precio = redondear(5 + (n % 17) * 1.13);
  const cantidad = 1 + (n % 3);
  const descuento = n % 4 === 0 ? redondear(precio * 0.1) : 0;
  const items = [{ descripcion: `Producto de prueba F-${n}`, cantidad, precioUni: precio, montoDescu: descuento, ventaGravada: redondear(precio * cantidad - descuento) }];
  if (n % 5 === 0) items.push({ tipoItem: 2, descripcion: 'Servicio de entrega', cantidad: 1, precioUni: 3.5, ventaNoSuj: 3.5, ventaGravada: 0 });
  const total = redondear(items.reduce((suma, item) => suma + item.ventaGravada + (item.ventaNoSuj || 0), 0));
  return {
    receptor: n % 6 === 0 ? { tipoDocumento: '13', numDocumento: '01234567-8', nombre: 'Consumidor de prueba', correo: 'consumidor@example.com' } : null,
    items,
    pago: { codigo: n % 2 === 0 ? '01' : '05', montoPago: total, referencia: n % 2 === 0 ? null : `TRANSF-${RUN_ID}-${n}`, numPagoElectronico: null },
  };
}

function payloadCcf(n) {
  const precio = redondear(10 + (n % 13) * 2.25);
  const cantidad = 1 + (n % 4);
  const descuento = n % 3 === 0 ? redondear(precio * cantidad * 0.05) : 0;
  const venta = redondear(precio * cantidad - descuento);
  const iva = redondear(venta * 0.13);
  return {
    receptor: receptorCcf,
    items: [{ descripcion: `Servicio de prueba C-${n}`, cantidad, precioUni: precio, montoDescu: descuento, ventaGravada: venta, ivaItem: iva }],
    pago: { codigo: '05', montoPago: redondear(venta + iva), referencia: `TRANSF-${RUN_ID}-C${n}`, numPagoElectronico: null },
  };
}

let fallosSeguidos = 0;
function registrarResultado(ok) {
  fallosSeguidos = ok ? 0 : fallosSeguidos + 1;
  if (fallosSeguidos >= MAX_FALLOS_SEGUIDOS) {
    guardar();
    console.error(`\n${MAX_FALLOS_SEGUIDOS} fallos seguidos: se detiene la corrida. Revisa el reporte ${REPORTE}.`);
    process.exit(2);
  }
}

async function esperarTransmision(codigoGeneracion, maxSegundos = 180) {
  const limite = Date.now() + maxSegundos * 1000;
  while (Date.now() < limite) {
    const { body } = await llamar('GET', `/api/dte/${codigoGeneracion}`);
    if (['TRANSMITIDO', 'RECHAZADO', 'INVALIDADO'].includes(body.estado)) return body;
    await esperar(5000);
  }
  return null;
}

async function emitir(tipo, n, payload) {
  const clave = `cert-${RUN_ID}-${tipo}-${n}`;
  const previo = reporte.documentos[clave];
  if (previo && ['TRANSMITIDO', 'INVALIDADO'].includes(previo.estado)) return previo;
  const ruta = tipo === 'ccf' ? '/api/dte/ccf' : '/api/dte/factura';
  let { status, body } = await llamar('POST', ruta, { body: payload, clave });
  if (status === 202 && body.codigoGeneracion) {
    const final = await esperarTransmision(body.codigoGeneracion);
    if (final) body = { ...body, estado: final.estado, selloRecepcion: final.sello_recepcion };
  }
  const resultado = {
    tipo,
    clave,
    httpStatus: status,
    codigoGeneracion: body.codigoGeneracion ?? null,
    numeroControl: body.numeroControl ?? null,
    estado: body.estado ?? 'ERROR',
    selloRecepcion: body.selloRecepcion ?? null,
    error: body.error ?? body.respuestaHacienda?.descripcionMsg ?? null,
    observaciones: body.respuestaHacienda?.observaciones ?? undefined,
  };
  reporte.documentos[clave] = resultado;
  guardar();
  registrarResultado(resultado.estado === 'TRANSMITIDO');
  console.log(`${tipo.toUpperCase()} ${n}: ${resultado.estado}${resultado.error ? ` — ${resultado.error}` : ''}`);
  await esperar(DELAY_MS);
  return resultado;
}

async function invalidar(n, documento) {
  const clave = `cert-${RUN_ID}-invalidacion-${n}`;
  const previo = reporte.invalidaciones[clave];
  if (previo?.estado === 'INVALIDADO') return previo;
  const { status, body } = await llamar('POST', `/api/dte/${documento.codigoGeneracion}/anular`, {
    fiscal: true,
    clave,
    body: { motivo: { tipoAnulacion: 2, motivoAnulacion: 'Prueba de certificación: operación rescindida', responsable, solicitante: responsable } },
  });
  const resultado = {
    clave,
    httpStatus: status,
    documento: documento.codigoGeneracion,
    estado: status === 200 ? 'INVALIDADO' : body.code || 'ERROR',
    evento: body.codigoGeneracionEvento ?? null,
    selloEvento: body.selloRecepcionEvento ?? null,
    error: body.error ?? null,
  };
  reporte.invalidaciones[clave] = resultado;
  if (resultado.estado === 'INVALIDADO') reporte.documentos[documento.clave].estado = 'INVALIDADO';
  guardar();
  registrarResultado(resultado.estado === 'INVALIDADO');
  console.log(`INVALIDACIÓN ${n}: ${resultado.estado}${resultado.error ? ` — ${resultado.error}` : ''}`);
  await esperar(DELAY_MS);
  return resultado;
}

async function contingencia(n) {
  const clave = `cert-${RUN_ID}-contingencia-${n}`;
  const previo = reporte.contingencias[clave];
  if (previo?.estado === 'COMPLETADA') return previo;

  let ventanaId = previo?.ventanaId;
  if (!ventanaId) {
    const forzada = await llamar('POST', '/api/dte/contingencia/forzar', {
      fiscal: true,
      body: { tipoContingencia: 5, motivoContingencia: `Prueba de certificación de contingencia ${n}` },
    });
    if (forzada.status !== 201) {
      console.error(`CONTINGENCIA ${n}: no se pudo forzar (${forzada.body.code || forzada.status}) — ${forzada.body.error || ''}`);
      registrarResultado(false);
      return null;
    }
    ventanaId = forzada.body.id;
    reporte.contingencias[clave] = { clave, ventanaId, estado: 'ACTIVA', documentos: [] };
    guardar();
  }

  const registro = reporte.contingencias[clave];
  if (registro.documentos.length === 0) {
    const { status, body } = await llamar('POST', '/api/dte/factura', { body: payloadFactura(1000 + n), clave: `${clave}-documento` });
    if (status !== 202 || body.estado !== 'CONTINGENCIA') {
      console.error(`CONTINGENCIA ${n}: el documento no nació en contingencia (${body.estado || status})`);
      registrarResultado(false);
      return null;
    }
    registro.documentos.push({ codigoGeneracion: body.codigoGeneracion, numeroControl: body.numeroControl });
    guardar();
  }

  const cierre = await llamar('POST', `/api/dte/contingencia/${ventanaId}/cerrar`, { fiscal: true, body: { responsable } });
  registro.evento = cierre.body.evento ?? null;
  registro.estado = cierre.body.estado ?? 'ERROR';
  registro.error = cierre.body.error ?? cierre.body.ultimoError ?? null;
  guardar();
  if (registro.estado !== 'REPORTADA' && registro.estado !== 'COMPLETADA') {
    console.error(`CONTINGENCIA ${n}: evento no recibido (${registro.estado}) — ${registro.error || ''}`);
    registrarResultado(false);
    return registro;
  }

  for (const documento of registro.documentos) {
    const final = await esperarTransmision(documento.codigoGeneracion, 300);
    documento.estado = final?.estado ?? 'SIN_CONFIRMAR';
    documento.selloRecepcion = final?.sello_recepcion ?? null;
  }
  registro.estado = registro.documentos.every((documento) => documento.estado === 'TRANSMITIDO') ? 'COMPLETADA' : registro.estado;
  guardar();
  registrarResultado(registro.estado === 'COMPLETADA');
  console.log(`CONTINGENCIA ${n}: ${registro.estado} (evento ${registro.evento?.selloRecepcion ? 'con sello' : 'sin sello'})`);
  await esperar(DELAY_MS);
  return registro;
}

async function main() {
  console.log(`Corrida ${RUN_ID} contra ${BASE_URL}. Reporte: ${REPORTE}`);
  const salud = await llamar('GET', '/api/health');
  if (salud.body.dteMode !== 'hacienda-test') {
    console.error(`El microservicio no está en hacienda-test (dteMode=${salud.body.dteMode}). Se detiene por seguridad.`);
    process.exit(1);
  }

  const facturas = [];
  for (let n = 1; n <= MINIMOS.factura; n++) facturas.push(await emitir('factura', n, payloadFactura(n)));
  for (let n = 1; n <= MINIMOS.ccf; n++) await emitir('ccf', n, payloadCcf(n));

  const invalidables = facturas.filter((documento) => documento?.estado === 'TRANSMITIDO' || documento?.estado === 'INVALIDADO');
  for (let n = 1; n <= MINIMOS.invalidacion; n++) {
    const documento = invalidables[invalidables.length - n];
    if (!documento) {
      console.error('No hay suficientes Facturas transmitidas para las invalidaciones.');
      break;
    }
    await invalidar(n, documento);
  }

  for (let n = 1; n <= MINIMOS.contingencia; n++) await contingencia(n);

  const documentos = Object.values(reporte.documentos);
  const resumen = {
    facturas: documentos.filter((d) => d.tipo === 'factura' && ['TRANSMITIDO', 'INVALIDADO'].includes(d.estado)).length,
    ccf: documentos.filter((d) => d.tipo === 'ccf' && ['TRANSMITIDO', 'INVALIDADO'].includes(d.estado)).length,
    invalidaciones: Object.values(reporte.invalidaciones).filter((i) => i.estado === 'INVALIDADO').length,
    contingencias: Object.values(reporte.contingencias).filter((c) => c.estado === 'COMPLETADA').length,
  };
  reporte.resumen = resumen;
  guardar();
  console.log('\nResumen con sello de recepción:', resumen);
  const cumple = resumen.facturas >= MINIMOS.factura && resumen.ccf >= MINIMOS.ccf
    && resumen.invalidaciones >= MINIMOS.invalidacion && resumen.contingencias >= MINIMOS.contingencia;
  console.log(cumple ? 'Se alcanzaron los mínimos configurados.' : 'Aún no se alcanzan los mínimos: revisa los errores del reporte y vuelve a ejecutar con el mismo CERT_RUN_ID.');
  process.exit(cumple ? 0 : 3);
}

main().catch((error) => {
  guardar();
  console.error('Error inesperado:', error.message);
  process.exit(1);
});
