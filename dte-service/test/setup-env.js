// Variables de entorno mínimas para que src/config/index.js no lance error
// al cargar los módulos durante los tests. Los valores son ficticios, solo
// necesitan tener el formato correcto.
const defaults = {
  DTE_MODE: 'hacienda-test',
  MH_NIT: '06141804941035',
  MH_NRC: '1234567',
  MH_NOMBRE: 'Mi Empresa de Pruebas S.A. de C.V.',
  MH_NOMBRE_COMERCIAL: 'Mi Empresa',
  MH_COD_ACTIVIDAD: '62010',
  MH_DESC_ACTIVIDAD: 'Programación informática',
  MH_TELEFONO: '22221111',
  MH_CORREO: 'facturacion@miempresa.com',
  MH_DIR_DEPARTAMENTO: '06',
  MH_DIR_MUNICIPIO: '23',
  MH_DIR_DISTRITO: '14',
  MH_DIR_COMPLEMENTO: 'Calle Principal #123, San Salvador',
  MH_PASSWORD_API: 'clave-api-de-prueba',
  MH_PASSWORD_PRI: 'clave-privada-de-prueba',
  MH_AMBIENTE: '00',
  MH_COD_ESTABLE_INTERNO: 'CASA',
  MH_COD_PUNTO_VENTA_INTERNO: '',
  MH_TIPO_ESTABLECIMIENTO: '02',
  MH_COD_ESTABLECIMIENTO: '001',
  MH_COD_PUNTO_VENTA: '001',
  MH_AUTH_URL: 'https://apitest.dtes.mh.gob.sv/seguridad/auth',
  MH_RECEPCION_URL: 'https://apitest.dtes.mh.gob.sv/fesv/recepciondte',
  MH_RECEPCION_LOTE_URL: 'https://apitest.dtes.mh.gob.sv/fesv/recepcionlote',
  MH_ANULACION_URL: 'https://apitest.dtes.mh.gob.sv/fesv/anulardte',
  MH_CONTINGENCIA_URL: 'https://apitest.dtes.mh.gob.sv/fesv/contingencia',
  MH_CONSULTA_URL: 'https://apitest.dtes.mh.gob.sv/fesv/recepcion/consultadte',
  MH_CONSULTA_LOTE_URL: 'https://apitest.dtes.mh.gob.sv/fesv/recepcion/consultadtelote',
  FIRMADOR_URL: 'http://localhost:8113/firmardocumento/',
  PORT: '3000',
  LOG_LEVEL: 'silent',
  SQLITE_PATH: ':memory:',
  RETRY_MAX_ATTEMPTS: '5',
  RETRY_BASE_DELAY_MS: '2000',
  MS_API_KEYS: 'clave-de-prueba-para-tests',
  MS_API_KEY_SCOPES: 'issue,read,invalidate,contingency',
  // Explícitos para que un .env local (dotenv no sobrescribe variables ya
  // definidas) no cambie el comportamiento de las pruebas.
  MS_AUTH_DESHABILITADA: 'false',
  DTE_AUTHORIZED_ISSUER_NITS: '06141804941035',
  DTE_ALLOWED_DOCUMENT_TYPES: '01,03',
};

for (const [key, value] of Object.entries(defaults)) {
  if (process.env[key] === undefined) process.env[key] = value;
}
