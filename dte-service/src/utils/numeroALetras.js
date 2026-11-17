const UNIDADES = ['', 'UNO', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS', 'SIETE', 'OCHO', 'NUEVE'];
const DIEZ_A_DIECINUEVE = ['DIEZ', 'ONCE', 'DOCE', 'TRECE', 'CATORCE', 'QUINCE', 'DIECISÉIS', 'DIECISIETE', 'DIECIOCHO', 'DIECINUEVE'];
const DECENAS = ['', '', 'VEINTE', 'TREINTA', 'CUARENTA', 'CINCUENTA', 'SESENTA', 'SETENTA', 'OCHENTA', 'NOVENTA'];
const VEINTENAS = ['', 'VEINTIUNO', 'VEINTIDÓS', 'VEINTITRÉS', 'VEINTICUATRO', 'VEINTICINCO', 'VEINTISÉIS', 'VEINTISIETE', 'VEINTIOCHO', 'VEINTINUEVE'];
const CENTENAS = ['', 'CIENTO', 'DOSCIENTOS', 'TRESCIENTOS', 'CUATROCIENTOS', 'QUINIENTOS', 'SEISCIENTOS', 'SETECIENTOS', 'OCHOCIENTOS', 'NOVECIENTOS'];
const MAXIMO = 999999999.99;

/**
 * Número de 0 a 999 en letras. `apocopado` aplica la forma usada delante de
 * MIL o MILLONES: UNO → UN y VEINTIUNO → VEINTIÚN (VEINTIÚN MIL, CIENTO UN MIL).
 */
function bloque(n, apocopado = false) {
  if (n === 0) return '';
  if (n === 100) return 'CIEN';
  const palabras = [];
  const centena = Math.floor(n / 100);
  const resto = n % 100;
  if (centena > 0) palabras.push(CENTENAS[centena]);
  if (resto >= 10 && resto < 20) {
    palabras.push(DIEZ_A_DIECINUEVE[resto - 10]);
  } else if (resto >= 21 && resto <= 29) {
    palabras.push(apocopado && resto === 21 ? 'VEINTIÚN' : VEINTENAS[resto - 20]);
  } else {
    const decena = Math.floor(resto / 10);
    const unidad = resto % 10;
    if (decena >= 2) palabras.push(DECENAS[decena]);
    if (unidad > 0) {
      if (decena >= 3) palabras.push('Y');
      palabras.push(apocopado && unidad === 1 ? 'UN' : UNIDADES[unidad]);
    }
  }
  return palabras.join(' ');
}

/**
 * Monto en letras con el formato usual de los documentos fiscales:
 *   1073.50 -> "MIL SETENTA Y TRES 50/100 DÓLARES"
 *   21000   -> "VEINTIÚN MIL 00/100 DÓLARES"
 * Hacienda no publica un algoritmo oficial; totalLetras es informativo.
 */
function numeroALetras(monto) {
  const absoluto = Math.abs(Number(monto));
  if (!Number.isFinite(absoluto) || absoluto > MAXIMO) {
    throw new Error(`Monto fuera del rango admitido para expresarlo en letras: ${monto}`);
  }
  // Se trabaja en centavos para que 2.995 no termine en "100/100".
  const totalCentavos = Math.round(absoluto * 100);
  const entero = Math.floor(totalCentavos / 100);
  const centavos = String(totalCentavos % 100).padStart(2, '0');
  if (entero === 0) return `CERO ${centavos}/100 DÓLARES`;

  const millones = Math.floor(entero / 1000000);
  const miles = Math.floor((entero % 1000000) / 1000);
  const unidades = entero % 1000;

  const partes = [];
  if (millones > 0) partes.push(millones === 1 ? 'UN MILLÓN' : `${bloque(millones, true)} MILLONES`);
  if (miles > 0) partes.push(miles === 1 ? 'MIL' : `${bloque(miles, true)} MIL`);
  if (unidades > 0) partes.push(bloque(unidades));

  return `${partes.join(' ')} ${centavos}/100 DÓLARES`;
}

module.exports = { numeroALetras };
