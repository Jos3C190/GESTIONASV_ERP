const PDFDocument = require('pdfkit');
const QRCode = require('qrcode');
const { construirUrlConsultaPublica } = require('../utils/qrConsultaPublica');
const { numeroALetras } = require('../utils/numeroALetras');
const etiquetas = require('../utils/etiquetasCatalogo');

/**
 * Representación gráfica (PDF) de un DTE, con el layout de un DTE real
 * (encabezado con QR, cajas y tablas con barras rellenas, totales y firmas)
 * en paleta monocromática: negro, blanco y grises neutros.
 *
 * Geometría en puntos sobre papel Carta (612 × 792). PDFKit abre páginas
 * por su cuenta cuando un texto cruza page.maxY(); para que eso no ocurra,
 * el margen inferior del documento es mínimo, todo texto se dibuja con
 * `height` explícito y el límite real del contenido es PAGINA.limite.
 */
const PAGINA = Object.freeze({ ancho: 612, alto: 792, izquierda: 28, derecha: 584, superior: 28, limite: 760, pie: 772 });
const ANCHO_UTIL = PAGINA.derecha - PAGINA.izquierda;

const COLOR = Object.freeze({
  tinta: '#000000',
  inverso: '#FFFFFF',
  secundario: '#4D4D4D',
  realce: '#EDEDED',
  guia: '#9A9A9A',
});

const FUENTE = Object.freeze({ normal: 'Helvetica', negrita: 'Helvetica-Bold', cursiva: 'Helvetica-Oblique' });

const TAM = Object.freeze({
  base: 6.8,
  marca: 13,
  nombreEmisor: 7.5,
  tituloDte: 8.2,
  datoDte: 6.2,
  leyendaQr: 4.2,
  seccion: 10,
  cabecera: 6.5,
  barra: 9,
  detalle: 5.8,
  total: 7.5,
  url: 5,
  pie: 6.5,
  marcaAgua: 36,
});

const GROSOR = Object.freeze({ marco: 0.6, rejilla: 0.4, separador: 0.5 });

// Bloques de altura fija.
const ALTO = Object.freeze({
  cajaDte: 130,
  barraDte: 24,
  franjaSimulacion: 14,
  terceros: 18,
  tituloSeccion: 18,
  cabeceraTabla: 15,
  filaTabla: 14,
  cabeceraItems: 24,
  filaItemMinima: 13,
  areaItemsMinima: 44,
  barraObservaciones: 16,
  firmas: 58,
});

const SEPARACION = 8;
const ANCHO_QR_CELDA = 100;
const X_CAJA_DTE = 292;
const ANCHO_EMISOR = 254;
const X_TOTALES = 352;
const ANCHO_ETIQUETA_TOTAL = 164;
const X_ENTREGA = 252;
const X_RECIBE = 418;

const MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
const TIPOS_VENTA = new Set(['01', '03', '04', '05', '06', '11']);

// Los 27 caracteres de WinAnsi por encima de U+00FF que PDFKit sí codifica.
const WINANSI_EXTRA = new Set([
  0x20AC, 0x201A, 0x0192, 0x201E, 0x2026, 0x2020, 0x2021, 0x02C6, 0x2030, 0x0160, 0x2039, 0x0152, 0x017D, 0x2018,
  0x2019, 0x201C, 0x201D, 0x2022, 0x2013, 0x2014, 0x02DC, 0x2122, 0x0161, 0x203A, 0x0153, 0x017E, 0x0178,
]);

// ---------------------------------------------------------------------------
// Formato de texto y valores
// ---------------------------------------------------------------------------

/**
 * Las fuentes estándar de PDFKit solo codifican WinAnsi: un emoji o un
 * carácter de control saldría como glifo basura. Se conserva Latin-1 y los
 * extras de WinAnsi (comillas tipográficas, guiones, €); el resto se reduce
 * a su letra base o a "?".
 */
function _textoPdf(valor, vacio = '') {
  if (valor === null || valor === undefined) return vacio;
  const texto = String(valor).normalize('NFC').replace(/\s+/g, ' ');
  let salida = '';
  for (const caracter of texto) {
    const punto = caracter.codePointAt(0);
    if (punto < 0x20 || (punto >= 0x7F && punto < 0xA0) || /\p{Cf}/u.test(caracter)) continue;
    if (punto <= 0xFF || WINANSI_EXTRA.has(punto)) {
      salida += caracter;
      continue;
    }
    const base = caracter.normalize('NFD').replace(/[̀-ͯ]/g, '');
    salida += base && [...base].every((c) => c.codePointAt(0) <= 0xFF) ? base : '?';
  }
  salida = salida.trim();
  return salida === '' ? vacio : salida;
}

function _numero(valor) {
  if (valor === null || valor === undefined || valor === '') return null;
  const numero = Number(valor);
  return Number.isFinite(numero) ? numero : null;
}

function _formatoMoneda(valor, decimales = 2) {
  const numero = _numero(valor);
  if (numero === null) return '-';
  const [entero, fraccion] = Math.abs(numero).toFixed(decimales).split('.');
  const conMiles = entero.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  const signo = numero < 0 && Number(Math.abs(numero).toFixed(decimales)) !== 0 ? '-' : '';
  return `${signo}$ ${conMiles}.${fraccion}`;
}

/** Precio unitario: al menos 2 decimales, hasta 6 si el JSON los trae. */
function _formatoPrecio(valor) {
  const numero = _numero(valor);
  if (numero === null) return '-';
  const decimales = (String(numero).split('.')[1] || '').length;
  return _formatoMoneda(numero, Math.min(6, Math.max(2, decimales)));
}

function _formatoCantidad(valor) {
  const numero = _numero(valor);
  if (numero === null) return valor === null || valor === undefined ? '-' : String(valor);
  return Number.isInteger(numero) ? String(numero) : numero.toFixed(8).replace(/0+$/, '').replace(/\.$/, '');
}

/** "2026-09-28" → "28 Sep 2026", sin pasar por Date (no hay zona horaria). */
function _formatoFecha(valor) {
  const partes = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(valor ?? ''));
  if (!partes) return valor ? String(valor) : null;
  const mes = MESES[Number(partes[2]) - 1];
  return mes ? `${partes[3]} ${mes} ${partes[1]}` : String(valor);
}

function _fechaRepresentacion(valor) {
  if (typeof valor === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(valor)) return _formatoFecha(valor);
  const fecha = valor instanceof Date && !Number.isNaN(valor.getTime()) ? valor : new Date();
  // El Salvador usa UTC-6 todo el año (no tiene horario de verano).
  return _formatoFecha(new Date(fecha.getTime() - 6 * 3600 * 1000).toISOString().slice(0, 10));
}

/** NIT de 14 dígitos (0614-151220-104-5) o DUI/NIT homologado de 9 (01234567-8). */
function _formatoNit(valor) {
  const texto = String(valor ?? '').trim();
  if (/^\d{14}$/.test(texto)) return `${texto.slice(0, 4)}-${texto.slice(4, 10)}-${texto.slice(10, 13)}-${texto.slice(13)}`;
  if (/^\d{9}$/.test(texto)) return `${texto.slice(0, 8)}-${texto.slice(8)}`;
  return texto || null;
}

function _formatoNrc(valor) {
  const texto = String(valor ?? '').trim();
  return /^\d{2,8}$/.test(texto) ? `${texto.slice(0, -1)}-${texto.slice(-1)}` : texto || null;
}

function _formatoTelefono(valor) {
  const texto = String(valor ?? '').trim();
  return /^\d{8}$/.test(texto) ? `${texto.slice(0, 4)}-${texto.slice(4)}` : texto || null;
}

/** Formatea según CAT-022: 36 = NIT, 13 = DUI; otros documentos tal cual. */
function _formatoDocumento(numero, codigoTipo) {
  if (numero === null || numero === undefined) return null;
  if (codigoTipo === '36' || codigoTipo === '13') return _formatoNit(numero);
  return String(numero);
}

function _modeloFacturacion(valor) {
  return Number(valor) === 1 ? 'Previo' : Number(valor) === 2 ? 'Diferido' : String(valor ?? '-');
}

function _tipoTransmision(valor) {
  return Number(valor) === 1 ? 'Normal' : Number(valor) === 2 ? 'Contingencia' : String(valor ?? '-');
}

// ---------------------------------------------------------------------------
// Primitivas de dibujo
// ---------------------------------------------------------------------------

/** Y de la línea para centrar verticalmente texto en mayúsculas dentro de una celda. */
function _yCentrado(y, alto, tam) {
  return y + (alto - 0.718 * tam) / 2;
}

function _texto(doc, valor, x, y, {
  ancho, alto, alinear = 'left', fuente = FUENTE.normal, tam = TAM.base, color = COLOR.tinta,
  elipsis = false, enlace, espaciado, vacio = '',
} = {}) {
  const texto = _textoPdf(valor, vacio);
  if (!texto) return;
  doc.font(fuente).fontSize(tam).fillColor(color);
  doc.text(texto, x, y, {
    width: ancho,
    height: alto ?? Math.max(PAGINA.alto - y, tam * 2),
    align: alinear,
    ellipsis: elipsis ? '…' : undefined,
    link: enlace,
    characterSpacing: espaciado,
  });
}

function _altoLinea(doc, tam, fuente = FUENTE.normal) {
  return doc.font(fuente).fontSize(tam).currentLineHeight(true);
}

function _alto(doc, valor, ancho, { fuente = FUENTE.normal, tam = TAM.base, espaciado } = {}) {
  const texto = _textoPdf(valor);
  doc.font(fuente).fontSize(tam);
  if (!texto) return doc.currentLineHeight(true);
  return doc.heightOfString(texto, { width: ancho, characterSpacing: espaciado });
}

function _rect(doc, x, y, ancho, alto, { relleno, borde, grosor = GROSOR.rejilla } = {}) {
  doc.save();
  doc.rect(x, y, ancho, alto);
  if (relleno && borde) doc.lineWidth(grosor).fillAndStroke(relleno, borde);
  else if (relleno) doc.fill(relleno);
  else doc.lineWidth(grosor).stroke(borde || COLOR.tinta);
  doc.restore();
}

function _linea(doc, x1, y1, x2, y2, { color = COLOR.tinta, grosor = GROSOR.rejilla } = {}) {
  doc.save().moveTo(x1, y1).lineTo(x2, y2).lineWidth(grosor).stroke(color).restore();
}

/** Una sola línea; reduce la fuente hasta que quepa y, si aun así no cabe, corta con "…". */
function _textoAjustado(doc, valor, x, y, ancho, {
  tam = TAM.base, tamMin = 5, fuente = FUENTE.normal, alinear = 'left', color = COLOR.tinta, vacio = '', enlace,
} = {}) {
  const texto = _textoPdf(valor, vacio);
  if (!texto) return;
  let tamFinal = tam;
  doc.font(fuente);
  while (tamFinal > tamMin && doc.fontSize(tamFinal).widthOfString(texto) > ancho) tamFinal -= 0.25;
  const desplazamiento = ((tam - tamFinal) * 0.718) / 2;
  _texto(doc, texto, x, y + desplazamiento, {
    ancho, alto: _altoLinea(doc, tamFinal, fuente) + 0.5, alinear, fuente, tam: tamFinal, color, elipsis: true, enlace,
  });
}

/** Bloque de texto centrado (puede envolver); devuelve su alto. */
function _textoCentrado(doc, valor, x, y, ancho, opciones = {}) {
  const alto = _alto(doc, valor, ancho, opciones);
  _texto(doc, valor, x, y, { ...opciones, ancho, alto: alto + 0.5, alinear: 'center' });
  return alto;
}

/** Barra negra con texto blanco centrado (una o varias líneas). */
function _barra(doc, x, y, ancho, alto, lineas, { tam = TAM.cabecera, fuente = FUENTE.negrita } = {}) {
  _rect(doc, x, y, ancho, alto, { relleno: COLOR.tinta });
  const lista = Array.isArray(lineas) ? lineas : [lineas];
  const altoLinea = _altoLinea(doc, tam, fuente);
  let yTexto = y + (alto - ((lista.length - 1) * altoLinea + 0.718 * tam)) / 2;
  for (const linea of lista) {
    _texto(doc, linea, x + 2, yTexto, {
      ancho: ancho - 4, alto: altoLinea + 0.5, alinear: 'center', fuente, tam, color: COLOR.inverso, elipsis: true,
    });
    yTexto += altoLinea;
  }
}

/**
 * "Etiqueta: valor" con sangría colgante: el valor envuelve alineado tras la
 * etiqueta, como en la dirección del DTE de referencia. Devuelve el alto
 * ocupado; con `medir` no dibuja nada.
 */
function _etiquetaValor(doc, x, y, ancho, etiqueta, valor, {
  tam = TAM.base, medir = false, maxLineas, color = COLOR.tinta, fuenteEtiqueta = FUENTE.negrita,
} = {}) {
  const textoEtiqueta = `${etiqueta} `;
  const anchoEtiqueta = doc.font(fuenteEtiqueta).fontSize(tam).widthOfString(textoEtiqueta);
  const anchoValor = Math.max(12, ancho - anchoEtiqueta);
  const altoLinea = _altoLinea(doc, tam);
  const textoValor = _textoPdf(valor);
  let alto = textoValor ? doc.heightOfString(textoValor, { width: anchoValor }) : altoLinea;
  if (maxLineas) alto = Math.min(alto, altoLinea * maxLineas);
  alto = Math.max(alto, altoLinea);
  if (!medir) {
    _texto(doc, textoEtiqueta, x, y, { ancho: anchoEtiqueta + 2, alto: altoLinea + 0.5, fuente: fuenteEtiqueta, tam, color });
    if (textoValor) {
      _texto(doc, textoValor, x + anchoEtiqueta, y, { ancho: anchoValor, alto: alto + 0.5, tam, color, elipsis: Boolean(maxLineas) });
    }
  }
  return alto;
}

// ---------------------------------------------------------------------------
// Datos derivados del DTE (puros: nunca mutan el JSON)
// ---------------------------------------------------------------------------

function _datosEmisor(dte) {
  const emisor = dte.emisor || {};
  return {
    nombre: emisor.nombre || emisor.nombreComercial || null,
    nombreComercial: emisor.nombreComercial || null,
    nit: _formatoNit(emisor.nit ?? emisor.numDocumento),
    nrc: _formatoNrc(emisor.nrc),
    actividad: emisor.descActividad || emisor.codActividad || null,
    direccion: etiquetas.direccionLegible(emisor.direccion),
    telefono: _formatoTelefono(emisor.telefono),
    correo: emisor.correo || null,
    establecimiento: etiquetas.tipoEstablecimientoDesdeNumeroControl(dte.identificacion.numeroControl),
  };
}

function _datosReceptor(dte) {
  const tipoDte = dte.identificacion.tipoDte;
  const titulo = tipoDte === '14' ? 'Información del sujeto excluido'
    : tipoDte === '15' ? 'Información del donante'
      : 'Información del receptor';
  const condicion = Array.isArray(dte.cuerpoDocumento) ? dte.resumen?.condicionOperacion : undefined;
  const textoCondicion = condicion === undefined || condicion === null ? null : etiquetas.nombreCondicionOperacion(condicion);
  const porDefecto = tipoDte === '01' ? 'Consumidor final' : null;
  const receptor = dte.receptor;
  if (!receptor) return { titulo, nombre: porDefecto, condicion: textoCondicion };

  // El CCF identifica al receptor con NIT directo, sin tipoDocumento.
  const codigoTipo = receptor.tipoDocumento ?? (receptor.nit ? '36' : null);
  const numero = receptor.numDocumento ?? receptor.nit ?? null;
  const direccion = receptor.direccion
    ? etiquetas.direccionLegible(receptor.direccion)
    : [receptor.complemento, receptor.nombrePais || etiquetas.nombrePais(receptor.codPais)].filter(Boolean).join(', ') || null;
  return {
    titulo,
    nombre: receptor.nombre || porDefecto,
    nombreComercial: receptor.nombreComercial || null,
    actividad: receptor.descActividad || receptor.codActividad || null,
    direccion,
    nrc: _formatoNrc(receptor.nrc),
    tipoDocumento: codigoTipo ? etiquetas.nombreTipoDocumentoIdentificacion(codigoTipo) : null,
    numDocumento: _formatoDocumento(numero, codigoTipo),
    correo: receptor.correo || null,
    telefono: _formatoTelefono(receptor.telefono),
    condicion: textoCondicion,
    // Nota de remisión: título a que se remiten los bienes (CAT-025) en lugar de la condición.
    bienTitulo: receptor.bienTitulo ? etiquetas.nombreBienTitulo(receptor.bienTitulo) : null,
  };
}

function _datosFirmas(dte, emisor, receptor) {
  const extension = dte.extension || {};
  return {
    entrega: {
      nombre: extension.nombEntrega || emisor.nombre,
      documento: extension.docuEntrega ? _formatoNit(extension.docuEntrega) : emisor.nit,
    },
    recibe: {
      nombre: extension.nombRecibe || receptor.nombre,
      documento: extension.docuRecibe ? _formatoNit(extension.docuRecibe) : receptor.numDocumento,
    },
  };
}

const _celdaMoneda = (campo, total) => ({ alinear: 'right', campo, total, valor: (item) => _formatoMoneda(item[campo]) });

const COLUMNAS_VENTA = [
  { titulo: ['No.'], ancho: 22, alinear: 'center', valor: (item) => item.numItem },
  { titulo: ['Cant.'], ancho: 30, alinear: 'center', valor: (item) => _formatoCantidad(item.cantidad) },
  { titulo: ['Unidad'], ancho: 36, alinear: 'center', envolver: true, valor: (item) => etiquetas.nombreUnidadMedida(item.uniMedida) },
  {
    titulo: ['Descripción'], ancho: 190, alinear: 'left', envolver: true,
    valor: (item) => item.descripcion,
    detalle: (item) => [
      item.codigo ? `Cód. ${item.codigo}` : null,
      item.numeroDocumento ? `Doc. relacionado ${item.numeroDocumento}` : null,
    ].filter(Boolean).join(' · '),
  },
  { titulo: ['Precio', 'unitario'], ancho: 46, alinear: 'right', valor: (item) => _formatoPrecio(item.precioUni) },
  { titulo: ['Descuento', 'por ítem'], ancho: 46, ..._celdaMoneda('montoDescu') },
  { titulo: ['Ventas no', 'sujetas'], ancho: 46, ..._celdaMoneda('ventaNoSuj', 'totalNoSuj') },
  { titulo: ['Ventas', 'exentas'], ancho: 46, ..._celdaMoneda('ventaExenta', 'totalExenta') },
  { titulo: ['Otros montos', 'no afectos'], ancho: 48, ..._celdaMoneda('noGravado', 'totalNoGravado') },
  { titulo: ['Ventas', 'gravadas'], ancho: 46, ..._celdaMoneda('ventaGravada', 'totalGravada') },
];

const _columnaDocumentoOrigen = [
  { titulo: ['No.'], ancho: 22, alinear: 'center', valor: (item) => item.numItem },
  { titulo: ['Tipo de', 'documento'], alinear: 'left', envolver: true, valor: (item) => etiquetas.nombreTipoDte(item.tipoDte) },
  { titulo: ['Tipo de', 'generación'], alinear: 'center', envolver: true, valor: (item) => etiquetas.nombreTipoGeneracion(item.tipoGeneracion) },
];

// Cada perfil suma exactamente ANCHO_UTIL (556 pt).
const PERFILES_COLUMNAS = {
  // Comprobante de retención
  '07': [
    { ..._columnaDocumentoOrigen[0] },
    { ..._columnaDocumentoOrigen[1], ancho: 88 },
    { ..._columnaDocumentoOrigen[2], ancho: 46 },
    // numDocumento: nombre del campo antes del schema de agosto de 2026.
    { titulo: ['Número de', 'documento'], ancho: 138, alinear: 'left', valor: (item) => item.numeroDocumento ?? item.numDocumento },
    { titulo: ['Fecha de', 'emisión'], ancho: 50, alinear: 'center', valor: (item) => _formatoFecha(item.fechaEmision) },
    { titulo: ['Descripción'], ancho: 90, alinear: 'left', envolver: true, valor: (item) => item.descripcion },
    { titulo: ['Cód.', 'ret.'], ancho: 30, alinear: 'center', valor: (item) => item.codigoRetencionMH },
    { titulo: ['Monto', 'sujeto'], ancho: 46, ..._celdaMoneda('montoSujetoGrav', 'totalSujetoRetencion') },
    { titulo: ['IVA', 'retenido'], ancho: 46, ..._celdaMoneda('ivaRetenido', 'totalIvaRetenido') },
  ],
  // Comprobante de liquidación
  '08': [
    { ..._columnaDocumentoOrigen[0] },
    { ..._columnaDocumentoOrigen[1], ancho: 80 },
    { ..._columnaDocumentoOrigen[2], ancho: 44 },
    {
      titulo: ['Número de', 'documento'], ancho: 128, alinear: 'left',
      valor: (item) => item.numeroDocumento, detalle: (item) => item.observaciones,
    },
    { titulo: ['Fecha de', 'emisión'], ancho: 48, alinear: 'center', valor: (item) => _formatoFecha(item.fechaEmision) },
    { titulo: ['Ventas no', 'sujetas'], ancho: 46, ..._celdaMoneda('ventaNoSuj', 'totalNoSuj') },
    { titulo: ['Ventas', 'exentas'], ancho: 46, ..._celdaMoneda('ventaExenta', 'totalExenta') },
    { titulo: ['Ventas', 'gravadas'], ancho: 46, ..._celdaMoneda('ventaGravada', 'totalGravada') },
    { titulo: ['Exporta-', 'ciones'], ancho: 50, ..._celdaMoneda('exportaciones', 'exportacion') },
    { titulo: ['IVA'], ancho: 46, ..._celdaMoneda('ivaItem', 'ivaPerci') },
  ],
  // Factura de sujeto excluido
  '14': [
    { titulo: ['No.'], ancho: 22, alinear: 'center', valor: (item) => item.numItem },
    { titulo: ['Cant.'], ancho: 34, alinear: 'center', valor: (item) => _formatoCantidad(item.cantidad) },
    { titulo: ['Unidad'], ancho: 40, alinear: 'center', envolver: true, valor: (item) => etiquetas.nombreUnidadMedida(item.uniMedida) },
    {
      titulo: ['Descripción'], ancho: 276, alinear: 'left', envolver: true,
      valor: (item) => item.descripcion, detalle: (item) => (item.codigo ? `Cód. ${item.codigo}` : null),
    },
    { titulo: ['Precio', 'unitario'], ancho: 60, alinear: 'right', valor: (item) => _formatoPrecio(item.precioUni) },
    { titulo: ['Descuento', 'por ítem'], ancho: 60, ..._celdaMoneda('montoDescu') },
    { titulo: ['Compra'], ancho: 64, ..._celdaMoneda('compra', 'totalCompra') },
  ],
  // Comprobante de donación
  '15': [
    { titulo: ['No.'], ancho: 22, alinear: 'center', valor: (item) => item.numItem },
    { titulo: ['Tipo de', 'donación'], ancho: 50, alinear: 'center', envolver: true, valor: (item) => etiquetas.nombreTipoDonacion(item.tipoDonacion) },
    { titulo: ['Cant.'], ancho: 34, alinear: 'center', valor: (item) => _formatoCantidad(item.cantidad) },
    { titulo: ['Unidad'], ancho: 40, alinear: 'center', envolver: true, valor: (item) => etiquetas.nombreUnidadMedida(item.uniMedida) },
    {
      titulo: ['Descripción'], ancho: 236, alinear: 'left', envolver: true,
      valor: (item) => item.descripcion, detalle: (item) => (item.codigo ? `Cód. ${item.codigo}` : null),
    },
    { titulo: ['Tipo de', 'depreciación'], ancho: 50, alinear: 'center', valor: (item) => item.tipoDepreciacion },
    { titulo: ['Valor', 'unitario'], ancho: 60, alinear: 'right', valor: (item) => _formatoPrecio(item.valorUni) },
    { titulo: ['Valor'], ancho: 64, ..._celdaMoneda('valor', 'valorTotal') },
  ],
};

function _columnasPara(tipoDte) {
  return PERFILES_COLUMNAS[tipoDte] || COLUMNAS_VENTA;
}

const ETIQUETAS_DCL = {
  periodoLiquidacionFechaInicio: 'Inicio del período',
  periodoLiquidacionFechaFin: 'Fin del período',
  codLiquidacion: 'Código de liquidación',
  cantidadDoc: 'Cantidad de documentos',
  valorOperaciones: 'Valor de operaciones',
  montoSinPercepcion: 'Monto sin percepción',
  descripSinPercepcion: 'Descripción sin percepción',
  porcentComision: 'Porcentaje de comisión',
};

const TOTALES_DCL = [
  ['subTotal', 'Sub-Total:'],
  ['iva', 'IVA:'],
  ['montoSujetoPercepcion', 'Monto sujeto a percepción:'],
  ['ivaPercibido', 'IVA percibido:'],
  ['comision', 'Comisión:'],
  ['ivaComision', 'IVA de comisión:'],
];

function _etiquetaCampo(campo) {
  if (ETIQUETAS_DCL[campo]) return ETIQUETAS_DCL[campo];
  const palabras = campo.replace(/([a-z])([A-Z])/g, '$1 $2').toLowerCase();
  return palabras.charAt(0).toUpperCase() + palabras.slice(1);
}

function _valorCampoDcl(campo, valor) {
  if (valor === null || valor === undefined) return '-';
  if (/fecha/i.test(campo)) return _formatoFecha(valor);
  if (/^cantidad/i.test(campo)) return _formatoCantidad(valor);
  if (/^porcent/i.test(campo)) return `${_formatoCantidad(valor)} %`;
  return typeof valor === 'number' ? _formatoMoneda(valor) : String(valor);
}

/**
 * Filas del cuadro de totales en el orden aritmético de Hacienda. Una fila
 * aparece si su campo existe en el resumen. El IVA se imprime una sola vez:
 * los builders lo llevan a la vez en totalIva y en tributos (código 20).
 */
function _filasTotales(dte) {
  const filas = [];
  const agregar = (etiqueta, valor, estilo = {}) => {
    if (valor !== undefined) filas.push({ etiqueta, valor: valor ?? 0, ...estilo });
  };

  if (!Array.isArray(dte.cuerpoDocumento)) {
    const cuerpo = dte.cuerpoDocumento || {};
    for (const [campo, etiqueta] of TOTALES_DCL) agregar(etiqueta, cuerpo[campo]);
    agregar('LÍQUIDO A PAGAR:', cuerpo.liquidoApagar, { destacada: true });
    return filas;
  }

  const resumen = dte.resumen || {};
  const tributos = Array.isArray(resumen.tributos) ? resumen.tributos : [];
  const ivaRetenido = resumen.ivaRete1 !== undefined ? resumen.ivaRete1 : resumen.ivaRete;

  if (TIPOS_VENTA.has(dte.identificacion.tipoDte)) {
    const tributoIva = tributos.find((tributo) => tributo.codigo === '20');
    const iva = resumen.totalIva ?? tributoIva?.valor;
    const otrosTributos = tributos.filter((tributo) => tributo.codigo !== '20');
    const sumaOtros = otrosTributos.reduce((suma, tributo) => suma + (Number(tributo.valor) || 0), 0);
    const base = (resumen.subTotal ?? resumen.subTotalVentas ?? 0) + (resumen.seguro ?? 0) + (resumen.flete ?? 0);
    // Con nuestros builders el IVA se suma a la base (totalPagar = base + IVA).
    // Si no cuadra como sumando (precios con IVA incluido, o la Nota de
    // remisión, que lo informa sin cobrarlo), se presenta como informativo.
    const ivaAditivo = iva !== undefined && iva !== null && resumen.montoTotalOperacion !== undefined
      && Math.abs(base + Number(iva) + sumaOtros - Number(resumen.montoTotalOperacion)) < 0.005;
    const tienePagar = resumen.totalPagar !== undefined;

    agregar('Suma de operaciones:', resumen.subTotalVentas, { negrita: true });
    agregar('Monto global de descuento, bonificación, rebajas y otros a ventas no sujetas:', resumen.descuNoSuj);
    agregar('Monto global de descuento, bonificación, rebajas y otros a ventas exentas:', resumen.descuExenta);
    agregar('Monto global de descuento, bonificación, rebajas y otros a ventas gravadas:', resumen.descuGravada);
    agregar('Sub-Total:', resumen.subTotal, { negrita: true });
    if (ivaAditivo) agregar('IVA 13%:', iva);
    for (const tributo of otrosTributos) agregar(`${tributo.descripcion || etiquetas.nombreTributo(tributo.codigo)}:`, tributo.valor);
    agregar('Seguro:', resumen.seguro);
    agregar('Flete:', resumen.flete);
    if (tienePagar) agregar('Monto Total de la Operación:', resumen.montoTotalOperacion);
    agregar('IVA Percibido:', resumen.ivaPerci);
    agregar('IVA Retenido:', ivaRetenido);
    agregar('Retención Renta:', resumen.reteRenta);
    agregar('Total otros montos no afectos:', resumen.totalNoGravado);
    if (Number(resumen.saldoFavor)) agregar('Saldo a favor:', resumen.saldoFavor);
    // La Nota de remisión no tiene totalPagar: su total es el monto de la operación.
    if (tienePagar) agregar('TOTAL A PAGAR:', resumen.totalPagar, { destacada: true });
    else agregar('MONTO TOTAL DE LA OPERACIÓN:', resumen.montoTotalOperacion, { destacada: true });
    if (!ivaAditivo && Number(iva) > 0) agregar('IVA 13% (informativo):', iva, { informativa: true });
    return filas;
  }

  // Resto de tipos (07, 08, 14, 15 y desconocidos): lista genérica ordenada.
  agregar('Total sujeto a retención:', resumen.totalSujetoRetencion);
  agregar('Total ventas no sujetas:', resumen.totalNoSuj);
  agregar('Total ventas exentas:', resumen.totalExenta);
  agregar('Total ventas gravadas:', resumen.totalGravada);
  agregar('Total exportaciones:', resumen.exportacion);
  agregar('Suma de operaciones:', resumen.subTotalVentas, { negrita: true });
  agregar('Total compra:', resumen.totalCompra, { negrita: true });
  agregar('Descuento:', resumen.descu);
  agregar('Total descuento:', resumen.totalDescu);
  agregar('Sub-Total:', resumen.subTotal, { negrita: true });
  for (const tributo of tributos) {
    // En el CL el IVA del tributo 20 es el mismo IVA percibido.
    if (tributo.codigo === '20' && resumen.ivaPerci !== undefined) continue;
    agregar(`${tributo.descripcion || etiquetas.nombreTributo(tributo.codigo)}:`, tributo.valor);
  }
  // En el comprobante de retención es el IVA generado sobre el monto sujeto, no un cobro.
  const etiquetaIva = dte.identificacion.tipoDte === '07' ? 'IVA generado 13%:' : 'IVA:';
  if (Number(resumen.totalIva)) agregar(etiquetaIva, resumen.totalIva);
  agregar('IVA Percibido:', resumen.ivaPerci);
  agregar('IVA Retenido:', ivaRetenido);
  agregar('Retención Renta:', resumen.reteRenta);
  agregar('Monto Total de la Operación:', resumen.montoTotalOperacion);
  const destacadas = [
    ['totalPagar', 'TOTAL A PAGAR:'],
    ['liquidoApagar', 'LÍQUIDO A PAGAR:'],
    ['total', 'TOTAL:'],
    ['valorTotal', 'VALOR TOTAL:'],
    ['totalIvaRetenido', 'TOTAL IVA RETENIDO:'],
  ];
  const destacada = destacadas.find(([campo]) => resumen[campo] !== undefined);
  if (destacada) agregar(destacada[1], resumen[destacada[0]], { destacada: true });
  return filas;
}

function _totalEnLetras(dte, filasTotales) {
  const fuente = Array.isArray(dte.cuerpoDocumento) ? dte.resumen : dte.cuerpoDocumento;
  if (fuente?.totalLetras) return fuente.totalLetras;
  // Solo 01, 03 y DCL traen totalLetras; para el resto se calcula del total destacado.
  const total = _numero(filasTotales.find((fila) => fila.destacada)?.valor);
  return total === null || total < 0 ? null : numeroALetras(total);
}

function _lineasObservaciones(dte) {
  const lineas = [];
  const resumen = Array.isArray(dte.cuerpoDocumento) ? (dte.resumen || {}) : (dte.cuerpoDocumento || {});
  const observaciones = resumen.observaciones ?? dte.extension?.observaciones;
  if (observaciones) lineas.push({ valor: observaciones });
  for (const pago of Array.isArray(dte.resumen?.pagos) ? dte.resumen.pagos : []) {
    // CAT-017 99 es «Otros (se debe indicar el medio de pago)»: el paréntesis es
    // una instrucción al emisor, y el medio viaja en referencia ("Tarjeta Wompi …").
    const otroMedio = String(pago.codigo) === '99' && pago.referencia;
    const forma = otroMedio ? `Otros (${pago.referencia})` : pago.codigo ? etiquetas.nombreFormaPago(pago.codigo) : 'No especificada';
    const partes = [forma, _formatoMoneda(pago.montoPago)];
    if (pago.referencia && !otroMedio) partes.push(`Ref. ${pago.referencia}`);
    if (pago.plazo) partes.push(`Plazo ${pago.plazo}${pago.periodo ? ` (${pago.periodo})` : ''}`);
    lineas.push({ etiqueta: 'Forma de pago:', valor: partes.join(' · ') });
  }
  if (dte.resumen?.numPagoElectronico) lineas.push({ etiqueta: 'Número de pago electrónico:', valor: dte.resumen.numPagoElectronico });
  const identificacion = dte.identificacion;
  if (Number(identificacion.tipoOperacion) === 2 || identificacion.tipoContingencia) {
    const contingencia = [etiquetas.nombreContingencia(identificacion.tipoContingencia), identificacion.motivoContin].filter(Boolean);
    lineas.push({ etiqueta: 'Contingencia:', valor: contingencia.join(' · ') || '-' });
  }
  if (dte.resumen?.descIncoterms || dte.resumen?.codIncoterms) {
    lineas.push({ etiqueta: 'Incoterms:', valor: dte.resumen.descIncoterms || dte.resumen.codIncoterms });
  }
  return lineas;
}

// ---------------------------------------------------------------------------
// Paginación
// ---------------------------------------------------------------------------

/** Página adicional con un encabezado compacto que identifica el documento. */
function _nuevaPagina(ctx) {
  const { doc, dte } = ctx;
  doc.addPage();
  const y = PAGINA.superior;
  _texto(doc, `${ctx.nombreTipo.toUpperCase()} (continuación)`, PAGINA.izquierda, y + 2, {
    ancho: 260, alto: 11, fuente: FUENTE.negrita, tam: 8,
  });
  const xDerecha = 300;
  const anchoDerecha = PAGINA.derecha - xDerecha;
  _texto(doc, `Número de Control: ${_textoPdf(dte.identificacion.numeroControl, '-')}`, xDerecha, y, {
    ancho: anchoDerecha, alto: 9, alinear: 'right', tam: TAM.pie,
  });
  _texto(doc, `Código de Generación: ${_textoPdf(dte.identificacion.codigoGeneracion, '-')}`, xDerecha, y + 9, {
    ancho: anchoDerecha, alto: 9, alinear: 'right', tam: TAM.pie,
  });
  _linea(doc, PAGINA.izquierda, y + 22, PAGINA.derecha, y + 22, { grosor: GROSOR.marco });
  ctx.y = y + 30;
}

function _asegurarEspacio(ctx, alto) {
  if (ctx.y + alto > PAGINA.limite) _nuevaPagina(ctx);
}

// ---------------------------------------------------------------------------
// Secciones
// ---------------------------------------------------------------------------

function _dibujarBloqueEmisor(ctx) {
  const { doc, emisor, opciones } = ctx;
  const x = PAGINA.izquierda;
  let y = PAGINA.superior;

  if (opciones.logoPngBuffer) {
    doc.image(opciones.logoPngBuffer, x + (ANCHO_EMISOR - 160) / 2, y, { fit: [160, 50], align: 'center', valign: 'center' });
    y += 56;
    y += _textoCentrado(doc, emisor.nombre, x, y, ANCHO_EMISOR, { fuente: FUENTE.negrita, tam: TAM.nombreEmisor }) + 1;
    if (emisor.nombreComercial && emisor.nombreComercial !== emisor.nombre) {
      y += _textoCentrado(doc, emisor.nombreComercial, x, y, ANCHO_EMISOR, { tam: TAM.base, color: COLOR.secundario }) + 1;
    }
  } else {
    // Sin logo, el nombre comercial hace de membrete tipográfico.
    const membrete = emisor.nombreComercial || emisor.nombre;
    y += 4;
    y += _textoCentrado(doc, membrete ? membrete.toUpperCase() : null, x, y, ANCHO_EMISOR, {
      fuente: FUENTE.negrita, tam: TAM.marca, espaciado: 1.5,
    }) + 5;
    if (emisor.nombre && emisor.nombre !== membrete) {
      y += _textoCentrado(doc, emisor.nombre, x, y, ANCHO_EMISOR, { fuente: FUENTE.negrita, tam: TAM.nombreEmisor }) + 1;
    }
  }

  y += 5;
  const filas = [
    ['NIT:', emisor.nit],
    ['NRC:', emisor.nrc],
    ['Actividad económica:', emisor.actividad],
    ['Dirección:', emisor.direccion],
    ['Número de teléfono:', emisor.telefono],
    ['Correo electrónico:', emisor.correo],
  ];
  if (emisor.establecimiento) filas.push(['Tipo de establecimiento:', emisor.establecimiento]);
  for (const [etiqueta, valor] of filas) {
    y += _etiquetaValor(doc, x, y, ANCHO_EMISOR, etiqueta, valor) + 1.2;
  }
  return y;
}

function _dibujarCeldaQr(ctx, x, y, ancho, alto) {
  const { doc, opciones } = ctx;
  const leyenda = opciones.simulation
    ? 'Los documentos simulados no se registran en el Ministerio de Hacienda'
    : 'Escanea este QR para ir al sitio del Ministerio de Hacienda y validar la información aquí contenida';
  const altoLeyenda = _textoCentrado(doc, leyenda, x + 4, y + 4, ancho - 8, { tam: TAM.leyendaQr });
  const lado = 84;
  const xQr = x + (ancho - lado) / 2;
  const yQr = Math.min(y + 4 + altoLeyenda + 2, y + alto - lado - 2);
  if (opciones.qrPngBuffer) {
    doc.image(opciones.qrPngBuffer, xQr, yQr, { width: lado });
    doc.link(xQr, yQr, lado, lado, opciones.urlConsulta);
    return;
  }
  const margen = 6;
  doc.save().dash(2, { space: 2 });
  _rect(doc, xQr + margen, yQr + margen, lado - margen * 2, lado - margen * 2, { borde: COLOR.guia, grosor: GROSOR.rejilla });
  doc.undash().restore();
  _texto(doc, 'SIN CÓDIGO QR', xQr + margen, yQr + lado / 2 - 8, {
    ancho: lado - margen * 2, alto: 9, alinear: 'center', fuente: FUENTE.negrita, tam: 6, color: COLOR.secundario,
  });
  _texto(doc, 'Documento simulado', xQr + margen, yQr + lado / 2 + 1, {
    ancho: lado - margen * 2, alto: 8, alinear: 'center', tam: 5, color: COLOR.secundario,
  });
}

function _dibujarCajaDte(ctx) {
  const { doc, dte, opciones } = ctx;
  const identificacion = dte.identificacion;
  const x = X_CAJA_DTE;
  const y = PAGINA.superior;
  const ancho = PAGINA.derecha - x;
  const yCuerpo = y + ALTO.barraDte;

  _barra(doc, x, y, ancho, ALTO.barraDte, ['DOCUMENTO TRIBUTARIO ELECTRÓNICO', ctx.nombreTipo.toUpperCase()], { tam: TAM.tituloDte });
  _linea(doc, x + ANCHO_QR_CELDA, yCuerpo, x + ANCHO_QR_CELDA, y + ALTO.cajaDte, { grosor: GROSOR.rejilla });
  _dibujarCeldaQr(ctx, x, yCuerpo, ANCHO_QR_CELDA, ALTO.cajaDte - ALTO.barraDte);

  const xDatos = x + ANCHO_QR_CELDA + 4;
  const anchoDatos = ancho - ANCHO_QR_CELDA - 8;
  let yDatos = yCuerpo + 5;
  const par = (etiqueta, valor) => {
    _texto(doc, etiqueta, xDatos, yDatos, { ancho: anchoDatos, alto: 9, alinear: 'center', fuente: FUENTE.negrita, tam: TAM.cabecera });
    _textoAjustado(doc, valor, xDatos, yDatos + 8.5, anchoDatos, { tam: TAM.datoDte, tamMin: 4.8, alinear: 'center', vacio: '-' });
    yDatos += 18.5;
  };
  par('Código de Generación', identificacion.codigoGeneracion);
  par(opciones.simulation ? 'Identificador simulado' : 'Sello de Recepción', opciones.selloRecepcion);
  par('Número de Control del DTE', identificacion.numeroControl);

  yDatos += 3;
  const anchoDerecha = 58;
  const fila = (etiqueta, valor, etiquetaDerecha, valorDerecha) => {
    _etiquetaValor(doc, xDatos, yDatos, anchoDatos - anchoDerecha - 4, etiqueta, valor, { tam: TAM.datoDte, maxLineas: 1 });
    if (etiquetaDerecha) {
      const xDerecha = xDatos + anchoDatos - anchoDerecha;
      _texto(doc, etiquetaDerecha, xDerecha, yDatos, { ancho: anchoDerecha, alto: 8, fuente: FUENTE.negrita, tam: TAM.datoDte });
      _texto(doc, valorDerecha, xDerecha, yDatos, { ancho: anchoDerecha, alto: 8, alinear: 'right', tam: TAM.datoDte, vacio: '-' });
    }
    yDatos += 12;
  };
  fila('Modelo de Facturación:', _modeloFacturacion(identificacion.tipoModelo), 'Moneda:', identificacion.tipoMoneda || 'USD');
  fila('Tipo de Transmisión:', _tipoTransmision(identificacion.tipoOperacion), 'Versión:', identificacion.version);
  const fecha = [_formatoFecha(identificacion.fecEmi), identificacion.horEmi].filter(Boolean).join(' ');
  _etiquetaValor(doc, xDatos, yDatos + 2, anchoDatos, 'Fecha y Hora de Generación:', fecha, { tam: TAM.datoDte, maxLineas: 1 });

  // El marco va al final para quedar por encima de la barra y del QR.
  _rect(doc, x, y, ancho, ALTO.cajaDte, { borde: COLOR.tinta, grosor: GROSOR.marco });
  return y + ALTO.cajaDte;
}

function _dibujarEncabezado(ctx) {
  const finEmisor = _dibujarBloqueEmisor(ctx);
  const finCaja = _dibujarCajaDte(ctx);
  ctx.y = Math.max(finEmisor, finCaja) + 10;
}

function _dibujarFranjaSimulacion(ctx) {
  const { doc, opciones } = ctx;
  const texto = opciones.watermark || 'DOCUMENTO SIMULADO - SIN VALIDEZ FISCAL';
  _rect(doc, PAGINA.izquierda, ctx.y, ANCHO_UTIL, ALTO.franjaSimulacion, { borde: COLOR.tinta, grosor: GROSOR.marco });
  _texto(doc, texto, PAGINA.izquierda, _yCentrado(ctx.y, ALTO.franjaSimulacion, TAM.total), {
    ancho: ANCHO_UTIL, alto: 10, alinear: 'center', fuente: FUENTE.negrita, tam: TAM.total, espaciado: 1.2, elipsis: true,
  });
  ctx.y += ALTO.franjaSimulacion + 6;
}

function _filaColumnas(doc, y, pares) {
  const columnas = [
    { x: PAGINA.izquierda + 4, ancho: 204 },
    { x: 240, ancho: 156 },
    { x: 400, ancho: PAGINA.derecha - 404 },
  ];
  let alto = 0;
  pares.forEach(([etiqueta, valor], indice) => {
    const { x, ancho } = columnas[indice];
    alto = Math.max(alto, _etiquetaValor(doc, x, y, ancho, etiqueta, valor));
  });
  return alto;
}

function _dibujarReceptor(ctx) {
  const { doc, receptor } = ctx;
  const xInterior = PAGINA.izquierda + 4;
  const anchoInterior = ANCHO_UTIL - 8;
  const separacion = 5.2;

  _texto(doc, receptor.titulo, PAGINA.izquierda + 4, ctx.y, { ancho: 300, alto: 9, fuente: FUENTE.negrita });
  ctx.y += 11;
  const yCaja = ctx.y;
  let y = yCaja + 5;

  if (receptor.nombreComercial) {
    y += Math.max(
      _etiquetaValor(doc, xInterior, y, 360, 'Nombre o razón social:', receptor.nombre),
      _etiquetaValor(doc, 400, y, PAGINA.derecha - 404, 'Nombre comercial:', receptor.nombreComercial),
    ) + separacion;
  } else {
    y += _etiquetaValor(doc, xInterior, y, anchoInterior, 'Nombre o razón social:', receptor.nombre) + separacion;
  }
  y += _etiquetaValor(doc, xInterior, y, anchoInterior, 'Actividad económica:', receptor.actividad) + separacion;
  y += _etiquetaValor(doc, xInterior, y, anchoInterior, 'Dirección:', receptor.direccion) + separacion;
  y += _filaColumnas(doc, y, [
    ['NRC:', receptor.nrc], ['Tipo Documento:', receptor.tipoDocumento], ['No. Documento:', receptor.numDocumento],
  ]) + separacion;
  y += _filaColumnas(doc, y, [
    ['Correo electrónico:', receptor.correo], ['Número de Teléfono:', receptor.telefono],
    receptor.bienTitulo ? ['Título de los bienes:', receptor.bienTitulo] : ['Condición de la Operación:', receptor.condicion],
  ]);
  y += 5;

  _rect(doc, PAGINA.izquierda, yCaja, ANCHO_UTIL, y - yCaja, { borde: COLOR.tinta, grosor: GROSOR.marco });
  ctx.y = y + SEPARACION;
}

function _dibujarTituloSeccion(ctx, titulo) {
  const { doc } = ctx;
  _asegurarEspacio(ctx, ALTO.tituloSeccion + ALTO.cabeceraTabla + ALTO.filaTabla);
  _rect(doc, PAGINA.izquierda, ctx.y, ANCHO_UTIL, ALTO.tituloSeccion, { borde: COLOR.tinta, grosor: GROSOR.marco });
  _texto(doc, titulo, PAGINA.izquierda, _yCentrado(ctx.y, ALTO.tituloSeccion, TAM.seccion), {
    ancho: ANCHO_UTIL, alto: 13, alinear: 'center', fuente: FUENTE.negrita, tam: TAM.seccion,
  });
  ctx.y += ALTO.tituloSeccion;
}

function _cabeceraTabla(doc, columnas, y, alto, tam = TAM.cabecera) {
  _rect(doc, PAGINA.izquierda, y, ANCHO_UTIL, alto, { relleno: COLOR.tinta });
  let x = PAGINA.izquierda;
  columnas.forEach((columna, indice) => {
    _barra(doc, x, y, columna.ancho, alto, columna.titulo, { tam });
    if (indice > 0) _linea(doc, x, y, x, y + alto, { color: COLOR.inverso, grosor: GROSOR.separador });
    x += columna.ancho;
  });
}

/** Tabla de referencia (documentos relacionados/asociados) con fila "-" si está vacía. */
function _dibujarTablaSimple(ctx, columnas, filas) {
  const { doc } = ctx;
  const dibujarCabecera = () => {
    _cabeceraTabla(doc, columnas, ctx.y, ALTO.cabeceraTabla);
    ctx.y += ALTO.cabeceraTabla;
  };
  dibujarCabecera();
  const lista = filas.length > 0 ? filas : [columnas.map(() => '-')];
  for (const fila of lista) {
    const alto = Math.max(ALTO.filaTabla, ...fila.map((valor, indice) => _alto(doc, valor, columnas[indice].ancho - 8) + 6));
    if (ctx.y + alto > PAGINA.limite) {
      _nuevaPagina(ctx);
      dibujarCabecera();
    }
    _rect(doc, PAGINA.izquierda, ctx.y, ANCHO_UTIL, alto, { borde: COLOR.tinta, grosor: GROSOR.marco });
    let x = PAGINA.izquierda;
    fila.forEach((valor, indice) => {
      _texto(doc, valor, x + 4, ctx.y + 3.5, { ancho: columnas[indice].ancho - 8, alto: alto - 3, alinear: 'center', vacio: '-' });
      x += columnas[indice].ancho;
    });
    ctx.y += alto;
  }
}

function _lista(valor) {
  return (Array.isArray(valor) ? valor : valor ? [valor] : []).filter((registro) => registro && typeof registro === 'object');
}

function _dibujarReferencias(ctx) {
  const { doc, dte } = ctx;
  const tercero = dte.ventaTercero || {};
  const y = ctx.y;
  const anchoCelda = 132;
  const yTexto = _yCentrado(y, ALTO.terceros, TAM.base);

  _rect(doc, PAGINA.izquierda, y, ANCHO_UTIL, ALTO.terceros, { borde: COLOR.tinta, grosor: GROSOR.marco });
  _barra(doc, PAGINA.izquierda, y, anchoCelda, ALTO.terceros, 'Venta a Cuenta de Terceros', { tam: TAM.base });
  _etiquetaValor(doc, 250, yTexto, 160, 'Nit:', _formatoNit(tercero.nit) || '-', { maxLineas: 1 });
  _etiquetaValor(doc, 420, yTexto, PAGINA.derecha - 424, 'Nombre o razón social:', tercero.nombre || '-', { maxLineas: 1 });
  ctx.y += ALTO.terceros;

  _dibujarTituloSeccion(ctx, 'DOCUMENTO RELACIONADO');
  const relacionados = _lista(dte.documentoRelacionado).map((documento) => {
    const generacion = etiquetas.nombreTipoGeneracion(documento.tipoGeneracion);
    return [
      [etiquetas.nombreTipoDte(documento.tipoDocumento), generacion ? `(${generacion})` : null].filter(Boolean).join(' ') || null,
      documento.numeroDocumento,
      _formatoFecha(documento.fechaEmision),
    ];
  });
  _dibujarTablaSimple(ctx, [
    { titulo: 'TIPO DE DOCUMENTO', ancho: 185 },
    { titulo: 'NÚMERO DE DOCUMENTO', ancho: 185 },
    { titulo: 'FECHA DE EMISIÓN', ancho: ANCHO_UTIL - 370 },
  ], relacionados);

  _dibujarTituloSeccion(ctx, 'OTROS DOCUMENTOS ASOCIADOS');
  const asociados = _lista(dte.otrosDocumentos)
    .filter((documento) => documento.codDocAsociado || documento.descDocumento || documento.detalleDocumento)
    .map((documento) => [
      [etiquetas.nombreDocumentoAsociado(documento.codDocAsociado), documento.descDocumento].filter(Boolean).join(': ') || null,
      documento.detalleDocumento,
    ]);
  _dibujarTablaSimple(ctx, [
    { titulo: 'IDENTIFICACIÓN DEL DOCUMENTO ASOCIADO', ancho: 206 },
    { titulo: 'DESCRIPCIÓN DEL DOCUMENTO ASOCIADO', ancho: ANCHO_UTIL - 206 },
  ], asociados);
  ctx.y += SEPARACION;
}

/** Alto del valor de una celda: envuelve si la columna lo permite; si no, una línea ajustada. */
function _altoValorCelda(doc, columna, item) {
  return columna.envolver
    ? _alto(doc, columna.valor(item), columna.ancho - 6, { tam: TAM.base })
    : _altoLinea(doc, TAM.base);
}

function _altoFilaItem(doc, columnas, item) {
  let alto = ALTO.filaItemMinima;
  for (const columna of columnas) {
    if (!columna.envolver && !columna.detalle) continue;
    let altoCelda = _altoValorCelda(doc, columna, item);
    const detalle = columna.detalle?.(item);
    if (detalle) altoCelda += _alto(doc, detalle, columna.ancho - 6, { tam: TAM.detalle });
    alto = Math.max(alto, altoCelda + 6);
  }
  return alto;
}

function _dibujarFilaItem(doc, columnas, item, y) {
  let x = PAGINA.izquierda;
  for (const columna of columnas) {
    const xCelda = x + 3;
    const anchoCelda = columna.ancho - 6;
    const valor = columna.valor(item);
    const altoValor = _altoValorCelda(doc, columna, item);
    if (columna.envolver) {
      _texto(doc, valor, xCelda, y + 3.5, { ancho: anchoCelda, alto: altoValor + 0.5, alinear: columna.alinear, vacio: '-' });
    } else {
      _textoAjustado(doc, valor, xCelda, y + 3.5, anchoCelda, { tam: TAM.base, tamMin: 5, alinear: columna.alinear, vacio: '-' });
    }
    const detalle = columna.detalle?.(item);
    if (detalle) {
      const altoDetalle = _alto(doc, detalle, anchoCelda, { tam: TAM.detalle });
      _texto(doc, detalle, xCelda, y + 3.5 + altoValor, {
        ancho: anchoCelda, alto: altoDetalle + 0.5, alinear: columna.alinear, tam: TAM.detalle, color: COLOR.secundario,
      });
    }
    x += columna.ancho;
  }
}

function _cerrarMarcoItems(doc, yInicio, yFin) {
  _linea(doc, PAGINA.izquierda, yInicio, PAGINA.izquierda, yFin, { grosor: GROSOR.marco });
  _linea(doc, PAGINA.derecha, yInicio, PAGINA.derecha, yFin, { grosor: GROSOR.marco });
  _linea(doc, PAGINA.izquierda, yFin, PAGINA.derecha, yFin, { grosor: GROSOR.marco });
}

/** Posición de "Sumas:" y ancho disponible para el total en letras. */
function _geometriaSumas(columnas) {
  let x = PAGINA.izquierda;
  let xPrimeraSuma = null;
  for (const columna of columnas) {
    if (columna.total && xPrimeraSuma === null) xPrimeraSuma = x;
    x += columna.ancho;
  }
  if (xPrimeraSuma === null) return { xSumas: null, anchoLetras: ANCHO_UTIL - 8 };
  return { xSumas: xPrimeraSuma, anchoLetras: xPrimeraSuma - 70 - (PAGINA.izquierda + 4) };
}

function _altoFilaSumas(ctx, columnas) {
  const { anchoLetras } = _geometriaSumas(columnas);
  return Math.max(15, _etiquetaValor(ctx.doc, 0, 0, anchoLetras, 'Total en Letras:', ctx.totalLetras, { medir: true }) + 7);
}

function _valorSuma(dte, columna) {
  const resumen = dte.resumen || {};
  if (resumen[columna.total] !== undefined) return resumen[columna.total];
  const items = Array.isArray(dte.cuerpoDocumento) ? dte.cuerpoDocumento : [];
  if (!items.some((item) => typeof item[columna.campo] === 'number')) return null;
  return items.reduce((suma, item) => suma + (Number(item[columna.campo]) || 0), 0);
}

function _dibujarFilaSumas(ctx, columnas, alto) {
  const { doc, dte } = ctx;
  const y = ctx.y;
  const { xSumas, anchoLetras } = _geometriaSumas(columnas);
  _rect(doc, PAGINA.izquierda, y, ANCHO_UTIL, alto, { borde: COLOR.tinta, grosor: GROSOR.marco });
  _etiquetaValor(doc, PAGINA.izquierda + 4, y + 4, anchoLetras, 'Total en Letras:', ctx.totalLetras || '-');
  if (xSumas === null) return;
  _texto(doc, 'Sumas:', xSumas - 64, y + 4, { ancho: 60, alto: 9, alinear: 'right', fuente: FUENTE.negrita });
  let x = PAGINA.izquierda;
  for (const columna of columnas) {
    if (columna.total) {
      _textoAjustado(doc, _formatoMoneda(_valorSuma(dte, columna)), x + 3, y + 4, columna.ancho - 6, {
        tam: TAM.base, tamMin: 5, alinear: 'right',
      });
    }
    x += columna.ancho;
  }
}

function _altoFilaTotal(doc, fila) {
  const { fuente, tam } = _estiloTotal(fila);
  return Math.max(12, _alto(doc, fila.etiqueta, ANCHO_ETIQUETA_TOTAL - 8, { fuente, tam }) + 4);
}

function _estiloTotal(fila) {
  if (fila.destacada) return { fuente: FUENTE.negrita, tam: TAM.total, color: COLOR.tinta };
  if (fila.informativa) return { fuente: FUENTE.cursiva, tam: TAM.base, color: COLOR.secundario };
  return { fuente: FUENTE.normal, tam: TAM.base, color: COLOR.tinta };
}

function _dibujarFilaTotal(doc, fila, y, alto) {
  const xValor = X_TOTALES + ANCHO_ETIQUETA_TOTAL;
  const anchoValor = PAGINA.derecha - xValor;
  const { fuente, tam, color } = _estiloTotal(fila);
  if (fila.destacada) _rect(doc, X_TOTALES, y, PAGINA.derecha - X_TOTALES, alto, { relleno: COLOR.realce });
  _rect(doc, X_TOTALES, y, ANCHO_ETIQUETA_TOTAL, alto, { borde: COLOR.tinta });
  _rect(doc, xValor, y, anchoValor, alto, { borde: COLOR.tinta });

  const altoEtiqueta = _alto(doc, fila.etiqueta, ANCHO_ETIQUETA_TOTAL - 8, { fuente, tam });
  const visible = altoEtiqueta - _altoLinea(doc, tam, fuente) + 0.718 * tam;
  _texto(doc, fila.etiqueta, X_TOTALES + 4, y + (alto - visible) / 2, {
    ancho: ANCHO_ETIQUETA_TOTAL - 8, alto: altoEtiqueta + 0.5, alinear: 'right', fuente, tam, color,
  });
  _textoAjustado(doc, _formatoMoneda(fila.valor), xValor + 3, _yCentrado(y, alto, tam), anchoValor - 6, {
    tam, tamMin: 5, alinear: 'right', color, fuente: fila.destacada || fila.negrita ? FUENTE.negrita : fuente,
  });
}

function _altoObservaciones(ctx) {
  const anchoTexto = X_TOTALES - PAGINA.izquierda - 10;
  return ctx.observaciones.reduce((suma, linea) => suma + _altoLineaObservacion(ctx.doc, linea, anchoTexto, true) + 2, 0);
}

function _altoLineaObservacion(doc, linea, ancho, medir, x = 0, y = 0) {
  if (linea.etiqueta) return _etiquetaValor(doc, x, y, ancho, linea.etiqueta, linea.valor, { medir });
  const alto = _alto(doc, linea.valor, ancho);
  if (!medir) _texto(doc, linea.valor, x, y, { ancho, alto: alto + 0.5 });
  return alto;
}

function _medirBloqueFinal(ctx) {
  const altoTotales = ctx.totales.reduce((suma, fila) => suma + _altoFilaTotal(ctx.doc, fila), 0);
  const altoObservaciones = ALTO.barraObservaciones + Math.max(_altoObservaciones(ctx) + 10, 24);
  const altoMedio = Math.max(altoTotales, altoObservaciones);
  return { altoMedio, total: altoMedio + 6 + ALTO.firmas };
}

function _dibujarFirmas(ctx) {
  const { doc, firmas, opciones } = ctx;
  const y = ctx.y;
  const alto = ALTO.firmas;
  _rect(doc, PAGINA.izquierda, y, ANCHO_UTIL, alto, { borde: COLOR.tinta, grosor: GROSOR.marco });
  _linea(doc, X_ENTREGA, y, X_ENTREGA, y + alto, { grosor: GROSOR.marco });
  _linea(doc, X_RECIBE, y, X_RECIBE, y + alto, { grosor: GROSOR.marco });

  const xIzquierda = PAGINA.izquierda + 8;
  const anchoIzquierda = X_ENTREGA - xIzquierda - 8;
  const yFecha = opciones.urlConsulta ? y + 12 : _yCentrado(y, alto, TAM.base);
  _etiquetaValor(doc, xIzquierda, yFecha, anchoIzquierda, 'Fecha de representación gráfica:', ctx.fechaRepresentacion, { maxLineas: 1 });
  if (opciones.urlConsulta) {
    _texto(doc, 'Consulta pública en el Ministerio de Hacienda:', xIzquierda, y + 27, {
      ancho: anchoIzquierda, alto: 8, fuente: FUENTE.negrita, tam: 5.5, color: COLOR.secundario,
    });
    _texto(doc, opciones.urlConsulta, xIzquierda, y + 35, {
      ancho: anchoIzquierda, alto: 2 * _altoLinea(doc, TAM.url) + 0.5, tam: TAM.url, enlace: opciones.urlConsulta, elipsis: true,
    });
  }

  const columnas = [
    { x: X_ENTREGA, ancho: X_RECIBE - X_ENTREGA, titulo: 'ENTREGA', datos: firmas.entrega },
    { x: X_RECIBE, ancho: PAGINA.derecha - X_RECIBE, titulo: 'RECIBE', datos: firmas.recibe },
  ];
  for (const { x, ancho, titulo, datos } of columnas) {
    _barra(doc, x, y, ancho, 15, titulo, { tam: TAM.barra, fuente: FUENTE.normal });
    _etiquetaValor(doc, x + 5, y + 19, ancho - 10, 'Nombre:', datos.nombre, { maxLineas: 2 });
    _etiquetaValor(doc, x + 5, y + 37, ancho - 10, 'DUI o NIT:', datos.documento, { maxLineas: 2 });
  }
  ctx.y = y + alto;
}

function _dibujarBloqueFinal(ctx, altoMedio) {
  const { doc } = ctx;
  const y = ctx.y;
  const anchoObservaciones = X_TOTALES - PAGINA.izquierda;

  _barra(doc, PAGINA.izquierda, y, anchoObservaciones, ALTO.barraObservaciones, 'OBSERVACIONES', { tam: TAM.barra, fuente: FUENTE.normal });
  _rect(doc, PAGINA.izquierda, y + ALTO.barraObservaciones, anchoObservaciones, altoMedio - ALTO.barraObservaciones, {
    borde: COLOR.tinta, grosor: GROSOR.marco,
  });
  let yObservacion = y + ALTO.barraObservaciones + 5;
  for (const linea of ctx.observaciones) {
    yObservacion += _altoLineaObservacion(doc, linea, anchoObservaciones - 10, false, PAGINA.izquierda + 5, yObservacion) + 2;
  }

  let yTotal = y;
  for (const fila of ctx.totales) {
    const alto = _altoFilaTotal(doc, fila);
    _dibujarFilaTotal(doc, fila, yTotal, alto);
    yTotal += alto;
  }

  ctx.y = y + altoMedio + 6;
  _dibujarFirmas(ctx);
}

/**
 * Tabla de ítems con paginación: la cabecera se repite en cada página y el
 * marco llega hasta el pie cuando la tabla continúa. La última fila viaja
 * junto a la fila "Sumas" y, si cabe en una página nueva, también junto al
 * bloque final (observaciones, totales y firmas), que nunca se parte; así no
 * queda una página con totales y sin ítems. Si el bloque final cabe en la
 * página, el área de ítems se estira para dejar las firmas ancladas al pie.
 */
function _dibujarTablaItems(ctx) {
  const { doc, dte } = ctx;
  const columnas = _columnasPara(ctx.tipoDte);
  const items = dte.cuerpoDocumento;
  const altoSumas = _altoFilaSumas(ctx, columnas);
  const final = _medirBloqueFinal(ctx);
  // Espacio útil de una página de continuación, debajo de su encabezado y de la cabecera de ítems.
  const capacidadPaginaNueva = PAGINA.limite - (PAGINA.superior + 30) - ALTO.cabeceraItems;

  _asegurarEspacio(ctx, ALTO.cabeceraItems + ALTO.areaItemsMinima + altoSumas);
  _cabeceraTabla(doc, columnas, ctx.y, ALTO.cabeceraItems);
  ctx.y += ALTO.cabeceraItems;
  let yArea = ctx.y;

  items.forEach((item, indice) => {
    const alto = _altoFilaItem(doc, columnas, item);
    let necesario = alto;
    if (indice === items.length - 1) {
      necesario += altoSumas;
      if (necesario + final.total <= capacidadPaginaNueva) necesario += final.total;
    }
    if (ctx.y + necesario > PAGINA.limite) {
      _cerrarMarcoItems(doc, yArea, PAGINA.limite);
      _nuevaPagina(ctx);
      _cabeceraTabla(doc, columnas, ctx.y, ALTO.cabeceraItems);
      ctx.y += ALTO.cabeceraItems;
      yArea = ctx.y;
    }
    _dibujarFilaItem(doc, columnas, item, ctx.y);
    ctx.y += alto;
  });

  const minimo = Math.max(0, yArea + ALTO.areaItemsMinima - ctx.y);
  const libre = PAGINA.limite - ctx.y - altoSumas - final.total;
  if (libre >= minimo) ctx.y += libre;
  else ctx.y = Math.max(ctx.y + minimo, PAGINA.limite - altoSumas);
  _cerrarMarcoItems(doc, yArea, ctx.y);

  _dibujarFilaSumas(ctx, columnas, altoSumas);
  ctx.y += altoSumas;
  if (ctx.y + final.total > PAGINA.limite + 0.01) _nuevaPagina(ctx);
  _dibujarBloqueFinal(ctx, final.altoMedio);
}

/** DCL: el cuerpo es un objeto; se presenta como cuadrícula etiqueta/valor. */
function _dibujarDetalleObjeto(ctx) {
  const { doc } = ctx;
  const cuerpo = ctx.dte.cuerpoDocumento || {};
  const excluidos = new Set(['totalLetras', 'observaciones', 'liquidoApagar', ...TOTALES_DCL.map(([campo]) => campo)]);
  const pares = Object.entries(cuerpo)
    .filter(([campo]) => !excluidos.has(campo))
    .map(([campo, valor]) => [_etiquetaCampo(campo), _valorCampoDcl(campo, valor)]);
  const anchoEtiqueta = 120;
  const anchoValor = ANCHO_UTIL / 2 - anchoEtiqueta;

  _asegurarEspacio(ctx, ALTO.cabeceraTabla + ALTO.filaTabla);
  _barra(doc, PAGINA.izquierda, ctx.y, ANCHO_UTIL, ALTO.cabeceraTabla, 'DETALLE DE LA LIQUIDACIÓN');
  ctx.y += ALTO.cabeceraTabla;
  for (let indice = 0; indice < pares.length; indice += 2) {
    const fila = pares.slice(indice, indice + 2);
    const alto = Math.max(ALTO.filaTabla, ...fila.flatMap(([etiqueta, valor]) => [
      _alto(doc, etiqueta, anchoEtiqueta - 8, { fuente: FUENTE.negrita }) + 6,
      _alto(doc, valor, anchoValor - 8) + 6,
    ]));
    _asegurarEspacio(ctx, alto);
    fila.forEach(([etiqueta, valor], columna) => {
      const x = PAGINA.izquierda + columna * (ANCHO_UTIL / 2);
      _rect(doc, x, ctx.y, anchoEtiqueta, alto, { borde: COLOR.tinta });
      _rect(doc, x + anchoEtiqueta, ctx.y, anchoValor, alto, { borde: COLOR.tinta });
      _texto(doc, etiqueta, x + 4, ctx.y + 3.5, { ancho: anchoEtiqueta - 8, alto: alto - 3, fuente: FUENTE.negrita });
      _texto(doc, valor, x + anchoEtiqueta + 4, ctx.y + 3.5, { ancho: anchoValor - 8, alto: alto - 3, vacio: '-' });
    });
    ctx.y += alto;
  }

  const altoSumas = _altoFilaSumas(ctx, []);
  const final = _medirBloqueFinal(ctx);
  _asegurarEspacio(ctx, altoSumas);
  _dibujarFilaSumas(ctx, [], altoSumas);
  ctx.y += altoSumas;
  if (ctx.y + final.total > PAGINA.limite + 0.01) _nuevaPagina(ctx);
  _dibujarBloqueFinal(ctx, final.altoMedio);
}

function _dibujarPiesYMarcas(doc, { simulation }) {
  const rango = doc.bufferedPageRange();
  for (let indice = rango.start; indice < rango.start + rango.count; indice += 1) {
    doc.switchToPage(indice);
    if (simulation) {
      doc.save();
      doc.rotate(-35, { origin: [PAGINA.ancho / 2, PAGINA.alto / 2] });
      doc.font(FUENTE.negrita).fontSize(TAM.marcaAgua).fillColor(COLOR.tinta, 0.07);
      doc.text('SIMULADO - SIN VALIDEZ FISCAL', -50, PAGINA.alto / 2 - TAM.marcaAgua / 2, {
        width: PAGINA.ancho + 100, height: TAM.marcaAgua * 1.5, align: 'center', lineBreak: false,
      });
      doc.restore();
      _texto(doc, 'Documento generado exclusivamente para pruebas. No fue firmado ni recibido por Hacienda.', PAGINA.izquierda, PAGINA.pie, {
        ancho: 420, alto: 9, fuente: FUENTE.negrita, tam: TAM.pie,
      });
    }
    _texto(doc, `Página ${indice + 1} de ${rango.count}`, PAGINA.izquierda, PAGINA.pie, {
      ancho: ANCHO_UTIL, alto: 9, alinear: 'right', tam: TAM.pie, color: COLOR.secundario,
    });
  }
}

/**
 * Genera la representación gráfica (PDF) de un DTE ya transmitido.
 * Devuelve una Promise<Buffer> con el PDF completo.
 *
 * `dte` = el JSON completo del DTE (el mismo que se firmó/transmitió).
 * `opciones.selloRecepcion` = el sello devuelto por Hacienda al recibirlo.
 * `opciones.ambiente` = "00" o "01" (para construir la URL del QR).
 * `opciones.fechaRepresentacion` = "YYYY-MM-DD" o Date para la leyenda
 *   "Fecha de representación gráfica"; por defecto, hoy en El Salvador.
 */
async function generarPDF(dte, { selloRecepcion, ambiente, simulation = false, watermark, logoPngBuffer = null, fechaRepresentacion } = {}) {
  if (typeof selloRecepcion !== 'string' || !selloRecepcion.trim()) {
    throw new Error('No se puede generar el PDF final sin sello de recepción')
  }

  const ambienteHistorico = dte.identificacion.ambiente;
  if (ambiente !== undefined && ambiente !== ambienteHistorico) {
    throw new Error('El ambiente del PDF no coincide con el ambiente histórico del DTE');
  }
  const urlConsulta = simulation ? null : construirUrlConsultaPublica({
    ambiente: ambienteHistorico,
    codigoGeneracion: dte.identificacion.codigoGeneracion,
    fechaEmi: dte.identificacion.fecEmi,
  });

  const qrPngBuffer = simulation ? null : await QRCode.toBuffer(urlConsulta, { width: 150, margin: 1 });

  return new Promise((resolve, reject) => {
    const tipoDte = dte.identificacion.tipoDte;
    const nombreTipo = etiquetas.nombreTipoDte(tipoDte) || `Tipo ${tipoDte}`;
    const doc = new PDFDocument({
      size: 'LETTER',
      margins: { top: PAGINA.superior, left: PAGINA.izquierda, right: PAGINA.ancho - PAGINA.derecha, bottom: 8 },
      bufferPages: true,
      info: { Title: _textoPdf(`${nombreTipo} ${dte.identificacion.numeroControl || ''}`) },
    });
    const chunks = [];
    doc.on('data', (chunk) => chunks.push(chunk));
    doc.on('end', () => resolve(Buffer.concat(chunks)));
    doc.on('error', reject);

    const emisor = _datosEmisor(dte);
    const receptor = _datosReceptor(dte);
    const totales = _filasTotales(dte);
    const ctx = {
      doc,
      dte,
      tipoDte,
      nombreTipo,
      y: PAGINA.superior,
      emisor,
      receptor,
      firmas: _datosFirmas(dte, emisor, receptor),
      totales,
      totalLetras: _totalEnLetras(dte, totales),
      observaciones: _lineasObservaciones(dte),
      fechaRepresentacion: _fechaRepresentacion(fechaRepresentacion),
      opciones: {
        simulation,
        watermark,
        selloRecepcion: selloRecepcion.trim(),
        urlConsulta,
        qrPngBuffer,
        logoPngBuffer,
      },
    };

    _dibujarEncabezado(ctx);
    if (simulation) _dibujarFranjaSimulacion(ctx);
    _dibujarReceptor(ctx);
    _dibujarReferencias(ctx);
    if (Array.isArray(dte.cuerpoDocumento)) _dibujarTablaItems(ctx);
    else _dibujarDetalleObjeto(ctx);
    _dibujarPiesYMarcas(doc, { simulation });

    doc.end();
  });
}

// Primitivas y estilo compartidos con otras representaciones gráficas (eventos).
const estilo = Object.freeze({
  PAGINA, ANCHO_UTIL, COLOR, FUENTE, TAM, GROSOR, ALTO, SEPARACION, X_CAJA_DTE, ANCHO_EMISOR,
  textoPdf: _textoPdf,
  formatoFecha: _formatoFecha,
  formatoNit: _formatoNit,
  formatoTelefono: _formatoTelefono,
  formatoDocumento: _formatoDocumento,
  yCentrado: _yCentrado,
  texto: _texto,
  textoAjustado: _textoAjustado,
  textoCentrado: _textoCentrado,
  alto: _alto,
  etiquetaValor: _etiquetaValor,
  rect: _rect,
  linea: _linea,
  barra: _barra,
  dibujarFranjaSimulacion: _dibujarFranjaSimulacion,
  dibujarTituloSeccion: _dibujarTituloSeccion,
  cabeceraTabla: _cabeceraTabla,
  dibujarTablaSimple: _dibujarTablaSimple,
  dibujarPiesYMarcas: _dibujarPiesYMarcas,
});

module.exports = { generarPDF, estilo };
