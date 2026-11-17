/**
 * URL de consulta pública que debe ir codificada en el QR de la
 * representación gráfica de todo DTE — confirmada en el Manual Tecnológico
 * para la Integración Tecnológica del Sistema de Transmisión V2.0,
 * sección 5 (Código QR):
 *
 *   https://admin.factura.gob.sv/consultaPublica?ambiente={ambiente}&codGen={codGen}&fechaEmi={fechaEmi}
 *
 * Parámetros (todos van en la URL, sin codificar aparte más allá de lo que
 * exige la URL estándar):
 *   ambiente:  "00" (pruebas) o "01" (producción)
 *   codGen:    codigoGeneracion del DTE (UUID v4 en mayúsculas)
 *   fechaEmi:  fecha de generación del DTE, formato YYYY-MM-DD
 */
function construirUrlConsultaPublica({ ambiente, codigoGeneracion, fechaEmi }) {
  const params = new URLSearchParams({
    ambiente,
    codGen: codigoGeneracion,
    fechaEmi,
  });
  return `https://admin.factura.gob.sv/consultaPublica?${params.toString()}`;
}

module.exports = { construirUrlConsultaPublica };
