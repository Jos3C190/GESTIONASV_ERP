// Utilidades de prueba para fijar el reloj y la zona horaria del proceso,
// usadas por las pruebas de fecEmi/horEmi en hora de El Salvador.

const ZONA_ORIGINAL = Intl.DateTimeFormat().resolvedOptions().timeZone;
const TZ_ORIGINAL = process.env.TZ;

// Zonas del proceso con las que se repiten las pruebas: contenedor Docker sin
// TZ (UTC), equipo de desarrollo en El Salvador y una zona con desfase positivo.
const ZONAS_DEL_PROCESO = ['UTC', 'America/El_Salvador', 'Asia/Tokyo'];

// Bordes del día en hora de El Salvador (UTC-6) con su instante UTC. Entre las
// 18:00 y las 23:59:59 SV la fecha UTC ya es la del día siguiente.
const BORDES_DIA_SV = [
  { utc: '2026-10-09T23:59:59.000Z', fecha: '2026-10-09', hora: '17:59:59' },
  { utc: '2026-10-10T00:00:00.000Z', fecha: '2026-10-09', hora: '18:00:00' },
  { utc: '2026-10-10T02:00:00.000Z', fecha: '2026-10-09', hora: '20:00:00' },
  { utc: '2026-10-10T05:59:59.000Z', fecha: '2026-10-09', hora: '23:59:59' },
  { utc: '2026-10-10T06:00:00.000Z', fecha: '2026-10-10', hora: '00:00:00' },
];

/**
 * Cambia la zona horaria del proceso durante la prueba `t`. Node reinicia su
 * caché de zona horaria al ASIGNAR process.env.TZ (borrarla no), así que al
 * terminar se reasigna la zona original antes de quitar la variable.
 */
function usarZonaDelProceso(t, zona) {
  process.env.TZ = zona;
  t.after(() => {
    process.env.TZ = ZONA_ORIGINAL;
    if (TZ_ORIGINAL === undefined) delete process.env.TZ;
  });
}

/** Congela `Date` (incluido `new Date()`) en el instante dado durante la prueba `t`. */
function fijarInstante(t, instanteIso) {
  t.mock.timers.enable({ apis: ['Date'], now: Date.parse(instanteIso) });
}

module.exports = { ZONAS_DEL_PROCESO, BORDES_DIA_SV, usarZonaDelProceso, fijarInstante };
