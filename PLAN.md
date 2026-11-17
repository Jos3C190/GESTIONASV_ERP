# Plan: Ventas V3b — Facturar el pedido (documento fiscal en el ERP)

Rama: `feature/ventas-v3b-facturar`, desde `develop` con V3a (#48).

Fuente: `docs/plan-area-ventas-el-salvador.pdf`.
- Módulo 5 (DTE).
- Secciones:
  - 6.3, estados del documento fiscal;
  - 6.4, el ERP es dueño de la venta y del cálculo fiscal, y guarda su copia del JSON, el sello y el PDF;
  - 6.5, el emisor se arma con tres niveles: empresa, sucursal y caja.

## Decisiones del usuario

- 17/11/2026 (V3):
  - «Facturar» es una acción sobre el pedido confirmado: un DTE por el pedido completo.
  - El servicio vive en `dte-service/` y es multiemisor (V3a).
  - Correo en V3c; ambiente de pruebas de Hacienda en V3d.
- 17/11/2026 (V3b):
  - **Cuándo**: se puede facturar en cualquier momento desde que el pedido está confirmado, antes, durante o después de entregar.
  - **Cancelar**: un pedido facturado ya no se cancela. Se resuelve con invalidación o nota de crédito en V4.
- El usuario delegó el merge de las PR cuando pasen los checks propios. Si el auto-merge de GitHub no dispara con los checks en verde, se mergea a mano.

## Hechos verificados

- Configuración fiscal del ERP (V1):
  - perfil con `operating_mode` (simulado, pruebas o producción), categoría, correo y teléfono DTE;
  - identidad de la empresa: nombre, nombre comercial, NIT y NRC;
  - actividades;
  - establecimientos por sucursal, con tipo, código, actividad y dirección codificada, y sus puntos de venta;
  - tipos de documento habilitados.
- El pedido (V2e) guarda por línea el precio en forma del documento, el descuento, gravado, exento, no sujeto, IVA, tratamiento y tipo de ítem; y los totales del motor fiscal, incluidos retención y percepción.
- El servicio (V3a), en el contrato v2:
  - **Retención y percepción**: fija `ivaRete` e `ivaPerci` en 0.
  - **Condición de operación**: siempre `CONTADO`.
  - **Descuento global**: lo prorratea a las líneas; el ERP lo lleva en el resumen.
  - **Snapshot del emisor**: lo valida con un hash SHA-256 del JSON canónico (llaves ordenadas).
- Infraestructura del ERP: almacenamiento S3 (`object_storage.py`, `upload_from` y descargas firmadas) y cola arq sobre Redis (la usa el OCR).

## Diseño

- **El servicio respeta el cálculo del ERP** (paso 1). El contrato v2 acepta:
  - `condicionOperacion` (contado o crédito) y `plazoDias`;
  - `ivaRete` (factura y CCF) e `ivaPerci` (CCF);
  - `descuentoGlobalEnResumen`: los descuentos globales van a `descuGravada`, `descuExenta` y `descuNoSuj`, sin prorratear.
  - Cada valor se valida contra las reglas de Hacienda: 1 % desde $100 sin IVA y holgura de ±0.01.
- **Documento fiscal** (`sales_fiscal_documents`):
  - Llaves: empresa, sucursal, pedido (único mientras el documento no haya fallado de forma definitiva), tipo y modo.
  - Estados: `pending`, `issued` (sellado), `simulated`, `rejected` y `failed`.
  - Identidad: código de generación y número de control.
  - Origen: establecimiento y punto de venta.
  - Contenido: snapshot del emisor, solicitud enviada, JSON devuelto, sello y respuesta de Hacienda.
  - Archivos: llaves del JSON y del PDF en el almacenamiento.
  - Control: error, intentos, clave de idempotencia, responsables y fechas.
- **Emisor**: se arma con el perfil, la identidad, la actividad y la dirección del establecimiento de la sucursal y el punto de venta elegido, con su hash. Antes de emitir, el ERP registra o actualiza a la empresa en el servicio (`PUT /api/emisores/:nit`) con su modo y sus tipos habilitados.
- **Facturar**:
  1. Valida el pedido: confirmado, sin documento vigente y con el documento habilitado.
  2. Crea el documento en `pending` y encola la emisión en arq (`dte-worker`).
  3. El trabajador llama al servicio con la clave de idempotencia del documento, baja el JSON y el PDF y los guarda en el almacenamiento.
  - Reintentar reusa la misma clave.
  - Antes de enviar, se verifica que los totales del JSON coincidan exactamente con los del pedido; si no, falla sin enviar.
- **Permisos**: `sales_invoices:read` y `sales_invoices:issue`. Toda acción queda en la bitácora.
- **Pantallas**:
  - «Facturar» en el pedido confirmado, que elige el punto de venta si la sucursal tiene varios;
  - bandeja «Documentos fiscales» con estado, tipo, número de control y total;
  - detalle con descarga del JSON y del PDF.
- **Despliegue**: `dte-service` y `dte-worker` pasan al arranque normal. La API key ya está en `.env`.

## Pasos

- [x] **Paso 0: plan.**
- [x] **Paso 1: servicio, contrato v2 ampliado.** Condición y plazo, retención, percepción y descuento global en el resumen, con pruebas.
- [x] **Paso 2: migración `0126` y modelos.** `sales_fiscal_documents`, permisos y bloqueo de la cancelación de pedidos facturados.
- [x] **Paso 3: dominio.** Snapshot del emisor con su hash, receptor, líneas y resumen desde el pedido, conciliación de totales y estados. Pruebas unitarias.
- [x] **Paso 4: infraestructura.**
  - Cliente HTTP del servicio (`app/infrastructure/dte_service_client.py`, puerto `app/domain/ports/dte_service.py`).
  - Configuración `DTE_SERVICE_*` y compose: `dte-service` en el arranque normal.
  - El trabajador y el guardado del JSON y el PDF pasan al paso 5, porque dependen del repositorio y de los casos de uso.
- [x] **Paso 5: aplicación y API.**
  - Repositorio del documento fiscal y trabajador arq `dte-worker` (emisión, JSON y PDF al almacenamiento, conciliación periódica de pendientes).
  - Facturar, reintentar, lista, detalle y descargas.
  - Registro del emisor.
  - Pruebas e2e contra el servicio real en simulado, con dos empresas.
- [ ] **Paso 6: frontend.** Facturar en el pedido, bandeja, detalle y menú. vitest.
- [ ] **Paso 7: documentación.** `docs/api.md`, `docs/database-schema.md` §36 y manual de facturación.
- [ ] **Paso 8: verificación y PR.** Batería completa, QA en el navegador y PR a `develop` con auto-merge.

## Estado actual

- **Paso en curso**: 6 (frontend).
  - Paso 5:
    - API (`routers/sales_invoices.py`):
      - `GET /sales/{id}/invoice-options`;
      - `POST /sales/{id}/invoice` (202 al crear; 200 si el pedido ya tenía documento, que se devuelve el mismo);
      - `GET /sales/fiscal-documents` (filtros `branch_id`, `sale_id`, `status`, `document_type`, `q`), `GET …/{id}`, `POST …/{id}/retry`, `GET …/{id}/json` (archivo) y `GET …/{id}/pdf` (enlace firmado).
    - Trabajador `dte-worker` (`app/infrastructure/dte_worker.py`, cola `arq:dte`):
      - registra al emisor (`PUT /api/emisores/:nit`), emite y baja el JSON y el PDF al almacenamiento;
      - concilia los pendientes cada 20 s;
      - la API encola después del commit.
    - e2e `tests/e2e/test_sales_invoices.py` (3) contra el servicio real; procesan con `process_fiscal_document` porque el trabajador mira la base de desarrollo.
  - **Decisión (reanudación del 17/11/2026)**: el servicio guardaba bajo la Idempotency-Key los rechazos del emisor (tipo no habilitado, emisor no autorizado o inactivo, modo no disponible) y los repetía para siempre. Ahora `guardarResultado` libera la clave cuando no hay identidad reservada, así el reintento usa la misma clave sin riesgo de duplicar. Prueba en `test/unit/idempotency.test.js`.
  - Paso 4: errores del servicio clasificados en reintentables (red, 5xx, `IDEMPOTENCY_IN_PROGRESS`, `ISSUER_MODE_UNAVAILABLE`) y definitivos (4xx, `FIRMADOR_CONFIGURATION_ERROR`). `DTE_SERVICE_URL` vacío = facturación deshabilitada; con URL exige `DTE_SERVICE_API_KEY`. El backend debe recrearse (`docker compose up -d backend`) para tomar las variables nuevas.
  - Paso 3: `app/domain/entities/sales_fiscal_document.py`.
    - Hash del emisor: `canonical_json` = llaves ordenadas, sin espacios, `ensure_ascii=False`. Se comprobó contra `issuerContractV2.js` (la prueba fija el hash que calculó el servicio).
    - Códigos MH: `M001` → tipo `02` y `001`; `P001` → `001`. `codEstable` y `codPuntoVenta` llevan el código del ERP.
    - Solicitudes de factura y CCF pasadas por los constructores reales del servicio: válidas contra el schema oficial y con los mismos totales.
- **Decisiones de diseño (paso 3)**:
  - Pago: contado `01` (billetes y monedas) y crédito `99` con plazo en días. La forma de pago real llega con cobros (V5).
  - Servicios (`tipoItem` 2) van con `uniMedida` 99; los bienes, con el CAT-014 de la unidad de la empresa o 59.
  - Consumidor final genérico: factura sin receptor. DUI con guion antes del verificador.
  - Conciliación en dos tiempos. Antes de enviar, la solicitud debe cuadrar al centavo con el pedido (`sales_invoice_totals_mismatch`, no se envía). Después, `dte_differences` compara el resumen devuelto; como el documento ya existe, una diferencia queda registrada en el documento para revisión, no lo anula.
  - `rejected` sigue contando como documento vigente; su corrección se resuelve en V3d con Hacienda.
  - Paso 2: tabla `sales_fiscal_documents` (un documento vigente por pedido; los `failed` se pueden reintentar), permisos `sales_invoices:read` e `sales_invoices:issue` para SUPER_ADMIN, y `cancel` del pedido responde 422 `sales_order_invoiced` si hay un documento no fallido. Pruebas: `tests/integration/test_sales_fiscal_documents_migration.py` y `test_invoiced_order_cannot_be_cancelled`.
  - Paso 1:
    - `ajustes` en factura y CCF (v1 y v2): `condicionOperacion` (1, 2 o 3), `plazoDias` (obligatorio a crédito), `ivaRete`, `ivaPerci` (solo CCF) y `descuentoGlobalEnResumen`.
    - Se validan con 1 % desde $100 sin IVA y holgura de ±0.01.
    - A crédito, el pago lleva `plazo` 01 y `periodo` en días.
    - Pruebas: `test/unit/ajustesErp.test.js` (5, con validación del schema oficial); 472 en total.
- **Pendiente de confirmar en certificación (V3d)**: con descuento global en el resumen, la factura informa `totalIva` sobre la base neta (`(gravada − descuGravada) × 0.13/1.13`), como el motor del ERP. Hay que confirmarlo contra Hacienda en el ambiente de pruebas.
- **Contexto**:
  - El frontend usa SvelteKit 3.
  - El servicio DTE se prueba con `./scripts/run-tests.sh dte`.
  - El proyecto de referencia es de solo lectura.
- **Comandos**:
  - Pruebas con objetivo explícito. Sin argumento corre la batería completa (unos 45 minutos).
  - No hacer commits mientras corre la batería.
- **Reglas del usuario**:
  - Commits y PR sin Co-Authored-By ni «Generated with Claude Code».
  - PR hacia `develop` con Auto-fix y auto-merge.
  - Ignorar el check de Vercel.
  - Dentro de una empresa, la interfaz no menciona a otras empresas.
