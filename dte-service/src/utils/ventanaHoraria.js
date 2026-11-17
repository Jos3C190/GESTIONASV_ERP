/**
 * Ventanas horarias de recepción de LOTES de DTE, confirmadas en el Manual
 * Tecnológico v2.0, sección 3.4 (Servicio de Recepción por Lotes), en hora de
 * El Salvador:
 *   - Ambiente de pruebas:    08:00 a 17:00
 *   - Ambiente de producción: 22:00 a 05:00 (cruza medianoche)
 *
 * OJO — matiz importante que el propio manual aclara: "La restricción de
 * horarios para la transmisión de lotes de documentos está establecida
 * para los contribuyentes que posean facturación cíclica." Es decir, NO
 * aplica a todos los que usan el modelo de lotes, solo a ese segmento
 * específico. Por eso esta utilidad NO BLOQUEA el envío — solo informa si
 * estás fuera de ventana, para que decidas tú si te aplica la restricción.
 *
 * La Contingencia, en cambio, NO tiene ninguna restricción de horario (está
 * abierta 24/365) — no necesita ninguna verificación.
 */

const { fechaHoraSV } = require('./fechaHoraSV');

const VENTANAS = {
  '00': { desdeHora: 8, hastaHora: 17 }, // pruebas: 08:00–17:00, no cruza medianoche
  '01': { desdeHora: 22, hastaHora: 5 }, // producción: 22:00–05:00, cruza medianoche
};

/**
 * Devuelve { dentroDeVentana: boolean, ventana: string } para el ambiente
 * dado, evaluado contra la hora actual (o la que se pase explícitamente,
 * útil para tests). La hora se toma en El Salvador, no en la zona del
 * proceso: el contenedor corre en UTC.
 */
function verificarVentanaLote(ambiente, ahora = new Date()) {
  const config = VENTANAS[ambiente];
  if (!config) {
    return { dentroDeVentana: true, ventana: null }; // ambiente desconocido: no opinar
  }

  const hora = Number(fechaHoraSV(ahora).hora.slice(0, 2));
  const { desdeHora, hastaHora } = config;

  const dentroDeVentana =
    desdeHora <= hastaHora
      ? hora >= desdeHora && hora < hastaHora // ventana normal (no cruza medianoche)
      : hora >= desdeHora || hora < hastaHora; // ventana que cruza medianoche

  const ventana = `${String(desdeHora).padStart(2, '0')}:00–${String(hastaHora).padStart(2, '0')}:00`;
  return { dentroDeVentana, ventana };
}

module.exports = { verificarVentanaLote };
