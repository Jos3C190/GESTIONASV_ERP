/**
 * Sanitiza recursivamente todos los valores string de un objeto antes de
 * firmarlo, siguiendo el Manual Tecnológico v2.0, sección 6.1 (Formato y
 * Estructura de Datos):
 *
 *   "Es imperativo enviar los datos limpios. No deben enviarse caracteres
 *   inválidos, residuales o de fin de instrucción, como el punto y coma
 *   (;), al final de las cadenas de texto, en los valores de los campos o
 *   al final del documento JSON."
 *   "Toda comunicación, petición y archivo JSON debe estar codificado
 *   estrictamente bajo el estándar UTF-8..."
 *
 * Qué hace concretamente:
 *   1. Normaliza cada string a la forma Unicode NFC (evita que el mismo
 *      carácter visual — ej. una "ñ" — llegue representado de dos formas
 *      binarias distintas según cómo lo haya tecleado el usuario).
 *   2. Quita caracteres de control no imprimibles (los que nunca deberían
 *      aparecer en un campo de texto legible).
 *   3. Quita punto y coma (o punto y coma + espacios) sueltos al final de
 *      cada string — el caso concreto que menciona el manual.
 *   4. Recorta espacios en blanco sueltos al final (trailing whitespace).
 *
 * NO toca el JSON en sí (la serialización final la hace JSON.stringify de
 * forma nativa vía axios, que ya produce UTF-8 válido sin caracteres
 * residuales al final del documento — ese riesgo del manual aplica más a
 * integradores que arman el JSON concatenando texto a mano).
 */
function _sanitizarString(valor) {
  return valor
    .normalize('NFC')
    // eslint-disable-next-line no-control-regex
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, '') // caracteres de control no imprimibles
    .replace(/[;\s]+$/, ''); // ; y espacios sueltos al final
}

function sanitizarProfundo(valor) {
  if (typeof valor === 'string') {
    return _sanitizarString(valor);
  }
  if (Array.isArray(valor)) {
    return valor.map(sanitizarProfundo);
  }
  if (valor && typeof valor === 'object') {
    const limpio = {};
    for (const [clave, v] of Object.entries(valor)) {
      limpio[clave] = sanitizarProfundo(v);
    }
    return limpio;
  }
  return valor;
}

module.exports = { sanitizarProfundo };
