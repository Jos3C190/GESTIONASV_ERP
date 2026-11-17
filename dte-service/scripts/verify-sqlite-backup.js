#!/usr/bin/env node

/**
 * Verifica integridad SQLite sin modificar el archivo de backup. Informa el
 * conteo de cada tabla y el último correlativo de cada serie: tras restaurar,
 * ninguno puede quedar por debajo de un número de control ya usado.
 */
const fs = require('node:fs');
const Database = require('better-sqlite3');

const file = process.argv[2];
if (!file || !fs.existsSync(file)) {
  console.error('Debe indicar un backup SQLite existente');
  process.exit(1);
}

const db = new Database(file, { readonly: true, fileMustExist: true });
try {
  const integrity = db.pragma('integrity_check', { simple: true });
  const foreignKeys = db.pragma('foreign_key_check');
  const tables = db
    .prepare("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    .pluck()
    .all();
  const counts = {};
  for (const table of tables) {
    counts[table] = db.prepare(`SELECT COUNT(*) FROM "${table.replaceAll('"', '""')}"`).pluck().get();
  }
  const correlativos = tables.includes('correlativos')
    ? db.prepare('SELECT tipo_dte, anio, cod_establecimiento, cod_punto_venta, ultimo FROM correlativos ORDER BY anio, tipo_dte, cod_establecimiento, cod_punto_venta').all()
    : [];

  const result = { file, integrity, foreignKeyViolations: foreignKeys.length, counts, correlativos };
  console.log(JSON.stringify(result));
  if (integrity !== 'ok' || foreignKeys.length > 0) process.exitCode = 1;
} finally {
  db.close();
}
