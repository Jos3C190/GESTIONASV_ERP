# Revisión del informe de Luna — cierre B01–B08

**Corte vigente:** 21/10/2026, America/El_Salvador. Este informe se actualizó tras ejecutar comprobaciones focalizadas P01–P04, la verificación final de cuatro puntos y corregir la documentación P06. Los informes previos quedan como historia.

## Dictamen vigente

### Actualización final — 21/10/2026

En clon aislada se aprobaron V04-01 ajuste correctivo, V04-02 traslado 8+2 y V04-03 devolución mixta con persistencia. El historial de valoración confirma antes/después de los ajustes, traslados, entregas y retorno; los cuatro SKU protegidos coinciden con el baseline. El dictamen global continúa **PARCIAL**: V01 carece de matriz completa de permisos/documentos, V02 no tiene PNG archivados, V03 no cubre recepción repetida/alias/consulta privada ajena, y V04-04 no simuló una respuesta perdida después del commit. Ver [informe final](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/informe-final.md), [conciliación por SKU](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/conciliacion-final.md) y [cierre vigente](cierre-visual-y-permisos-b01-b08.md).

### Contexto de la continuación del 20/10/2026

La continuación encontró y corrigió la omisión de identidad de lote en la ficha privada de unidad logística: ahora diferencia lote de fabricante, detalle canónico y cabecera de recepción. P01 agregó una prueba PostgreSQL de permisos/descarga documental de ajustes y actualizó la referencia API/RBAC. P04 agregó evidencia persistida para corrección de ajuste, traslado parcial/final y devolución parcial con múltiples asignaciones, incluidos rollback e idempotencia. P03 se comprobó en la ficha de una HU real mediante lectura sin escritura.

La aceptación integrada sigue **PARCIAL**. No se completó la matriz finita E13 de todos los módulos; no se pudo archivar PNG desde la sesión CUA disponible; P03 aún requiere recepción visual con varias líneas del mismo SKU y filtros UI de códigos con registros aplicables; P04 aún requiere devolución mixta operada en interfaz y recuperación de respuesta perdida desde navegador. El E2E de documentos simula emisión del URL y no verifica bytes ni vencimiento. Los cuatro SKU protegidos se conciliaron antes y después en solo lectura.

La evidencia detallada está en [casos P01–P04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/p01-p04-casos-y-evidencia.md), [cierre de pasada](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/cierre-de-pasada.md), [matriz E13](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/matriz-permisos.md) y [cierre integrado](cierre-visual-y-permisos-b01-b08.md).

## Resultado de las observaciones anteriores

| ID | Estado actual | Evidencia / siguiente acción |
| --- | --- | --- |
| A01 / P01 — autorización | Parcial. Se probó acceso al documento de ajuste por perfil, sucursal y empresa; redacción, descarga, retiro y nueva autorización. | [Prueba P01](../../backend/tests/e2e/test_inventory_adjustment_permissions.py), [comando/log P01](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/p01-adjustment-document-permission-rerun.log). Derivar y ejecutar las acciones restantes desde routers/contratos; no extrapolar a otros módulos. |
| A02 / P02 — evidencia visual | Pendiente. La observación de la UI no produjo PNG exportable desde la capacidad CUA disponible. | Siguiente: reabrir las vistas en un navegador/sesión con captura exportable y guardar metadatos de ruta, tema, tamaño, perfil y estado para las siete familias. |
| A03 / P03–P04 — procesos | Parcial. La ficha HU fue corregida; API/PostgreSQL cubre ajuste correctivo, traslado parcial/final y devolución parcial/multi-asignación. | [Evidencia P01–P04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/p01-p04-casos-y-evidencia.md). Siguiente: recepción repetida, UI de devolución mixta y recuperación con respuesta descartada. |
| A04 / P05 — OCR | Resuelto en el corte anterior: pruebas unitarias pasaron 753 con extras dev+ocr. No se volvió a ejecutar la suite completa. | [Log de backend](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/backend-unit-dev-ocr-final.log). |
| A05 / migración y datos | Sin nueva migración en esta continuación; cuatro SKU protegidos volvieron a consultarse en solo lectura. | [Snapshot posterior](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/protected-skus-after-continuation.log). No es necesario repetir restauración sin cambio de esquema. |
| A06 / P06 — coherencia documental | Actualizado: cierre integrado, matriz, manual e informes enlazan el mismo estado y los límites concretos. | Este informe y [evidencia P01–P04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-20/pasada-final/p01-p04-casos-y-evidencia.md). |

## Alcance de las pruebas

No se suman como nuevas las regresiones repetidas del corte anterior. No se ejecutaron suites completas en esta continuación. Las pruebas persistidas nuevas se ejecutaron contra erp_db_test; no se escribieron erp_db ni los SKU protegidos. Vitest focalizado aprobó 47 pruebas; Svelte-check no encontró errores, ESLint enfocado y build aprobaron. Los avisos conocidos no bloquean.

No se requieren impresora, lector HS200 ni hardware físico. El usuario puede continuar con su demostración manual siguiendo [el manual de pruebas y demostración](manual-pruebas-y-demostracion.md), manteniendo por separado la aceptación pendiente aquí descrita.

## Addendum — ejecución final V01–V04, 21/10/2026

V04-01, 02 y 03 aprobaron desde UI persistida en la clon aislada: corrección AJ-000005→AJ-000006, traslado TR-20261021-60344005 recibido 8+2 y devolución DEV-20261021-530AF39F con 2 aceptadas y 1 rechazada desde la primera de dos entregas. El original de ajuste permanece aplicado y vinculado; la devolución aceptada genera una entrada al costo de origen y el rechazo no genera movimiento.

V03 confirmó en UI el producto/SKU/unidad, la separación de cabecera/detalle del lote, el QR público sin campos de costo y la cancelación del formulario de división sin cambio de cantidades. La lectura QR agregó una capability en la clon, anotada sin token. V01 permanece ABIERTO por matriz de acciones/rutas y documentos no exhaustiva; V02 permanece ABIERTO porque no se guardaron PNG; V03 requiere recepción repetida/alias/privacidad UI; V04-04 sigue abierto porque no se pudo interceptar y perder una respuesta postcommit desde el navegador. La salida por punto y la conciliación están en [informe final V01–V04](../../tmp/ers-v1/cierre-visual-y-permisos/2026-10-21/verificacion-cuatro-puntos/informe-final.md).

La conciliación final `READ ONLY` confirmó los cuatro SKU protegidos sin cambios en `erp_db` ni en la clon. Se restauró y verificó CORS de RustFS a los puertos habituales 5173. No se ejecutaron suites completas ni se abrió una migración.
