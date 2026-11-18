# Firmador oficial de Hacienda

Código fuente del firmador de documentos tributarios electrónicos que el Ministerio de Hacienda
de El Salvador entrega a los contribuyentes (`svfe-api-firmador.zip`, versión 2.0.0 del
`pom.xml`). Se copió sin cambios. Lo único agregado es lo de este proyecto:

- `Dockerfile.erp`: compila el jar con Maven y lo corre sobre un JRE 21, con usuario sin
  privilegios y chequeo de salud en `GET /firmardocumento/status`.
- `PROCEDENCIA.md`: esta nota.

El `Dockerfile` original se conserva tal como lo entregó Hacienda.

## Cómo lo usa el ERP

- Corre como el servicio `dte-signer` de `compose.yaml`, solo en la red interna (puerto 8113,
  perfil `nonssl`).
- Firma con `POST /firmardocumento/` (`nit`, `activo`, `passwordPri`, `dteJson`) usando el
  certificado `{nit}.crt` de la carpeta `CERTIFICATE_HOME`. El volumen `dte-certificates` se
  comparte con `dte-service`, que escribe ahí el certificado de cada empresa. Así un mismo firmador
  sirve a varias empresas.

## Actualizar

Cuando Hacienda publique otra versión, reemplazar `pom.xml` y `src/` con los del nuevo paquete,
revisar `Dockerfile.erp` y correr las pruebas del servicio DTE.
