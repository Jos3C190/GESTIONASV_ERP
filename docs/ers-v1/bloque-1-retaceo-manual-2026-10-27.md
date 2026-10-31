# Bloque 1: retaceo manual y gastos reales

Fecha local: 27/10/2026. Alcance: recepción documental, captura de costos y
proyección del promedio. Forma parte del plan maestro de seis bloques.

## Resultado implementado

- Todo retaceo nuevo comienza con FOB por línea, flete, DAI e IVA vacíos en la
  interfaz. El operador captura los importes de los documentos. Omitido y cero
  son estados distintos: flete/DAI/IVA exigen entrada explícita, incluido 0.
- Flete y DAI son componentes propios y se distribuyen según FOB. Los otros
  gastos son opcionales, pero cada uno requiere categoría, fecha, descripción,
  monto y distribución para calcular. Los comprobantes adjuntos son opcionales,
  según la aclaración de Rodrigo del 27/10/2026. El IVA queda fuera del costo.
- Los gastos previstos sirven para comparar; no se extraen ni se convierten en
  cargos reales automáticamente. La bitácora de gastos reales se encuentra en
  el detalle de la orden, después de la recepción/seguimiento. Se puede usar desde
  aprobación, durante la espera o con recepciones parciales, hasta que se cierre
  un retaceo de la misma orden. Desde ese cierre se bloquean nuevas altas en la
  bitácora compartida de la orden, también para sus otras recepciones parciales.
- Los reales no cambian el presupuesto aprobado. Se pueden vincular explícitamente
  al desglose del retaceo; se comprueba el saldo no asignado entre recepciones.
  Seleccionar la referencia no rellena importes financieros.
- La factura y fecha confirmadas se muestran de solo lectura. País y póliza
  conservan sus campos propios. Se aclaró que el descuento de oferta se captura
  como importe monetario total para evitar confundirlo con un porcentaje.
- Comparación de promedio global por empresa: entrada futura frente a saldo actual;
  para una recepción antigua ya registrada, ajuste de valor con 0 unidades nuevas.
  La simulación incluye el efecto de salidas/devoluciones posteriores.
- FOB histórico diferente: exige motivo documentado y aplicación separada; conserva
  compra/asientos originales. El caso COM-00024 quedó explicado en su documento
  específico, con FOB 1900 confirmado y sin cargos reales inventados.

## Recorrido para utilizarlo

1. En una orden aprobada/enviada, abrir **Bitácora de otros gastos reales**.
   Registrar cada gasto conocido; adjuntar su comprobante es opcional.
2. Registrar y confirmar la recepción documental; mantener el conteo parcial,
   aceptado/rechazado y los pendientes del flujo existente.
3. Desde la compra abrir **Crear retaceo**. Capturar FOB total por producto,
   flete, DAI e IVA. Los valores no se importan de la orden ni de su presupuesto.
4. En **Costos y comprobantes**, agregar otros gastos, relacionar la bitácora si
   corresponde y capturar sus valores. Distribuirlos entre productos o usar la
   acción explícita **Distribuir según FOB**, que calcula solamente el reparto.
5. Guardar borrador, adjuntar comprobantes si se desea, revisar/calcular y verificar.
   Guardar no publica inventario ni equivale a aprobar el cálculo.
6. Revisar el costo por producto y la comparación del promedio. Cerrar con las
   condiciones del flujo correspondiente. Etiquetado y colocación se trabajan
   en los siguientes bloques; no se dan por terminados aquí.

## Persistencia, seguridad y compatibilidad

- Migración **0095 aplicada**. Copia previa en
  `tmp/ers-v1/bloque-1-2026-10-27/before.dump`. Downgrade protegido si los nuevos
  registros ya están en uso.
- Nuevas rutas bajo RBAC y alcance de empresa/sucursal/bodega; registro de gastos
  reales con auditoría obligatoria. El acceso al promedio mantiene permiso de
  valoración y alcance de empresa.
- Un retaceo manual activo por compra. Validación monetaria decimal y reparto
  exacto a seis decimales. Bloqueo de la orden evita asignaciones concurrentes
  que excedan un gasto real. Los comprobantes conservan archivo original.
- No se migraron ni sobrescribieron importes comerciales, stock o asientos
  históricos. COM-00023, RET-00018 y COM-00025 no se alteraron.

## Evidencia de validación

- Backend: **71 pruebas** del retaceo, gastos, conversión, aplicación idempotente y
  corrección histórica. Frontend: **17 pruebas** de captura vacía, cero explícito, payload manual,
  categorías, reintentos sin pérdida, bitácora y comparación sin duplicar stock.
- Ruff y ESLint de los archivos del bloque sin incidencias. Svelte-check: 0 errores;
  8 avisos previos de `@apply` en TransferOperationsPage, fuera de este cambio.
- Prueba transaccional de persistencia: presupuesto intacto, fuentes y fechas
  conservadas, reserva compartida y liberación al cancelar; rollback comprobado.
- Simulación real de almacenamiento de COM-00024: proyección y aplicación coinciden,
  cantidad sin cambio, historial intacto e idempotencia; rollback comprobado.
- Vistas de componentes con datos de prueba: escritorio 1280 px, tablet 768 px y
  móvil 375 px, claro/oscuro. Se generaron desde DOM real de pruebas y estilos
  del proyecto. No se presentan como sesión autenticada ni como ingreso comercial
  completado. La validación funcional utiliza Vitest y los casos de uso/backend.

## Límites y trabajo restante

- Corrección del 27/10: el cierre del retaceo bloquea nuevas altas de gastos reales
  tanto en API como en pantalla. Un formulario abierto antes del cierre también
  será rechazado por el servidor; el cierre y el alta comparten bloqueo de orden.
- Consulta de OC-00026: RET-00021 está cerrado en USD 37 (FOB 13 + flete 12 + DAI 12).
  La bitácora conserva USD 33 con referencia `333` y USD 15 con referencia `skiu`,
  ambos sin asignación. No se borraron ni incorporaron al retaceo cerrado. La
  pantalla muestra sus importes pendientes de revisión para evitar confundirlos
  con costos aplicados. Los archivos adjuntos continúan siendo opcionales.
- Validación de esta corrección: 43 pruebas unitarias de backend y 20 de frontend
  correctas. La prueba nueva de repositorio comprueba estados, empresa y orden en
  PostgreSQL. En la ejecución ampliada pasaron otras ocho pruebas de repositorio;
  dos pruebas anteriores de bodega central sin sucursal fallan ante la regla
  vigente que exige matriz activa. No se cambió esa regla ni esas pruebas ajenas
  al bloqueo de gastos. Ruff/ESLint correctos; Svelte-check sin errores y con los
  mismos ocho avisos previos de `@apply`.
- Comprobación real de solo lectura: OC-00026 devuelve `can_record=false` y
  RET-00021 como motivo del bloqueo. El endpoint está registrado en el servidor
  activo y `/health/live` responde 200. No se modificaron datos de esa orden.

- El FOB de COM-00024 ya está confirmado y el camino de regularización está
  implementado/probado. Su retaceo real **no está aplicado**: aún corresponde
  capturar flete/DAI/IVA reales; adjuntar archivos es opcional.
- La bitácora es de altas documentadas; no se añadió edición retroactiva de gastos
  ya registrados. Su relación con un retaceo se elige antes de guardar ese gasto;
  para cambiar la referencia se quita y vuelve a agregar en el borrador.
- Este bloque no cambió el momento de alta final del stock ni la vista del
  bodeguero. El flujo completo ubicación → ingreso se cerrará en el bloque 3.
- Etiquetas/lotes (2), bodeguero/ubicación (3), inventario (4), Kardex/reportes (5)
  y aceptación/demostración completa (6) siguen en el plan.

## Revisión visual independiente

Se hicieron tres rondas con jueces de solo lectura y contexto independiente.
Puntuaciones medias: **8.18**, **8.33** y **8.06**; el umbral del skill es 8.5 y
ningún rubro menor que 7. **No se obtuvo aprobación visual final.**

| Rubro | Última nota | Evidencia del juez |
| --- | ---: | --- |
| Distinción | 8.0 | Resumen monetario y desglose apropiados; paneles uniformes |
| Tipografía/contenido | 8.5 | Jerarquía e importes legibles; IVA y regularización explicados |
| Layout/responsive | 8.0 | Grillas adaptadas; formularios aún largos en móvil |
| Interacción | 8.5 | Acordeones, foco al error y movimiento reducido |
| Consistencia | 8.5 | Tokens y controles comunes en claro/oscuro |
| Accesibilidad | 8.5 | Labels, errores asociados, alertas y contraste; teclado completo sin acreditar |
| Código | 8.0 | Componentes especializados; edición fija requería preservar documentos |
| Estados/límites | 6.5 | El juez encontró pérdida de identidad del gasto al editar 10→0→12 |

Tras la tercera ronda se corrigió ese hallazgo funcional: un cero transitorio ya
no elimina el objeto del gasto ni sus documentos. La exclusión de un componente
con cero definitivo ocurre al guardar, conservando su historial en el servidor.
Dos pruebas nuevas cubren **10→0→12** y **10→0→0.5** con un comprobante existente
y comprueban que el payload mantiene su ID. No se inventa una nueva puntuación
después de esa corrección. El pulido restante consiste en reducir longitud y
paneles, especialmente en móvil; la aprobación visual queda pendiente.

Las rondas también corrigieron asociación accesible de errores, factura de solo
lectura visible, borde de Notas, copy del reparto, ayudas plegables, resumen
monetario al inicio y presentación compacta del flete con prioridad al comprobante.
