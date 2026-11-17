const Database = require('better-sqlite3');
const fs = require('fs');
const path = require('path');
const config = require('../config');

const dir = path.dirname(config.db.path);
if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

const db = new Database(config.db.path);
db.pragma('journal_mode = WAL');
// Sin esto, SQLite NO aplica las restricciones FOREIGN KEY declaradas más
// abajo (es el comportamiento por defecto de SQLite/better-sqlite3) — se
// podría insertar una fila en cola_reintentos apuntando a un codigo_generacion
// que no existe en dtes, y la restricción sería solo decorativa.
db.pragma('foreign_keys = ON');

db.exec(`
  CREATE TABLE IF NOT EXISTS correlativos (
    tipo_dte TEXT NOT NULL,
    anio INTEGER NOT NULL,
    cod_establecimiento TEXT NOT NULL,
    cod_punto_venta TEXT NOT NULL,
    ultimo INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (tipo_dte, anio, cod_establecimiento, cod_punto_venta)
  );

  CREATE TABLE IF NOT EXISTS dtes (
    codigo_generacion TEXT PRIMARY KEY,
    numero_control TEXT NOT NULL,
    tipo_dte TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'PENDIENTE', -- PENDIENTE | FIRMADO | TRANSMITIDO | RECHAZADO | PENDIENTE_REINTENTO | PENDIENTE_RECONCILIACION | RECONCILIACION | CONTINGENCIA | CONTINGENCIA_REPORTADA | INVALIDADO | ERROR_FIRMA
    payload_json TEXT NOT NULL,
    documento_firmado TEXT,
    sello_recepcion TEXT,
    observaciones TEXT,
    intentos INTEGER NOT NULL DEFAULT 0,
    creado_en TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT NOT NULL DEFAULT (datetime('now'))
  );

  CREATE TABLE IF NOT EXISTS cola_reintentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_generacion TEXT NOT NULL,
    accion TEXT NOT NULL, -- TRANSMITIR | ANULAR | CONTINGENCIA
    intentos INTEGER NOT NULL DEFAULT 0,
    proximo_intento TEXT NOT NULL DEFAULT (datetime('now')),
    ultimo_error TEXT,
    creado_en TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (codigo_generacion) REFERENCES dtes(codigo_generacion)
  );

  CREATE TABLE IF NOT EXISTS idempotency_keys (
    clave TEXT PRIMARY KEY,
    estado TEXT NOT NULL DEFAULT 'PROCESANDO', -- PROCESANDO | COMPLETADO | PENDIENTE | REINTENTABLE | VALIDACION_REINTENTABLE
    request_hash TEXT,
    codigo_generacion TEXT,
    status_code INTEGER,
    respuesta_json TEXT,
    creado_en TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT NOT NULL DEFAULT (datetime('now')),
    reintentos_validacion INTEGER NOT NULL DEFAULT 0
  );
`);

const dteColumns = new Set(db.pragma('table_info(dtes)').map((column) => column.name));
if (!dteColumns.has('modo_emision')) db.exec("ALTER TABLE dtes ADD COLUMN modo_emision TEXT NOT NULL DEFAULT 'HACIENDA_TEST'");
if (!dteColumns.has('simulation_run_id')) db.exec('ALTER TABLE dtes ADD COLUMN simulation_run_id TEXT');
if (!dteColumns.has('simulation_marker')) db.exec('ALTER TABLE dtes ADD COLUMN simulation_marker TEXT');
// Reenvíos hechos después de confirmar que Hacienda no recibió el documento
// (Manual Técnico 3.3: máximo 2 antes de pasar a contingencia).
if (!dteColumns.has('reenvios')) db.exec('ALTER TABLE dtes ADD COLUMN reenvios INTEGER NOT NULL DEFAULT 0');
// Fecha (YYYY-MM-DD) del sello de recepción: base de los plazos de invalidación.
if (!dteColumns.has('fecha_sello')) db.exec('ALTER TABLE dtes ADD COLUMN fecha_sello TEXT');

// Eventos fiscales firmados (invalidación y contingencia) con identidad
// propia: un reintento con la misma Idempotency-Key reenvía el mismo evento
// en vez de generar otro.
db.exec(`
  CREATE TABLE IF NOT EXISTS eventos (
    codigo_generacion TEXT PRIMARY KEY,
    tipo TEXT NOT NULL, -- INVALIDACION | CONTINGENCIA
    dte_codigo_generacion TEXT,
    estado TEXT NOT NULL DEFAULT 'PENDIENTE', -- PENDIENTE | ERROR_FIRMA | FIRMADO | ACEPTADO | RECHAZADO | SIN_CONFIRMAR | CONCILIACION
    payload_json TEXT NOT NULL,
    documento_firmado TEXT,
    sello_recepcion TEXT,
    respuesta_json TEXT,
    creado_en TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (dte_codigo_generacion) REFERENCES dtes(codigo_generacion)
  );
  CREATE INDEX IF NOT EXISTS idx_eventos_dte ON eventos(dte_codigo_generacion);
`);

// Invalidación simulada (DEC-010): el marcador sintético nunca va en
// sello_recepcion. modo_emision se hereda del DTE; queda NULL en eventos sin
// DTE (contingencia), que pertenecen al modo de esta base.
const eventoColumns = new Set(db.pragma('table_info(eventos)').map((column) => column.name));
if (!eventoColumns.has('simulation_marker')) db.exec('ALTER TABLE eventos ADD COLUMN simulation_marker TEXT');
if (!eventoColumns.has('modo_emision')) {
  db.transaction(() => {
    db.exec('ALTER TABLE eventos ADD COLUMN modo_emision TEXT');
    db.exec(`UPDATE eventos SET modo_emision = (
      SELECT dtes.modo_emision FROM dtes WHERE dtes.codigo_generacion = eventos.dte_codigo_generacion
    ) WHERE dte_codigo_generacion IS NOT NULL`);
  })();
}

// Contingencia (Manual Funcional VIII): una ventana agrupa los documentos
// generados en modelo diferido con el mismo tipo y motivo, y se informa con
// un único Evento de Contingencia (máximo 1000 documentos).
db.exec(`
  CREATE TABLE IF NOT EXISTS contingencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    estado TEXT NOT NULL DEFAULT 'ACTIVA', -- ACTIVA | CERRADA | REPORTADA | COMPLETADA
    tipo_contingencia INTEGER NOT NULL,
    motivo TEXT,
    forzada INTEGER NOT NULL DEFAULT 0,
    inicio TEXT NOT NULL, -- ISO 8601 UTC
    fin TEXT,
    evento_codigo_generacion TEXT,
    evento_sello TEXT,
    evento_sello_en TEXT,
    intentos_evento INTEGER NOT NULL DEFAULT 0,
    proximo_intento_evento TEXT,
    ultimo_error TEXT,
    creado_en TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT NOT NULL DEFAULT (datetime('now'))
  );

  CREATE TABLE IF NOT EXISTS contingencia_documentos (
    contingencia_id INTEGER NOT NULL,
    codigo_generacion TEXT NOT NULL UNIQUE,
    PRIMARY KEY (contingencia_id, codigo_generacion),
    FOREIGN KEY (contingencia_id) REFERENCES contingencias(id),
    FOREIGN KEY (codigo_generacion) REFERENCES dtes(codigo_generacion)
  );
`);
// Versión transmitida originalmente (modelo previo) de un documento que se
// convirtió a diferido: se restaura si Hacienda sí lo había recibido.
// Multiemisor: a qué emisor pertenece cada documento (null = un solo emisor heredado).
if (!new Set(db.pragma('table_info(dtes)').map((column) => column.name)).has('nit')) {
  db.exec('ALTER TABLE dtes ADD COLUMN nit TEXT');
  db.exec('CREATE INDEX IF NOT EXISTS idx_dtes_nit ON dtes(nit)');
}
const dteColumnsContingencia = new Set(db.pragma('table_info(dtes)').map((column) => column.name));
// V4a del ERP: una ventana de contingencia por emisor y establecimiento ('' = sin dato,
// emisor heredado del entorno). Las ventanas anteriores toman el emisor y el establecimiento
// de sus documentos.
const contingenciaColumns = new Set(db.pragma('table_info(contingencias)').map((column) => column.name));
if (!contingenciaColumns.has('nit_emisor')) {
  db.exec("ALTER TABLE contingencias ADD COLUMN nit_emisor TEXT NOT NULL DEFAULT ''");
  db.exec("ALTER TABLE contingencias ADD COLUMN cod_establecimiento TEXT NOT NULL DEFAULT ''");
  db.prepare(
    `UPDATE contingencias SET
       nit_emisor = COALESCE((SELECT t.nit FROM contingencia_documentos d JOIN dtes t ON t.codigo_generacion = d.codigo_generacion
                              WHERE d.contingencia_id = contingencias.id AND t.nit IS NOT NULL LIMIT 1), ?),
       cod_establecimiento = COALESCE((SELECT json_extract(t.payload_json, '$.emisor.codEstable')
                                       FROM contingencia_documentos d JOIN dtes t ON t.codigo_generacion = d.codigo_generacion
                                       WHERE d.contingencia_id = contingencias.id LIMIT 1), ?)`
  ).run(config.emisor?.nit ?? '', config.emisor?.codEstableInterno ?? '');
}
db.exec(`
  DROP INDEX IF EXISTS idx_contingencia_unica_activa;
  CREATE UNIQUE INDEX IF NOT EXISTS idx_contingencia_activa_por_establecimiento
    ON contingencias(nit_emisor, cod_establecimiento) WHERE estado = 'ACTIVA';
`);
if (!dteColumnsContingencia.has('payload_original_json')) db.exec('ALTER TABLE dtes ADD COLUMN payload_original_json TEXT');
if (!dteColumnsContingencia.has('documento_firmado_original')) db.exec('ALTER TABLE dtes ADD COLUMN documento_firmado_original TEXT');

const colaColumns = new Set(db.pragma('table_info(cola_reintentos)').map((column) => column.name));
// SIN_RESPUESTA (timeout/5xx) o DUPLICADO (Hacienda dijo "ya existe").
if (!colaColumns.has('motivo')) db.exec('ALTER TABLE cola_reintentos ADD COLUMN motivo TEXT');

// idEnvio es "Integer" en el API de Hacienda: se usa un correlativo propio
// en vez de Date.now(), que excede los 32 bits.
db.exec(`
  CREATE TABLE IF NOT EXISTS secuencia_envios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creado_en TEXT NOT NULL DEFAULT (datetime('now'))
  );
`);
const insertarEnvio = db.prepare('INSERT INTO secuencia_envios DEFAULT VALUES');
function siguienteIdEnvio() {
  return Number(insertarEnvio.run().lastInsertRowid);
}

// Migración compatible para bases SQLite creadas antes de que la
// idempotencia quedara ligada al request y a la identidad fiscal.
const idempotencyColumns = new Set(db.pragma('table_info(idempotency_keys)').map((column) => column.name));
if (!idempotencyColumns.has('request_hash')) {
  db.exec('ALTER TABLE idempotency_keys ADD COLUMN request_hash TEXT');
}
if (!idempotencyColumns.has('codigo_generacion')) {
  db.exec('ALTER TABLE idempotency_keys ADD COLUMN codigo_generacion TEXT');
}
if (!idempotencyColumns.has('reintentos_validacion')) {
  db.exec('ALTER TABLE idempotency_keys ADD COLUMN reintentos_validacion INTEGER NOT NULL DEFAULT 0');
}
db.exec('CREATE INDEX IF NOT EXISTS idx_idempotency_codigo_generacion ON idempotency_keys(codigo_generacion)');

/**
 * Obtiene el siguiente correlativo de forma atómica (transacción) para
 * un tipo de DTE + año + establecimiento + punto de venta.
 * El correlativo NUNCA debe reiniciarse salvo cambio de año fiscal, y
 * nunca debe reutilizarse un número ya emitido.
 */
// Multiemisor: el correlativo se lleva por emisor (NIT) y ambiente además del
// tipo, año, establecimiento y punto de venta. Las filas de un solo emisor
// (sin NIT) quedan con nit = '' y ambiente = '' y siguen su propia serie.
const columnasCorrelativo = new Set(db.pragma('table_info(correlativos)').map((column) => column.name));
if (!columnasCorrelativo.has('nit')) {
  db.exec(`
    CREATE TABLE correlativos_emisor (
      nit TEXT NOT NULL DEFAULT '',
      ambiente TEXT NOT NULL DEFAULT '',
      tipo_dte TEXT NOT NULL,
      anio INTEGER NOT NULL,
      cod_establecimiento TEXT NOT NULL,
      cod_punto_venta TEXT NOT NULL,
      ultimo INTEGER NOT NULL DEFAULT 0,
      PRIMARY KEY (nit, ambiente, tipo_dte, anio, cod_establecimiento, cod_punto_venta)
    );
    INSERT INTO correlativos_emisor (tipo_dte, anio, cod_establecimiento, cod_punto_venta, ultimo)
      SELECT tipo_dte, anio, cod_establecimiento, cod_punto_venta, ultimo FROM correlativos;
    DROP TABLE correlativos;
    ALTER TABLE correlativos_emisor RENAME TO correlativos;
  `);
}

const obtenerSiguienteCorrelativo = db.transaction(
  (tipoDte, anio, codEstablecimiento, codPuntoVenta, nit = '', ambiente = '') => {
  const row = db
    .prepare(
      `SELECT ultimo FROM correlativos
       WHERE nit = ? AND ambiente = ? AND tipo_dte = ? AND anio = ? AND cod_establecimiento = ?
         AND cod_punto_venta = ?`
    )
    .get(nit, ambiente, tipoDte, anio, codEstablecimiento, codPuntoVenta);

  const siguiente = (row?.ultimo || 0) + 1;

  db.prepare(
    `INSERT INTO correlativos (nit, ambiente, tipo_dte, anio, cod_establecimiento, cod_punto_venta, ultimo)
     VALUES (?, ?, ?, ?, ?, ?, ?)
     ON CONFLICT(nit, ambiente, tipo_dte, anio, cod_establecimiento, cod_punto_venta)
     DO UPDATE SET ultimo = excluded.ultimo`
  ).run(nit, ambiente, tipoDte, anio, codEstablecimiento, codPuntoVenta, siguiente);

  return siguiente;
  }
);

module.exports = { db, obtenerSiguienteCorrelativo, siguienteIdEnvio };
