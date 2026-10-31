# Bloque 6: aceptación del recorrido y preparación de la exposición

Fecha: 29/10/2026. Grupo Lorena. Alcance: cerrar las pruebas del tramo
recepción → retaceo → bodega → inventario → Kardex y comprobar continuidad de
entregas, devoluciones, ajustes y traslados. Este bloque añade aceptación y guion;
no incorpora un rediseño ni nuevas operaciones comerciales en la base de Rodrigo.

## Resultado comprobado

Se ejecutó un caso nuevo contra la API real de FastAPI y PostgreSQL `erp_db_test`.
Cada entrada pasa por solicitud aprobada, cotización respondida/seleccionada,
orden aprobada/enviada, recepción, retaceo manual cerrado, verificación,
medidas, etiqueta confirmada y colocación por un usuario operativo restringido.
No se inyectan asientos para simular el recorrido de estas compras.

| Momento | Físico | Valorado | Valor | Promedio vigente |
|---|---:|---:|---:|---:|
| Primera entrada: 5, FOB 40 + flete 5 + DAI 5 | 5 | 5 | 50 | 10 |
| Segunda entrada: 10, FOB 140 + flete 5 + DAI 5 | 15 | 15 | 200 | 13.333333 |
| Tercera entrada: 15, FOB 290 + flete 5 + DAI 5 | 30 | 30 | 500 | 16.666667 |
| Venta confirmada y entrega en borrador | 30 | 30 | 500 | 16.666667 |
| Entrega confirmada de las tres unidades logísticas completas | 0 | 0 | 0 | Sin existencia |
| Orden de 6; recepción de 4, FOB 90 + flete 5 + DAI 5 | 4 | 4 | 100 | 25 |

La última orden conserva 2 pendientes. Sus 2 unidades no recibidas no entran
en la cantidad ni en el costo. Los costos fijos de este ejercicio son importes
documentados ficticios; no representan tasas arancelarias reales.

Comprobaciones dentro del mismo recorrido:

- Antes de cerrar el retaceo, la verificación que habilita preparación se rechaza.
- El cierre de retaceo y la preparación/impresión de etiquetas conservan cantidad
  y valor anteriores. El comparativo anticipa correctamente la próxima entrada.
- Al colocar se publican cantidad y valor juntos. Repetir la confirmación con
  la misma clave devuelve el resultado original sin duplicar el ingreso.
- Las tres recepciones mantienen identidades de lote distintas; la etiqueta
  conserva recepción y lote. El Kardex físico presenta referencias COM legibles.
- El cierre bloquea la bitácora de gastos reales de su orden, incluso cuando
  queda una cantidad pendiente de recibir. Los adjuntos de los costos son opcionales.
- La entrega descuenta al confirmar, agotando cantidad y valor sin residuo.
- La nueva recepción usa su propio costo cuando ya no queda existencia anterior.
  Las tres entradas anteriores conservan íntegros sus datos históricos.
- La conciliación final muestra físico 4, valorado 4, diferencia 0 y valor 100.
- PDF y XLSX se generan desde la consulta valorada. El Excel conserva el primer
  promedio 10 y el último 25, además de las tres salidas de unidades logísticas.
- El operador consulta los movimientos físicos de su bodega; la valoración por
  API responde 403. Consultar o exportar no agrega ni modifica asientos.

Implementación de la aceptación:
`backend/tests/e2e/test_inventory_final_acceptance.py`.

## Continuidad y cobertura complementaria

| Caso | Cobertura ejecutada |
|---|---|
| Preparación parcial 50 → 30 + 20 | Capacidad, códigos incorrectos, medidas/etiquetas obligatorias, reintentos, rollback y conservación exacta de valor |
| Etiquetas | Identidad y fecha de recepción, producto archivado, permisos e impresión sin movimiento de stock |
| Apertura individual | 80 × 6.80 = 544, producto sin historia, idempotencia/concurrencia, restricción por bodega y rechazo de nueva apertura tras agotar un producto con historia |
| Inventario/reubicación | Existencia por ubicación, motivo obligatorio, saldo conservado y alcance de bodega |
| Traslados | Despachos concurrentes sobre una unidad, recepción desde destino con alcance limitado, otra empresa, tránsito, recepción parcial, incidentes y rollback |
| Entregas y devoluciones | Venta sin salida, unidades completas y equivalencias congeladas, costo aplicado, concurrencia, cancelación, rollback, devolución al costo de la entrega original y controles de cantidad |
| Ajustes | Aplicación al promedio vigente, corrección documentada, pérdida en tránsito, rollback, idempotencia y autorización de comprobantes |
| Kardex y reportes | Filtros y totales coherentes, cortes históricos, seis exportaciones físico/valorado/conciliación, protección financiera y bodegas no asignadas |
| Retaceo manual | Campos explícitos, cero válido, factura protegida, gastos reales y presupuesto separados, cierre de gastos, documentos opcionales y reparto válido |

La prueba antigua de entregas preparaba sus existencias mediante el endpoint
genérico de recepción. Ese endpoint ahora exige el documento de compra y rechaza
el atajo con `purchase_receipt_document_required`. Se actualizó **solo el fixture
de esa prueba** para preparar su stock mediante el servicio interno; los pasos de
venta, entrega y devolución siguen pasando por la API. El nuevo caso integrado
anterior cubre el recorrido público completo de compras. No se debilitó la
protección del endpoint de producción.

Al añadir la comprobación de recepción parcial se corrigió también una suposición
del test: una orden totalmente recibida no permite consultar `/receivable` para
seguir recibiendo. El test consulta esa ruta solo si queda pendiente y comprueba
el estado `received` en el caso completo. No fue necesario cambiar lógica productiva.

## Pruebas y evidencia

Resultado final de las selecciones ejecutadas: **146 pruebas aprobadas distintas**:
79 backend (68 lógica/integración y 11 E2E) y 67 frontend. No es un conteo de toda
la suite del ERP. La selección E2E se cerró en dos ejecuciones: 10 regresiones
aprobadas en la ronda conjunta y el nuevo caso final aprobado tras corregir la
suposición del test descrita arriba. El log conjunto conserva ese fallo anterior
para no ocultar el diagnóstico; `final-flow.log` contiene su verificación posterior.

- Evidencia local: `tmp/block6-acceptance/`: `regression-e2e.log`, `final-flow.log`,
  `integration-unit.log`, `frontend.log`, `svelte-check.log` y `results.json`.
- Ruff sobre los dos archivos de pruebas modificados: sin errores; formato válido.
- `pnpm check`: 0 errores y 8 avisos CSS `@apply` ya existentes en
  `TransferOperationsPage.svelte`. Vitest emite avisos `derived_inert` en las
  pruebas de etiquetas; las seis pruebas de ese archivo aprueban.
- Esquema de desarrollo: Alembic `0097 (head)`. Este bloque no añade migración.

Selección de E2E (base reiniciada por cada caso):

```text
uv run pytest tests/e2e/test_inventory_preparation.py
  tests/e2e/test_inventory_labels_retaceo_workflow.py
  tests/e2e/test_inventory_workspace.py tests/e2e/test_inventory_transfers.py
  tests/e2e/test_sales_deliveries.py tests/e2e/test_inventory_adjustment_permissions.py
  tests/e2e/test_kardex_statements.py tests/e2e/test_inventory_final_acceptance.py -q
```

Selección de lógica/integración:

```text
uv run pytest tests/integration/test_inventory_adjustment_repository.py
  tests/integration/test_inventory_transfer_repository.py
  tests/integration/test_inventory_valuation_repository.py
  tests/integration/test_kardex_reconciliation_cut.py
  tests/unit/test_retaceo_manual_entry.py tests/unit/test_retaceo_valuation.py
  tests/unit/test_inventory_valuation.py tests/unit/test_inventory_preparation.py
  tests/unit/test_kardex_reports.py -q
```

Frontend: RetaceoManualWorkflow, RetaceoManualCreate, InventoryLabelDialog,
WarehousePreparationQueue, WarehouseMovementsPanel, InventoryConsultation,
InventoryKardexPage, KardexLists, KardexReconciliationControls y ReportDownloads.

No se ejecutan dos suites de base de datos simultáneamente: comparten
`erp_db_test` y reconstruyen su esquema. Durante la sesión Docker estaba apagado;
se levantó de nuevo y se recuperaron los logs de los contenedores antes de seguir.

## Qué queda preparado para Rodrigo

[Guion de exposición](guion-exposicion-corto-grupo-lorena.md): recorrido con seis
pasos, nombres de pestañas, diferencia entre recepción documental y operación de
bodega, ejemplo de promedio y respuestas a las preguntas del ingeniero.

La aceptación anterior es automatizada con API y base reales de pruebas; no es
una grabación completa de clics del ejemplo en la base de demostración. Los
recorridos visuales previos de los bloques 2–5 siguen documentados en sus informes.
Antes de exponer, Rodrigo elige su producto y documentos reales, comprueba ambas
cuentas y ensaya el guion. No se han creado compras de prueba en `erp_db` ni borrado
sus pendientes antiguos para hacer una pantalla artificialmente limpia.

## Límites conservados

- La regularización histórica de COM-00024 sigue separada: descuento confirmado
  5% = 100 y FOB neto 1900; no se aplicaron cargos de importación supuestos ni se
  reescribió su costo histórico. Su ejecución real requiere los importes documentados
  que faltan, conforme al informe del bloque 1.
- Al cerrar este bloque, C03/C04/A01 permanecían posteriores. Después Rodrigo
  autorizó exclusivamente la matriz visual de proveedores, implementada sin
  recomendación automática; véase [matriz manual](matriz-proveedores-manual-2026-10-29.md).
  La devolución ampliada de Gerencia y el abastecimiento por mínimos siguen
  posteriores; la continuidad de los traslados existentes sí fue probada.
- Un saldo legado sin vínculo a recepción se conserva identificado como tal. No
  se le inventa proveedor, lote o compra. El ejemplo nuevo tiene su propia trazabilidad.
- Los PDF/XLSX son reportes internos. No se afirma compatibilidad certificada con
  una plantilla fiscal oficial que no se haya identificado y validado.

Con estas evidencias queda cerrado el bloque 6 del tramo acordado; las mejoras
posteriores y la regularización histórica permanecen explícitas en el plan maestro.
