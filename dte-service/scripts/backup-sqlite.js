#!/usr/bin/env node

/**
 * Hace un backup consistente de SQLite usando la API online de
 * better-sqlite3. Se ejecuta dentro del contenedor DTE para incluir WAL sin
 * copiar manualmente un archivo que pueda estar en uso.
 *
 * La base de origen es la misma que abre el servicio según DTE_MODE
 * (SQLITE_PATH o, en simulación, DTE_SIMULATION_SQLITE_PATH).
 *
 * Uso:
 *   node scripts/backup-sqlite.js /tmp/dte-backup.sqlite
 */
require('dotenv').config();
const fs = require('node:fs');
const path = require('node:path');
const Database = require('better-sqlite3');
const { rutaSqlite } = require('../src/config/sqlitePath');

async function main() {
  const destination = process.argv[2];
  if (!destination) throw new Error('Debe indicar la ruta destino del backup SQLite');

  // La copia contiene documentos fiscales: solo la lee el dueño del proceso.
  process.umask(0o077);
  const source = rutaSqlite(process.env);
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  if (fs.existsSync(destination)) throw new Error(`El destino ya existe: ${destination}`);

  // Una ruta equivocada no debe crear (y respaldar) una base vacía.
  const db = new Database(source, { fileMustExist: true });
  try {
    // PASSIVE no bloquea lectores ni intenta forzar a escritores activos.
    db.pragma('wal_checkpoint(PASSIVE)');
    await db.backup(destination);
  } finally {
    db.close();
  }

  // La copia hereda el modo WAL de la fuente. En modo DELETE queda en un solo
  // archivo y se puede abrir en solo lectura sin crear -wal/-shm a su lado.
  const copy = new Database(destination, { fileMustExist: true });
  try {
    copy.pragma('journal_mode = DELETE');
  } finally {
    copy.close();
  }

  const stat = fs.statSync(destination);
  if (stat.size === 0) throw new Error('El backup SQLite quedó vacío');
  process.stdout.write(JSON.stringify({ source, destination, bytes: stat.size }) + '\n');
}

main().catch((error) => {
  process.stderr.write((error instanceof Error ? error.message : String(error)) + '\n');
  process.exitCode = 1;
});
