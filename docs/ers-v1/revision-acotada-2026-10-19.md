# Revisión acotada de cierre ERS — 19/10/2026

**Seguimiento posterior:** H01 y H02 se corrigieron y comprobaron durante la [revisión ampliada B01–B08](revision-completa-2026-10-19.md), continuada el 20/10/2026. Este documento conserva el diagnóstico inicial; no representa los pendientes actuales.

## Alcance y resultado

Revisión estática solicitada por el usuario para avanzar con un consumo limitado. Se revisaron el servicio, contratos y rutas de devoluciones B08, su enlace con las asignaciones de entrega B07, las pruebas de permisos de fraccionamiento y el informe de aceptación B01–B08. No se ejecutaron pruebas nuevas ni se modificó la aplicación o los datos en esta revisión.

Resultado: dos defectos concretos pendientes y aceptación integral todavía parcial. Esto no constituye una aprobación de todos los bloques.

## Hallazgos

### H01 — P2: se pueden guardar motivos vacíos en devoluciones

- `backend/app/api/v1/schemas/sales_return.py:16` y `:31` validan longitud mínima antes de quitar espacios.
- `backend/app/application/sales/returns.py:420`, `:698` y `:715` guardan `reason.strip()` sin volver a comprobar la longitud.
- Por lectura del código, un cliente API puede enviar `reason: "   "`, superar los tres caracteres y terminar con un motivo vacío en la creación o resolución. También se acepta `" a "` y se almacena un solo carácter. No se reprodujo mediante petición en esta revisión.
- Impacto: se pierde la justificación obligatoria de una devolución o de su aceptación/rechazo. La cancelación sí normaliza y valida correctamente.
- Corrección propuesta: normalizar antes de validar la longitud en ambos contratos y mantener una validación defensiva en el servicio si admite otras entradas. Añadir casos de espacios, longitud tras normalización y texto válido; comprobar que el rechazo no genera documento, evento ni movimiento.

### H02 — P2: dos pruebas de permisos comprueban el nombre antiguo del botón

- `frontend/tests/unit/WarehouseHandlingUnitsIntegration.test.ts:209` y `:217` comprueban que no exista «Preparar fracción».
- El caso positivo del mismo archivo, línea 193, ya utiliza «Dividir unidad» y abre «Otras acciones».
- Impacto: las dos comprobaciones negativas pueden pasar aunque se exponga indebidamente la acción actual. Esto es un defecto de cobertura, no demuestra por sí solo una vulnerabilidad del permiso real.
- Corrección propuesta: usar el nombre vigente, contemplar el menú y comprobar que no sea posible invocar la división con almacén no apto o sin `inventory:move`. Verificar también que no se llamó al servicio de división.

## Lo observado en el código de B08

- Creación, recepción, cancelación y resolución contienen transacciones anidadas para revertir fallos.
- Se comprueba el origen de la entrega y se limita lo aceptado/reservado a la cantidad entregada.
- Las operaciones usan claves de idempotencia y bloqueo de la venta.
- La aceptación crea una entrada en cuarentena vinculada a la valoración original; el rechazo no crea esa entrada.

Estas observaciones estáticas no sustituyen una prueba de concurrencia, permisos o conciliación.

## Pendiente para retomar

1. Corregir H01/H02 y ejecutar sus pruebas focalizadas.
2. Ejecutar la aceptación integrada E01–E15 del informe `revision-integral-bloques-01-08.md`. La ausencia de clientes/ventas en la demo exige preparar datos ficticios; no es por sí sola un bloqueo técnico ni evidencia de que el flujo falle.
3. Priorizar retaceo tardío y devolución al costo original, resoluciones concurrentes, perfiles y alcance entre empresas/sucursales, y liberación de la HU devuelta con etiqueta/Kardex.
4. Completar la revisión de código de B01–B06 y el resto de B07: no se auditaron de forma exhaustiva en esta pasada.
5. Registrar IDs, saldos antes/después y resultados reales del recorrido. No se requieren impresora ni lector físicos.

La evidencia de 483 pruebas frontend y la E2E de B08 corresponde a la ejecución anterior documentada; no se repitió aquí. El checklist B09 continúa formando parte del cierre de B08.
