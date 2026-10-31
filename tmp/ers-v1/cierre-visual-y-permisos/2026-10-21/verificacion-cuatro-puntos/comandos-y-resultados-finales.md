# Comandos y resultados — verificación final 21/10/2026

Todos los accesos SQL de esta verificación usaron transacción PostgreSQL `READ ONLY`. El script `readonly-final-reconciliation.py` valida primero que `DATABASE_URL_SYNC` apunte a `erp_db_ers_final4p_20261020`; deriva la conexión a `erp_db` solo para la consulta de los cuatro SKU protegidos. Se copió temporalmente a `/app/tmp/ers-final-four-point-reconciliation.py` dentro del contenedor `erp-final4p-api`, se ejecutó y se retiró esa copia temporal. El código fuente del helper permanece en esta carpeta.

| Acción | Comando/operación | Resultado |
| --- | --- | --- |
| Reconciliar clon y demo | `docker exec erp-final4p-api python /app/tmp/ers-final-four-point-reconciliation.py` (tras copia temporal del helper) | Exit 0; ambas bases reportan 4/4/USD40, 5/5/USD60, 12/12/USD160, 0/0/USD0. Salida íntegra: `reconciliation-final.log`. |
| Leer historial anterior/posterior de V04 | `docker exec erp-final4p-api python /app/tmp/ers-final-four-point-transaction-history.py` (con helper que valida el DSN del clon y ejecuta `SET TRANSACTION READ ONLY`) | Exit 0; balances de valoración previos, salidas/entradas de ajuste, despacho/recepciones de traslado y entregas/devolución. Salida: `transaction-history-v04.log`. La copia temporal se retiró del contenedor. |
| Restaurar CORS RustFS del clon | `docker exec -e OBJECT_STORAGE_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173 erp-final4p-api python -m app.infrastructure.storage_bootstrap` | Exit 0; CORS de bucket restaurado. |
| Verificar CORS | `docker exec -e OBJECT_STORAGE_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173 erp-final4p-api python -c "from app.core.config import settings; from app.infrastructure.object_storage import S3ObjectStorage; client=S3ObjectStorage(settings)._client(settings.OBJECT_STORAGE_INTERNAL_ENDPOINT); rules=client.get_bucket_cors(Bucket=settings.OBJECT_STORAGE_BUCKET)['CORSRules']; print([(r.get('AllowedOrigins'),r.get('AllowedMethods')) for r in rules])"` | `[['http://localhost:5173','http://127.0.0.1:5173'], ['PUT','GET','HEAD']]`; no `5174`. |
| Comprobar listeners del proxy | `Get-NetTCPConnection -State Listen -LocalPort 5174,8002` | 5174 sigue escuchando; no hay listener 8002. No se ejecutó el proxy postcommit. |
| CUA / V03 | Navegador autenticado 5174: QR de `HU-8FEE57267CC84449`; vista pública `/inventory/trace`; abrir y cancelar división de `HU-8D63FE508BF14124`; recargar/consultar UI y SQL. | Se registró en `v03-ui-trace-qr-division-cancel-2026-10-21.md`; ninguna división se confirmó. QR agregó una capability al clon. |
| CUA / V04 | Formularios de ajuste, traslado, venta/entrega y devolución en 5174; consultas SQL de persistencia posteriores. | Se registró en `v04-ui-operations-2026-10-21.md`; V04-01/02/03 aprobados. |

## Acciones no ejecutadas

- La petición de detener/reiniciar el Vite aislado para rerutear API al proxy fue bloqueada antes de ejecutar el comando. No se tocó el servicio habitual. Por ello V04-04 queda abierto.
- No se generaron PNG: la API CUA documentada permite observar la captura, no escribirla en el directorio de evidencia. V02 queda abierto.
- No se repitieron suites completas. No hubo cambios a código de aplicación en esta pasada; los cambios son evidencia/documentación.
