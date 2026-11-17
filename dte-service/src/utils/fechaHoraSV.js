/**
 * Fecha y hora de El Salvador (America/El_Salvador) para fecEmi/horEmi de
 * los DTE y las fechas de los eventos (Invalidación, Contingencia).
 *
 * Hacienda valida fecEmi/horEmi en hora de El Salvador (Manual Técnico v2.0,
 * sección 3.1: el último día del período tributario la holgura es de 30
 * minutos), y la URL del QR de consulta pública usa fecEmi. Antes cada builder
 * sacaba fecEmi de toISOString() (fecha UTC) y horEmi de toTimeString() (hora
 * de la zona del proceso): en el contenedor (sin TZ, o sea UTC) ambas quedaban
 * 6 h adelantadas, y con el proceso en hora de El Salvador la fecha se
 * adelantaba un día entre las 18:00 y las 23:59.
 *
 * El Salvador usa UTC-6 fijo (sin horario de verano desde 1988), así que basta
 * con desplazar el instante 6 h y leer sus campos UTC: el resultado no depende
 * de la zona del proceso ni de los datos de zonas horarias del contenedor.
 */

const ZONA_HORARIA_SV = 'America/El_Salvador';
const DESFASE_SV_MS = -6 * 60 * 60 * 1000;

let relojActivo = () => new Date();

/** Permite fijar el reloj en pruebas; sin argumento vuelve al reloj real. */
function usarReloj(fn) {
  relojActivo = typeof fn === 'function' ? fn : () => new Date();
}

/** Instante actual según el reloj activo (el real, o el fijado con usarReloj). */
function ahora() {
  return relojActivo();
}

/**
 * Devuelve { fecha: 'YYYY-MM-DD', hora: 'HH:MM:SS', anio } del instante dado
 * (por defecto, ahora) en hora de El Salvador. Fecha, hora y año salen del
 * MISMO instante, para que nunca correspondan a momentos distintos.
 */
function fechaHoraSV(instante = ahora()) {
  const ms = instante instanceof Date ? instante.getTime() : NaN;
  if (!Number.isFinite(ms)) {
    throw new TypeError('fechaHoraSV requiere una fecha (Date) válida');
  }
  const iso = new Date(ms + DESFASE_SV_MS).toISOString(); // "YYYY-MM-DDTHH:MM:SS.sssZ", ya en hora SV
  return {
    fecha: iso.slice(0, 10),
    hora: iso.slice(11, 19),
    anio: Number(iso.slice(0, 4)),
  };
}

module.exports = { fechaHoraSV, ZONA_HORARIA_SV, usarReloj, ahora };
