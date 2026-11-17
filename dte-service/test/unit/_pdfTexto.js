const zlib = require('node:zlib');

/**
 * Lectura mínima de los PDF que genera PDFKit, solo para pruebas. El texto
 * va comprimido (FlateDecode) y en hex dentro de operadores TJ, partido por
 * el kerning, así que buscarlo con buffer.toString() no encuentra nada.
 * No es un parser general de PDF: asume la estructura que escribe PDFKit.
 */

// Bytes 0x80-0x9F de WinAnsi que no coinciden con Latin-1.
const WINANSI_A_UNICODE = {
  0x80: '€', 0x82: '‚', 0x83: 'ƒ', 0x84: '„', 0x85: '…', 0x86: '†', 0x87: '‡', 0x88: 'ˆ', 0x89: '‰', 0x8A: 'Š',
  0x8B: '‹', 0x8C: 'Œ', 0x8E: 'Ž', 0x91: '‘', 0x92: '’', 0x93: '“', 0x94: '”', 0x95: '•', 0x96: '–', 0x97: '—',
  0x98: '˜', 0x99: '™', 0x9A: 'š', 0x9B: '›', 0x9C: 'œ', 0x9E: 'ž', 0x9F: 'Ÿ',
};

function _leerObjetos(buffer) {
  const texto = buffer.toString('latin1');
  const objetos = new Map();
  const cabecera = /(\d+) 0 obj\n/g;
  let coincidencia;
  while ((coincidencia = cabecera.exec(texto))) {
    const inicio = coincidencia.index + coincidencia[0].length;
    const inicioStream = texto.indexOf('\nstream\n', inicio);
    const finObjeto = texto.indexOf('endobj', inicio);
    if (inicioStream !== -1 && inicioStream < finObjeto) {
      const diccionario = texto.slice(inicio, inicioStream);
      const longitud = Number(/\/Length (\d+)/.exec(diccionario)[1]);
      const datos = buffer.subarray(inicioStream + 8, inicioStream + 8 + longitud);
      objetos.set(Number(coincidencia[1]), { diccionario, datos });
      cabecera.lastIndex = inicioStream + 8 + longitud;
    } else {
      objetos.set(Number(coincidencia[1]), { diccionario: texto.slice(inicio, finObjeto), datos: null });
    }
  }
  return objetos;
}

function _contenidoDePaginas(buffer) {
  const objetos = _leerObjetos(buffer);
  const raiz = [...objetos.values()].find((objeto) => /\/Type \/Pages\b/.test(objeto.diccionario));
  const kids = /\/Kids \[([^\]]*)\]/.exec(raiz.diccionario)[1].match(/\d+ 0 R/g).map((ref) => Number.parseInt(ref, 10));
  return kids.map((id) => {
    const contenido = objetos.get(Number(/\/Contents (\d+) 0 R/.exec(objetos.get(id).diccionario)[1]));
    const datos = /\/FlateDecode/.test(contenido.diccionario) ? zlib.inflateSync(contenido.datos) : contenido.datos;
    return datos.toString('latin1');
  });
}

function _decodificarHex(hex) {
  let salida = '';
  for (let i = 0; i < hex.length; i += 2) {
    const byte = Number.parseInt(hex.slice(i, i + 2), 16);
    salida += WINANSI_A_UNICODE[byte] ?? String.fromCharCode(byte);
  }
  return salida;
}

/** Texto de cada página: una línea por operador TJ. */
function textoPorPagina(buffer) {
  return _contenidoDePaginas(buffer).map((contenido) => {
    const lineas = [];
    for (const [, arreglo] of contenido.matchAll(/\[([^\]]*)\] TJ/g)) {
      lineas.push([...arreglo.matchAll(/<([0-9a-fA-F]*)>/g)].map(([, hex]) => _decodificarHex(hex)).join(''));
    }
    return lineas.join('\n');
  });
}

function textoCompleto(buffer) {
  return textoPorPagina(buffer).join('\n');
}

/** Colores RGB de relleno y trazo usados en el contenido, como [r, g, b] en 0..1. */
function coloresUsados(buffer) {
  return _contenidoDePaginas(buffer).flatMap((contenido) => [...contenido.matchAll(/(\S+) (\S+) (\S+) (?:scn|SCN)\b/g)]
    .map(([, r, g, b]) => [Number(r), Number(g), Number(b)]));
}

function contarPaginas(buffer) {
  return (buffer.toString('latin1').match(/\/Type\s*\/Page\b/g) || []).length;
}

function contarApariciones(texto, fragmento) {
  return texto.split(fragmento).length - 1;
}

module.exports = { textoPorPagina, textoCompleto, coloresUsados, contarPaginas, contarApariciones };
