/**
 * Construye el archivo DTE que se entrega al receptor: payload fiscal más
 * la firma y el sello de recepción. El payload previo a firmar se conserva
 * separado para auditoría, pero nunca se entrega como si fuera el archivo
 * fiscal final.
 */
function construirArchivoDte(row) {
  const payload = JSON.parse(row.payload_json);
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new Error('El payload DTE no es un objeto JSON');
  }
  if (typeof row.documento_firmado !== 'string' || !row.documento_firmado.trim()) {
    throw new Error('El documento firmado no está disponible');
  }

  const documento = {
    ...payload,
    firmaElectronica: row.documento_firmado,
  };
  const selloOMarcador = row.sello_recepcion || row.simulation_marker;
  if (typeof selloOMarcador === 'string' && selloOMarcador.trim()) {
    documento.selloRecibido = selloOMarcador.trim();
  }
  return documento;
}

module.exports = { construirArchivoDte };
