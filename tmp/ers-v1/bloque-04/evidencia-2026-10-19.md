# Evidencia técnica ERS-B04

**Fecha:** 19/10/2026  
**Alcance:** operación visible de traslados B04 sobre el contrato B03 (base de partida Alembic 0086).  
**Entorno de datos:** pruebas PostgreSQL en `erp_db_test`; no se alteró la base demo. No se añadió migración.

## Resultados ejecutados

### Frontend

Los comandos se ejecutaron desde `C:\Developer\GESTIONASV_ERP\frontend` con las dependencias locales ya instaladas:

```text
node .\node_modules\vitest\vitest.mjs run src/lib/features/inventory/transfer-operations.test.ts src/lib/features/inventory/transfer-documents.test.ts src/lib/features/inventory/components/HandlingUnitsPanel.test.ts

Test Files  3 passed (3)
Tests       39 passed (39)
```

```text
node .\node_modules\eslint\bin\eslint.js src/lib/features/inventory/components/TransferOperationsPage.svelte src/lib/features/inventory/components/TransferDemandOverview.svelte src/lib/features/inventory/components/TransferDocumentList.svelte src/lib/features/inventory/components/TransferVehicleCatalog.svelte src/lib/features/inventory/components/TransferLifecycleProgress.svelte src/lib/features/inventory/components/HandlingUnitsPanel.svelte "src/routes/(app)/transfers/+page.svelte"

Resultado: sin errores de ESLint.
```

```text
node .\node_modules\svelte-check\bin\svelte-check --tsconfig .\tsconfig.json

Resultado: 0 errores y 8 avisos de regla CSS desconocida @apply en TransferOperationsPage.svelte.
```

Los avisos son de `svelte-check` al analizar las directivas `@apply`; Vite procesa la hoja y el build final se aprobó.

```text
node .\node_modules\vite\bin\vite.js build

Resultado: build de cliente y SSR terminado con código de salida 0.
Avisos: import default de jsbarcode sin uso en HandlingUnitLabelDialog.svelte (preexistente) y adapter-auto sin destino de despliegue detectado.
```

### Backend

```text
docker compose exec -T backend pytest tests/integration/test_inventory_transfer_repository.py -q

Resultado: 6 passed in 19.52s.
```

La integración focalizada incluye documento/despacho/recepción parcial y replay idempotente, incidencia que conserva inventario no resuelto, límite de asignación de demanda, avance de demanda sin doble conteo, rechazo del puente genérico de traslados y rollback de fallos parciales.

El primer intento de esa suite falló porque el fixture de la ubicación destino no construía la jerarquía física completa requerida por el contrato. Se corrigió el fixture para crear pasillo, rack, nivel y posición válidos, y se repitió la suite completa: el resultado final fue 6/6. El fallo fue del montaje de datos de prueba, no de la base demo.

```text
docker compose exec -T backend ruff check app/api/v1/routers/inventory.py app/infrastructure/repositories/inventory_transfer_repository.py tests/integration/test_inventory_transfer_repository.py

Resultado: All checks passed.
```

## Revisión UI de código

El crítico de UI hizo una revisión estática de los componentes; no operó el navegador ni una sesión autenticada. La evaluación inicial fue 7.75/10 y se consideró insuficiente. Se añadieron un indicador de ciclo del traslado, estado de avance accesible y porcentaje asignado, además de mensajes de procesamiento con soporte para movimiento reducido. Tras esos cambios el crítico calificó la interfaz **8.5/10, aprobada**, sin defectos bloqueantes observados. La aceptación visual integrada sigue pendiente para B08.

## Límites de esta evidencia

- No se ejecutó un recorrido manual autenticado de principio a fin en el navegador. Los casos de perfiles, teclado, persistencia tras recarga, móvil y temas quedan para B08.
- Las pruebas previas de B03 se referencian como antecedentes en su entrega; este informe no las vuelve a contar como ejecuciones B04.
- No se probó lector físico HS200 ni impresora; no son requisitos de la demostración.
- No se ejecutó una semilla ni se modificaron datos de la demo.
- La aceptación del bloque no extiende su alcance a B05: el bloque siguiente no se inició.
