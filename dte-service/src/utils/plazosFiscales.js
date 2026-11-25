/**
 * Reglas de fecha y plazo del Evento de Invalidación (Manual Funcional v2.0,
 * sección VII "Plazos para aplicar evento de invalidación").
 *
 * - CCF, NR, NC, ND, CR, CL, DCL y CD: la "Fecha del Evento" es la misma
 *   fecha de generación del DTE, y el evento se transmite a más tardar el
 *   décimo día hábil del mes siguiente al período en que el DTE obtuvo sello.
 * - FE, FEX y FSE: la "Fecha del Evento" puede estar hasta 3 meses después
 *   de la fecha de generación, y el evento se transmite dentro de los 3 meses
 *   siguientes al sello de recepción.
 */
// 17 y 18: Eventos de Operaciones Especiales y de Retorno (Manual Funcional VII).
const TIPOS_FECHA_EVENTO_IGUAL_A_GENERACION = new Set(['03', '04', '05', '06', '07', '08', '09', '15', '17', '18']);
const TIPOS_PLAZO_TRES_MESES = new Set(['01', '11', '14']);

function aFecha(iso) {
  const [anio, mes, dia] = iso.split('-').map(Number);
  return new Date(Date.UTC(anio, mes - 1, dia));
}

function aIso(fecha) {
  return fecha.toISOString().slice(0, 10);
}

/** Suma meses de calendario; si el día no existe se usa el último del mes (30-nov + 3 = 28-feb). */
function sumarMeses(iso, meses) {
  const [anio, mes, dia] = iso.split('-').map(Number);
  const destino = new Date(Date.UTC(anio, mes - 1 + meses, 1));
  const ultimoDia = new Date(Date.UTC(destino.getUTCFullYear(), destino.getUTCMonth() + 1, 0)).getUTCDate();
  destino.setUTCDate(Math.min(dia, ultimoDia));
  return aIso(destino);
}

/** Domingo de Pascua (algoritmo gregoriano anónimo). */
function domingoDePascua(anio) {
  const a = anio % 19;
  const b = Math.floor(anio / 100);
  const c = anio % 100;
  const d = Math.floor(b / 4);
  const e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4);
  const k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const mes = Math.floor((h + l - 7 * m + 114) / 31);
  const dia = ((h + l - 7 * m + 114) % 31) + 1;
  return new Date(Date.UTC(anio, mes - 1, dia));
}

/**
 * Asuetos nacionales (Código de Trabajo, art. 190): 1 de enero, jueves y
 * viernes santos, 1 y 10 de mayo, 17 de junio, 6 de agosto, 15 de
 * septiembre, 2 de noviembre y 25 de diciembre. Los asuetos locales o
 * decretados se agregan con DTE_DIAS_INHABILES (YYYY-MM-DD separados por coma).
 */
function diasInhabiles(anio) {
  const fijos = ['01-01', '05-01', '05-10', '06-17', '08-06', '09-15', '11-02', '12-25'].map((md) => `${anio}-${md}`);
  const pascua = domingoDePascua(anio);
  const jueves = new Date(pascua.getTime() - 3 * 86400000);
  const viernes = new Date(pascua.getTime() - 2 * 86400000);
  const extra = (process.env.DTE_DIAS_INHABILES || '')
    .split(',')
    .map((valor) => valor.trim())
    .filter((valor) => /^\d{4}-\d{2}-\d{2}$/.test(valor));
  return new Set([...fijos, aIso(jueves), aIso(viernes), ...extra]);
}

function esHabil(fecha) {
  const diaSemana = fecha.getUTCDay();
  return diaSemana !== 0 && diaSemana !== 6 && !diasInhabiles(fecha.getUTCFullYear()).has(aIso(fecha));
}

/** Décimo día hábil del mes siguiente al de `iso`. */
function decimoDiaHabilDelMesSiguiente(iso) {
  const base = aFecha(iso);
  const fecha = new Date(Date.UTC(base.getUTCFullYear(), base.getUTCMonth() + 1, 1));
  let habiles = 0;
  while (true) {
    if (esHabil(fecha)) {
      habiles += 1;
      if (habiles === 10) return aIso(fecha);
    }
    fecha.setUTCDate(fecha.getUTCDate() + 1);
  }
}

/** "Fecha del Evento" que corresponde a un DTE invalidado hoy (fechas YYYY-MM-DD, hora de El Salvador). */
function fechaDelEventoInvalidacion(tipoDte, fecEmiDte, hoy) {
  if (TIPOS_FECHA_EVENTO_IGUAL_A_GENERACION.has(tipoDte)) return fecEmiDte;
  const maximo = sumarMeses(fecEmiDte, 3);
  if (hoy < fecEmiDte) return fecEmiDte;
  return hoy < maximo ? hoy : maximo;
}

/**
 * Último día (inclusive, hasta las 23:59:59) para transmitir la invalidación.
 * `estimado` indica que depende del calendario de días hábiles: un asueto no
 * registrado en DTE_DIAS_INHABILES haría que el plazo real sea posterior.
 */
function plazoInvalidacion(tipoDte, fechaSello) {
  if (TIPOS_PLAZO_TRES_MESES.has(tipoDte)) {
    return { regla: 'TRES_MESES_DESDE_SELLO', limite: sumarMeses(fechaSello, 3), estimado: false };
  }
  return { regla: 'DECIMO_DIA_HABIL_MES_SIGUIENTE', limite: decimoDiaHabilDelMesSiguiente(fechaSello), estimado: true };
}

/** fhProcesamiento de Hacienda llega como "DD/MM/YYYY HH:MM:SS". */
function fechaDeProcesamiento(fhProcesamiento) {
  const partes = /^(\d{2})\/(\d{2})\/(\d{4})/.exec(String(fhProcesamiento || '').trim());
  return partes ? `${partes[3]}-${partes[2]}-${partes[1]}` : null;
}

module.exports = {
  TIPOS_FECHA_EVENTO_IGUAL_A_GENERACION,
  TIPOS_PLAZO_TRES_MESES,
  sumarMeses,
  domingoDePascua,
  esHabil,
  decimoDiaHabilDelMesSiguiente,
  fechaDelEventoInvalidacion,
  plazoInvalidacion,
  fechaDeProcesamiento,
};
