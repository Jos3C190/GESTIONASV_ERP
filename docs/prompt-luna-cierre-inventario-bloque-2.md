# Prompt para Luna: completar la integración del bloque 2

Copia el texto siguiente como encargo para Luna.

---

Continúa en `C:\Developer\GESTIONASV_ERP`. El usuario ya autorizó implementar la política de inventario y valoración. Tu objetivo es **completar y corregir el bloque 2 existente —lotes, etiquetas y ubicación agrupada— y validar su integración con el núcleo de valoración del bloque 1**. Entrega cambios funcionales y evidencia; no termines solo con un plan o una actualización documental.

Primero lee estos archivos y las instrucciones aplicables del repositorio:

- `C:\Developer\GESTIONASV_ERP\docs\inventario-valoracion-bloque-1.md`
- `C:\Developer\GESTIONASV_ERP\docs\inventario-bloque-2-lotes-etiquetas-colocacion.md`
- `C:\Developer\GESTIONASV_ERP\docs\revision-inventario-bloques-1-2-2026-10-14.md`
- `C:\Developer\GESTIONASV_ERP\.agents\skills\feature-development\SKILL.md`

El árbol tiene muchos cambios previos y archivos sin seguimiento: consérvalos. No reviertas trabajo ajeno ni reescribas módulos completos. Si modificas interfaz, aplica las instrucciones de calidad frontend del proyecto y reutiliza los componentes existentes.

## Estado de partida

El bloque 1 ya contiene promedio por empresa/artículo, apertura documentada, recepción con costo provisional, retaceo aplicado una vez, historial inmutable y reglas de devoluciones. Todavía no tiene aceptación integrada sobre PostgreSQL.

También existen lotes, ubicación agrupada, etiquetas 1D/QR y enlaces públicos revocables del bloque 2. Las migraciones llegan a `0082`; no empieces esas funcionalidades desde cero. El frontend pasó 406 pruebas y `svelte-check`, pero eso no valida backend ni base de datos. Las 51 pruebas backend citadas en el documento 1 son un resultado anterior; comprueba el estado actual.

## Trabajo prioritario

1. **Corregir las incompatibilidades detectadas.** Confirma los hallazgos H1–H4 del informe y corrígelos con pruebas de regresión:
   - Etiquetas/QR: distinguir recepciones anteriores al corte de las nuevas valoradas. Un retaceo antiguo finalizado puede no tener `applied_at`. Los intentos cancelados no deben bloquear una versión vigente. Mantén la exigencia de costo aplicado donde corresponda y no inventes aplicaciones históricas.
   - Cantidad agrupada: usar todos los detalles aceptados del mismo producto y lote. Dos líneas de 20 y 30 deben permitir distribuir 50 conservando su origen; 51 debe rechazarse.
   - Concurrencia: unificar el orden de bloqueos de empresa, ámbitos físicos y unidades entre ubicación agrupada, movimientos y verificación de medidas. Actualmente el grupo bloquea la unidad antes de pedir los bloqueos usados por el movimiento. Corrige la causa y prueba concurrencia real; no la ocultes con reintentos.
   - Permisos: permitir que el operador autorizado imprima y gestione el QR de su propia bodega, sin darle acceso a otras sucursales. Mantén el alcance de toda la empresa para valoración global.

2. **Completar la confirmación de viñeteado (H5).** El flujo autorizado es recepción verificada → retaceo requerido aplicado → etiquetas de las unidades físicas → confirmación de viñeteado y ubicación válida → disponible.
   - Registrar la solicitud de impresión o abrir `window.print()` no demuestra que se imprimió o colocó una etiqueta. Conserva ese historial y añade una confirmación explícita, idempotente y auditada por unidad/etiqueta vigente.
   - Valida la confirmación en backend al liberar las recepciones sujetas a este flujo, tanto por grupo como por liberación individual. Puedes permitir ubicación previa manteniendo cuarentena; no debe aparecer como disponible antes de cumplir los requisitos.
   - Distingue copias/reimpresiones de unidades físicas nuevas. Muestra presentación y equivalencia base cuando corresponda: una caja de 12 equivale a 12 unidades base. No multipliques existencias por imprimir varias copias.
   - Define el tratamiento de fraccionamientos: conservar origen y cantidad; la unidad hija debe tener su identificación y confirmación pertinente. No heredar una confirmación que ya no representa la unidad física.
   - No inventes confirmaciones históricas ni cambies cantidades reales para cumplir la nueva regla. Si hace falta esquema, crea una nueva revisión según las cabezas reales de Alembic, sin modificar a ciegas migraciones ya utilizadas.

3. **Preparar validación reproducible.** El backend requiere Python `>=3.12,<3.13`. Usa un entorno aislado y las dependencias del proyecto/`uv.lock`; la falta de `pytest` en el Python global no basta para declarar agotadas las opciones. Inspecciona las herramientas disponibles y configura un entorno compatible si es posible.
   - Usa PostgreSQL desechable con datos ficticios. Verifica la conexión de destino antes de migrar o sembrar. No uses la base operativa para las pruebas ni apruebes un saldo inicial real.
   - Comprueba `alembic current` y `alembic heads`. El destino `0079` prueba el bloque 1; `head` actualmente incorpora `0080`–`0082` y podría incluir tu nueva revisión. Explica qué destino probaste.
   - Si el entorno impide una prueba, deja el comando, error concreto y trabajo completado; continúa las comprobaciones independientes. No presentes ese caso como aprobado.

## Reglas que deben conservarse

- Promedio compartido entre almacenes de una empresa y separado entre empresas/artículos. Los traslados internos conservan cantidad y valor total.
- Recepción aceptada valorada aun en cuarentena; rechazos no ingresan como disponibles.
- Calcular retaceo es vista previa. Verificar autoriza aplicar; aplicar es idempotente; cerrar bloquea cambios. El ajuste tardío se reparte entre remanente y salidas afectadas sin editar eventos originales.
- Devolución de cliente vinculada a la salida original. Devolución a proveedor al promedio, crédito y diferencia separados. Mantén aritmética decimal exacta.
- QR público limitado a la unidad, revocable, sin sesión y sin exponer operadores, permisos ni inventario ajeno. Conserva el botón para abrir ficha en pestaña nueva. No prometas que un lector USB tipo teclado abre pestañas por sí solo ni que `localhost` funciona desde otro dispositivo.

## Criterios de aceptación

- Ejemplo de costos: recibir 10 a $10 y 10 a $20, vender 15 y devolver 5 al proveedor con crédito de $100 debe terminar en cantidad 0 y valor 0, salida a proveedor de $75 y diferencia de $25.
- Retaceo tardío: entrada de 10 por $100, salida de 6 y costo adicional de $20 produce ajuste de $8 al remanente y $12 a las salidas; repetir la aplicación no duplica nada.
- Probar el recorrido con dos bodegas de la misma empresa y otra empresa; comprobar permisos por sucursal, cuarentena, traslados, fracciones, rollback e idempotencia con contenido igual y diferente.
- Cubrir H1–H5, incluyendo impresión cancelada, ausencia de confirmación, reimpresión y confirmación repetida. No asumir éxito físico por el evento `afterprint`.
- Ejecutar primero las pruebas afectadas, después las regresiones pertinentes, `svelte-check` y build cuando haya cambios frontend. Prueba las transacciones importantes sobre PostgreSQL; los mocks no sustituyen esa evidencia.

Mantén el alcance acotado: libro mayor, períodos contables, conversión de moneda, deterioro, captura avanzada del corte y todas las pantallas de devoluciones pertenecen a futuros bloques. No los implementes en este encargo.

Actualiza los documentos de los bloques 1 y 2 con el estado real, comandos/resultados y pendientes. Termina explicando qué quedó corregido, dónde usarlo, qué pruebas ejecutaste y qué falta por entorno o equipo físico. No marques el bloque como aceptado operativamente mientras falten esas comprobaciones.
