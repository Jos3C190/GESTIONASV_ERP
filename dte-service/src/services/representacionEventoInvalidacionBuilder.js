const PDFDocument = require('pdfkit');
const etiquetas = require('../utils/etiquetasCatalogo');
const { estilo } = require('./representacionGraficaBuilder');

/**
 * Representación gráfica (PDF) del Evento de Invalidación V3, según el modelo
 * sugerido del Manual Funcional (sección XXII, punto 12): identificación del
 * evento, emisor y receptor, motivo, documento invalidado y documento que lo
 * reemplaza. Usa la paleta, tipografía y primitivas del PDF de los DTE.
 *
 * Es solo una representación del JSON ya sellado: no cambia nada de lo que
 * se envía a Hacienda.
 */
const {
  PAGINA, ANCHO_UTIL, COLOR, FUENTE, TAM, GROSOR, ALTO, SEPARACION, X_CAJA_DTE, ANCHO_EMISOR,
} = estilo;

const ALTO_FILA_IDENTIFICACION = 18.5;
const ANCHO_CAJA = (ANCHO_UTIL - SEPARACION) / 2;

function _documentoIdentificacion(tipo, numero) {
  return {
    tipo: tipo ? etiquetas.nombreTipoDocumentoIdentificacion(tipo) : null,
    numero: estilo.formatoDocumento(numero, tipo),
  };
}

function _fechaHora(fecha, hora) {
  return [estilo.formatoFecha(fecha), hora].filter(Boolean).join(' ') || null;
}

function _datosEvento(evento) {
  const { identificacion, emisor = {}, documento = {}, motivo = {} } = evento;
  const receptor = _documentoIdentificacion(documento.tipoDocumento, documento.numDocumento);
  const responsable = _documentoIdentificacion(motivo.tipDocResponsable, motivo.numDocResponsable);
  const solicitante = _documentoIdentificacion(motivo.tipDocSolicita, motivo.numDocSolicita);
  return {
    codigoGeneracion: identificacion.codigoGeneracion,
    fechaHora: _fechaHora(identificacion.fecEmi, identificacion.horEmi),
    version: identificacion.version,
    sello: evento.selloRecibido,
    emisor: {
      nombre: emisor.nombre || null,
      nit: estilo.formatoNit(emisor.nit),
      telefono: estilo.formatoTelefono(emisor.telefono),
      correo: emisor.correo || null,
    },
    receptor: {
      nombre: documento.nombre || null,
      tipoDocumento: receptor.tipo,
      numDocumento: receptor.numero,
      telefono: estilo.formatoTelefono(documento.telefono),
      correo: documento.correo || null,
    },
    motivo: {
      tipo: motivo.tipoAnulacion ? `${motivo.tipoAnulacion}. ${etiquetas.nombreTipoInvalidacion(motivo.tipoAnulacion)}` : null,
      descripcion: motivo.motivoAnulacion || null,
      responsable: { nombre: motivo.nombreResponsable || null, ...responsable },
      solicitante: { nombre: motivo.nombreSolicita || null, ...solicitante },
    },
    documento: {
      tipo: documento.tipoDte ? etiquetas.nombreTipoDte(documento.tipoDte) : null,
      codigoGeneracion: documento.codigoGeneracion || null,
      sello: documento.selloRecibido || null,
      numeroControl: documento.numeroControl || null,
      fecha: estilo.formatoFecha(documento.fecEmi),
      reemplazo: documento.codigoGeneracionR || null,
    },
  };
}

function _dibujarMembrete(ctx) {
  const { doc, datos, opciones } = ctx;
  const x = PAGINA.izquierda;
  let y = PAGINA.superior;
  if (opciones.logoPngBuffer) {
    doc.image(opciones.logoPngBuffer, x + (ANCHO_EMISOR - 160) / 2, y, { fit: [160, 50], align: 'center', valign: 'center' });
    y += 56;
    y += estilo.textoCentrado(doc, datos.emisor.nombre, x, y, ANCHO_EMISOR, { fuente: FUENTE.negrita, tam: TAM.nombreEmisor }) + 1;
  } else {
    y += 4;
    y += estilo.textoCentrado(doc, datos.emisor.nombre ? datos.emisor.nombre.toUpperCase() : null, x, y, ANCHO_EMISOR, {
      fuente: FUENTE.negrita, tam: TAM.marca, espaciado: 1.5,
    }) + 5;
  }
  return y;
}

function _dibujarCajaEvento(ctx) {
  const { doc, datos, opciones } = ctx;
  const x = X_CAJA_DTE;
  const y = PAGINA.superior;
  const ancho = PAGINA.derecha - x;
  estilo.barra(doc, x, y, ancho, ALTO.barraDte, ['EVENTO DE INVALIDACIÓN', `Versión ${datos.version ?? 3}`], { tam: TAM.tituloDte });

  let yDatos = y + ALTO.barraDte + 5;
  const par = (etiqueta, valor) => {
    estilo.texto(doc, etiqueta, x + 4, yDatos, { ancho: ancho - 8, alto: 9, alinear: 'center', fuente: FUENTE.negrita, tam: TAM.cabecera });
    estilo.textoAjustado(doc, valor, x + 4, yDatos + 8.5, ancho - 8, { tam: TAM.datoDte, tamMin: 4.8, alinear: 'center', vacio: '-' });
    yDatos += ALTO_FILA_IDENTIFICACION;
  };
  par('Código de Generación', datos.codigoGeneracion);
  par('Fecha y Hora del Evento', datos.fechaHora);
  par(opciones.simulation ? 'Identificador simulado' : 'Sello de Recepción', datos.sello);
  const alto = yDatos + 2 - y;
  estilo.rect(doc, x, y, ancho, alto, { borde: COLOR.tinta, grosor: GROSOR.marco });
  return y + alto;
}

/** Filas "Etiqueta: valor" en una caja con título; devuelve el alto que ocupa (sin dibujar con `medir`). */
function _cajaDatos(doc, x, y, ancho, titulo, filas, { medir = false } = {}) {
  if (!medir) estilo.texto(doc, titulo, x + 4, y, { ancho: ancho - 8, alto: 9, fuente: FUENTE.negrita });
  let yFila = y + 16;
  for (const [etiqueta, valor] of filas) {
    yFila += estilo.etiquetaValor(doc, x + 4, yFila, ancho - 8, etiqueta, valor ?? '-', { medir }) + 5.2;
  }
  return yFila - 5.2 + 5 - y;
}

function _dibujarPartes(ctx, izquierda, derecha) {
  const { doc } = ctx;
  const xDerecha = PAGINA.izquierda + ANCHO_CAJA + SEPARACION;
  const alto = Math.max(
    _cajaDatos(doc, PAGINA.izquierda, ctx.y, ANCHO_CAJA, izquierda.titulo, izquierda.filas, { medir: true }),
    _cajaDatos(doc, xDerecha, ctx.y, ANCHO_CAJA, derecha.titulo, derecha.filas, { medir: true }),
  );
  _cajaDatos(doc, PAGINA.izquierda, ctx.y, ANCHO_CAJA, izquierda.titulo, izquierda.filas);
  _cajaDatos(doc, xDerecha, ctx.y, ANCHO_CAJA, derecha.titulo, derecha.filas);
  for (const x of [PAGINA.izquierda, xDerecha]) {
    estilo.rect(doc, x, ctx.y + 11, ANCHO_CAJA, alto - 11, { borde: COLOR.tinta, grosor: GROSOR.marco });
  }
  ctx.y += alto + SEPARACION;
}

function _dibujarMotivo(ctx) {
  const { doc, datos } = ctx;
  const { motivo } = datos;
  const xInterior = PAGINA.izquierda + 4;
  const anchoInterior = ANCHO_UTIL - 8;
  const anchoColumna = (anchoInterior - SEPARACION) / 2;
  const xDerecha = xInterior + anchoColumna + SEPARACION;

  estilo.texto(doc, 'Información relativa al motivo de invalidación', xInterior, ctx.y, { ancho: 300, alto: 9, fuente: FUENTE.negrita });
  ctx.y += 11;
  const yCaja = ctx.y;
  let y = yCaja + 5;
  y += estilo.etiquetaValor(doc, xInterior, y, anchoInterior, 'Tipo de invalidación:', motivo.tipo ?? '-') + 5.2;
  y += estilo.etiquetaValor(doc, xInterior, y, anchoInterior, 'Motivo:', motivo.descripcion ?? '-') + 5.2;

  const persona = (x, yPersona, etiquetaNombre, datosPersona) => {
    let yActual = yPersona;
    yActual += estilo.etiquetaValor(doc, x, yActual, anchoColumna, etiquetaNombre, datosPersona.nombre ?? '-') + 3;
    yActual += estilo.etiquetaValor(doc, x, yActual, anchoColumna, 'Tipo de doc. de identificación:', datosPersona.tipo ?? '-') + 3;
    yActual += estilo.etiquetaValor(doc, x, yActual, anchoColumna, 'N.º de doc. de identificación:', datosPersona.numero ?? '-');
    return yActual;
  };
  y = Math.max(
    persona(xInterior, y, 'Nombre de quien realiza el evento:', motivo.responsable),
    persona(xDerecha, y, 'Nombre de quien solicita el evento:', motivo.solicitante),
  ) + 5;
  estilo.rect(doc, PAGINA.izquierda, yCaja, ANCHO_UTIL, y - yCaja, { borde: COLOR.tinta, grosor: GROSOR.marco });
  ctx.y = y + SEPARACION;
}

/**
 * Tabla de una fila con el documento invalidado. Los identificadores (código,
 * sello y número de control) reducen la letra para caber en una línea; el
 * tipo de DTE puede envolver.
 */
function _dibujarDocumento(ctx) {
  const { doc, datos, opciones } = ctx;
  const { documento } = datos;
  const columnas = [
    { titulo: 'TIPO DE DTE', ancho: 92, valor: documento.tipo, envolver: true },
    { titulo: 'CÓDIGO DE GENERACIÓN', ancho: 128, valor: documento.codigoGeneracion },
    { titulo: opciones.simulation ? 'IDENTIFICADOR SIMULADO' : 'SELLO DE RECEPCIÓN', ancho: 146, valor: documento.sello },
    { titulo: 'NÚMERO DE CONTROL', ancho: 106, valor: documento.numeroControl },
    { titulo: 'FECHA DE GENERACIÓN', ancho: ANCHO_UTIL - 472, valor: documento.fecha },
  ];
  estilo.dibujarTituloSeccion(ctx, 'IDENTIFICACIÓN DEL DOCUMENTO INVALIDADO');
  estilo.cabeceraTabla(doc, columnas, ctx.y, ALTO.cabeceraTabla);
  ctx.y += ALTO.cabeceraTabla;

  const alto = Math.max(ALTO.filaTabla + 4, ...columnas
    .filter((columna) => columna.envolver)
    .map((columna) => estilo.alto(doc, columna.valor, columna.ancho - 8) + 8));
  estilo.rect(doc, PAGINA.izquierda, ctx.y, ANCHO_UTIL, alto, { borde: COLOR.tinta, grosor: GROSOR.marco });
  let x = PAGINA.izquierda;
  columnas.forEach((columna, indice) => {
    if (indice > 0) estilo.linea(doc, x, ctx.y, x, ctx.y + alto, { grosor: GROSOR.rejilla });
    if (columna.envolver) {
      const altoTexto = estilo.alto(doc, columna.valor, columna.ancho - 8);
      estilo.texto(doc, columna.valor, x + 4, ctx.y + (alto - altoTexto) / 2, {
        ancho: columna.ancho - 8, alto: altoTexto + 1, alinear: 'center', vacio: '-',
      });
    } else {
      estilo.textoAjustado(doc, columna.valor, x + 4, estilo.yCentrado(ctx.y, alto, TAM.base), columna.ancho - 8, {
        tamMin: 5, alinear: 'center', vacio: '-',
      });
    }
    x += columna.ancho;
  });
  ctx.y += alto + SEPARACION;
  ctx.y += estilo.etiquetaValor(doc, PAGINA.izquierda + 4, ctx.y, ANCHO_UTIL - 8,
    'Código de generación que reemplaza al invalidado:', documento.reemplazo ?? 'No aplica');
}

/**
 * Genera el PDF de un Evento de Invalidación ya sellado (o simulado).
 * `evento` = el archivo del evento: el JSON transmitido más `selloRecibido`.
 * Devuelve una Promise<Buffer>.
 */
function generarPDFEventoInvalidacion(evento, { simulation = false, watermark, logoPngBuffer = null } = {}) {
  if (!evento?.identificacion?.codigoGeneracion || !evento.documento) {
    return Promise.reject(new Error('El evento de invalidación no trae identificación ni documento'));
  }
  if (typeof evento.selloRecibido !== 'string' || !evento.selloRecibido.trim()) {
    return Promise.reject(new Error('No se puede generar el PDF del evento sin sello de recepción'));
  }

  return new Promise((resolve, reject) => {
    const doc = new PDFDocument({
      size: 'LETTER',
      margins: { top: PAGINA.superior, left: PAGINA.izquierda, right: PAGINA.ancho - PAGINA.derecha, bottom: 8 },
      bufferPages: true,
      info: { Title: estilo.textoPdf(`Evento de invalidación ${evento.identificacion.codigoGeneracion}`) },
    });
    const chunks = [];
    doc.on('data', (chunk) => chunks.push(chunk));
    doc.on('end', () => resolve(Buffer.concat(chunks)));
    doc.on('error', reject);

    const datos = _datosEvento(evento);
    const ctx = {
      doc,
      datos,
      y: PAGINA.superior,
      // Lo que usa el encabezado de continuación de las tablas compartidas.
      nombreTipo: 'Evento de invalidación',
      dte: { identificacion: { numeroControl: datos.documento.numeroControl, codigoGeneracion: datos.codigoGeneracion } },
      opciones: { simulation, watermark, logoPngBuffer },
    };

    ctx.y = Math.max(_dibujarMembrete(ctx), _dibujarCajaEvento(ctx)) + 10;
    if (simulation) estilo.dibujarFranjaSimulacion(ctx);
    _dibujarPartes(ctx, {
      titulo: 'Identificación del emisor',
      filas: [
        ['Nombre:', datos.emisor.nombre],
        ['NIT:', datos.emisor.nit],
        ['Teléfono:', datos.emisor.telefono],
        ['Correo electrónico:', datos.emisor.correo],
      ],
    }, {
      titulo: 'Identificación del receptor',
      filas: [
        ['Nombre:', datos.receptor.nombre],
        ['Tipo de doc. de identificación:', datos.receptor.tipoDocumento],
        ['N.º de doc. de identificación:', datos.receptor.numDocumento],
        ['Teléfono:', datos.receptor.telefono],
        ['Correo electrónico:', datos.receptor.correo],
      ],
    });
    _dibujarMotivo(ctx);
    _dibujarDocumento(ctx);
    estilo.dibujarPiesYMarcas(doc, { simulation });

    doc.end();
  });
}

module.exports = { generarPDFEventoInvalidacion };
