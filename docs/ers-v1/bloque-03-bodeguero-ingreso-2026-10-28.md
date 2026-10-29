# Bloque 3 — Bodeguero, colocación e ingreso

Estado: implementado y verificado para el bloque 3. Fecha local: 28/10/2026.

## Decisiones y plan

- Reutilizar /inventory, cuenta Rodrigo y permisos/asignaciones de bodega ya
  existentes. Nueva cola operativa de preparación/etiquetado/ubicación, sin costos.
- Versionar compras nuevas con `placement_before_inventory`. Las compras con
  lote o movimiento conservan sus versiones e historial; no se recalcula el pasado.
  Una recepción previa de `retaceo_before_inventory`, aún recibida y sin lote ni
  movimiento, se continúa con la nueva secuencia. La migración no transforma
  automáticamente las recepciones del flujo legado anterior a esa versión.
- La verificación del flujo nuevo crea lote, detalles y unidades en preparación,
  sin saldo ni movimiento físico/valorado. Cada detalle congela el costo aceptado
  y moneda del retaceo cerrado. Las etiquetas usan esa identidad persistida.
- Añadir `inventory_posted_at` a la unidad logística. Las unidades existentes se
  marcan ingresadas; las de preparación quedan con NULL. Consultas de existencias
  y movimientos generales excluyen/rechazan las unidades sin ingreso.
- Verificar medidas y confirmar etiqueta en preparación. Al colocar una unidad
  completa, conservar su código e ingresar cantidad y valor en una transacción.
  Repartir costo proporcionalmente con remanente exacto al último ingreso.
- Dividir una unidad pendiente crea una porción y un remanente identificables,
  sin existencias ni movimientos. Invalida medidas/etiqueta del remanente y exige
  revisión de ambas unidades antes de ingresar. Permite repartir 50 en 30 y 20.
- Escaneo autenticado: unidad/lote/producto dentro de una selección explícita,
  destino por código de ubicación dentro de la bodega autorizada. La confirmación
  vuelve a verificar estado, etiqueta, medidas, capacidad, retaceo y cantidades.
- Idempotencia persistida para dividir y colocar; mutex de valoración por empresa,
  bloqueo de unidades/detalle y auditoría obligatoria. Reintentos no duplican stock.

## Aceptación prevista

1. Nueva recepción: cero cantidad/valor antes de colocar, etiquetas habilitadas
   solo con retaceo cerrado; valores anteriores intactos.
2. Medición/etiqueta pendientes, ubicación de otra bodega, capacidad insuficiente,
   vencimiento, cantidad excesiva, empresa/permisos incorrectos: rechazo atómico.
3. Preparar 50 → 30 + 20, revisar ambas porciones y confirmar en dos espacios;
   cantidad y valor exactos, promedio vigente e historial coherentes.
4. Reintentar/dividir/colocar doble vez no duplica; cambiar contenido con la misma
   clave se rechaza. Reimpresión conserva identidad y fecha de recepción.
5. Rodrigo usa vista móvil sin costos en API/pantalla; administrador puede revisar
   el mismo flujo. Evidencias de navegador y pruebas se incorporarán al cierre.

## Diseño y recorrido implementados

Se reutiliza `/inventory` y el acceso operativo de Rodrigo Molina; no se creó
otra cuenta ni se cambiaron contraseñas. El diseño usa los tokens existentes,
tareas separadas (Recepciones / Preparar y ubicar / Existencias), controles de
44 px y cola paginada. En móvil/tablet, seleccionar una unidad reemplaza la
lista por su tarea y ofrece volver a pendientes. En escritorio conviven cola
y detalle. La API operativa no devuelve importes ni costos.

La cola presenta fases de medidas, etiqueta y ubicación. El lector de teclado
puede avanzar con Enter sin confirmar automáticamente. Se acepta el código HU,
producto, lote o un enlace QR vigente de la unidad seleccionada; el destino es
el código de una ubicación de la bodega autorizada. Se conservan la identidad,
fecha de recepción, origen y confirmación de etiqueta al ingresar una unidad.

Guion para probar con el ingeniero:

1. Confirmar la recepción documental y cerrar el retaceo manual.
2. Verificar las cantidades aceptadas en un área de recepción. El botón ahora
   prepara unidades: todavía no aumenta existencia ni valor.
3. Entrar con Rodrigo a Inventario y elegir Preparar y ubicar. Abrir una unidad,
   revisar su peso/volumen y confirmar que se imprimió y colocó su etiqueta.
4. Escanear su código, la ubicación del estante y confirmar la cantidad completa.
   La confirmación registra cantidad y valor juntos y deja la unidad disponible.
5. Si deben ir 30 de 50 a un espacio y 20 a otro, preparar primero la porción de
   30. Revisar medidas y etiquetas de ambas partes y ubicar cada unidad completa.
6. Consultar Existencias y el Kardex del administrador: cada colocación produce
   su entrada, valor y promedio vigente. Reintentar la misma petición conserva el
   mismo resultado; no duplica ingresos. Las líneas históricas no se reescriben.

## Verificación técnica

- 128 pruebas backend aprobadas: 115 de preparación, etiquetas, compras,
  retaceo manual y capacidad, más 13 de contratos de lotes/ubicación. Resultados
  adicionales en `tmp/block3-lot-unit.log`.
- Tres escenarios E2E con PostgreSQL aprobados: preparación/ubicación y etiquetas
  con producto activo o eliminado. La última repetición de colocación también
  verifica que el lote sin ingreso no aparece entre existencias.
- El escenario de colocación usa un bodeguero sin privilegios de administrador,
  restringido a una bodega. Verifica denegación de valoración/otra empresa/bodega,
  error de lectura, medidas/etiqueta pendientes, capacidad insuficiente y rechazo
  atómico. División 50 → 30 + 20: dos movimientos, cantidad 50 y valor 108.123457,
  con remanente exacto. Los reintentos y cambios de contenido con una clave usada
  se comprueban contra datos persistidos.
- 37 pruebas frontend aprobadas, incluyendo 19 de cantidad/cola operativa,
  navegación de Enter por fase, validaciones, reintento con la misma clave y
  descarte de respuestas del contexto anterior.
- Svelte check: cero errores; ocho advertencias CSS `@apply` preexistentes en
  TransferOperationsPage. ESLint de los archivos nuevos/operativos y Ruff pasan.
- Edge: 375, 768 y 1280 px, claro/oscuro, carga/vacío/error/reintento/éxito,
  porción y error de medidas, sin desbordamiento ni errores JavaScript. Contraste
  de placeholders: 4.67:1 claro y 7.37:1 oscuro.

Evidencias de UI con fixtures, script reproducible y resultados en
`tmp/ers-v1/bodeguero-bloque3-2026-10-28/`. La ruta temporal de QA fue retirada.
Los datos de demostración se ejecutaron en la base aislada `erp_db_test`; no
se colocaron unidades ni se hicieron impresiones en la base de trabajo.

## Migración y conservación de datos

Se aplicó 0096 en la base de trabajo después de guardar una copia de seguridad
en esa carpeta. Huella SHA-256 de la copia:
`512c7d94d3c930aea706107f7ff623eeeea176dc8a7cb303be2879f55edcf611`.
Los snapshots anterior/posterior coinciden: 58 saldos, cantidad 6379.682800;
142 movimientos; 35 eventos de valoración con suma 51742.038666; 49 unidades
logísticas. El ingreso anterior se marcó con su fecha existente. Se actualizó
la versión de una recepción pendiente sin lote ni movimiento. Backend y
frontend se reiniciaron para cargar la actualización.

La primera colocación enlaza el retaceo aplicado y las siguientes conservan
esa referencia en cada evento de valoración. La comparación del retaceo
describe el ingreso ya registrado cuando existe aplicación parcial; el
Kardex muestra las colocaciones por separado. La revisión completa de reportes
y conciliación corresponde al bloque 5.

## Revisión visual independiente

Rondas: 7.6 (corregir prioridad móvil/foco), 8.4 (corregir placeholder) y
**8.56/10, aprobado**, sin categoría inferior a 7.

| Categoría | Nota | Evidencia |
|---|---:|---|
| Distinción visual | 7.5 | Fases y acciones de bodega; se mantiene el lenguaje visual del ERP |
| Tipografía/contenido | 8.5 | Producto/cantidad claros y lote desplegable, sin costos |
| Responsive | 8.5 | Tres tareas visibles; detalle prioritario en móvil/tablet |
| Interacción | 9 | Enter según tarea, sin ingreso automático, foco restaurado |
| Consistencia | 9 | Button reutilizado, controles de 44 px y tokens comunes |
| Accesibilidad | 8.5 | Contraste medido, labels, errores asociados y foco visible |
| Código | 9 | API separada, paginación, idempotencia y protección de contexto |
| Estados/límites | 8.5 | Carga, vacío, error, reintento y última operación identificada |

Limitación: no se certificaron lector Bluetooth físico ni impresora. Se probó
su comportamiento como teclado y las etiquetas ya existentes. Este cierre es
del bloque 3; siguen pendientes los bloques 4, 5 y 6 del plan maestro.

## Corrección del acceso de Rodrigo Molina — 28/10/2026

El acceso real detectó un defecto en el aprovisionamiento anterior: el usuario
`rodrigo.molina.bodega` tenía un correo con dominio reservado `.invalid`.
La contraseña era aceptada por `/auth/login` (200), pero `/auth/me` fallaba
con 500 al validar el correo en `MeResponse`, y el frontend descartaba la sesión.

Se corrigió únicamente el correo de esa cuenta a un marcador válido de
demostración en `example.com`, conservando contraseña, empleado, rol y alcance.
La corrección quedó en auditoría. El generador valida el correo antes de crear
la cuenta y permite indicar uno real con `--email`; el marcador de demostración
no configura un buzón de correo. Los DTO de autenticación conservan su validación.

El script `backend/scripts/repair_warehouse_operator_email.py` es específico para
el marcador original y el rol BODEGUERO PRINCIPAL en la empresa indicada.
Requiere un actor administrador activo, previsualiza por defecto y aplica con
`--apply`. Es idempotente y rechaza correos ajenos al defecto o duplicados.

Validación:

- Cinco pruebas unitarias: generación compatible con el perfil, normalización
  de correo explícito y rechazo de tres direcciones inválidas.
- Una prueba E2E con PostgreSQL aislado: previsualización, reparación, reintento,
  una sola auditoría, perfil/permisos/contexto, única bodega autorizada, cola de
  preparación y denegación de valoración; contraseña y permisos conservados.
- Ruff y formato: cuatro archivos aprobados.
- Edge con la cuenta real y la contraseña existente: login → empresa Grupo
  Lorena → Inventario → Existencias (nueve unidades registradas) → Preparar y
  ubicar (sin unidades pendientes). Sin errores JavaScript ni respuestas 500.
  No se modificaron cantidades, lotes ni costos durante esta verificación.

Evidencias sin credenciales en `tmp/warehouse-login/`: `result.json`,
`rodrigo-stock.png` y `rodrigo-preparation.png`. El paso transitorio por dashboard
intentó consultar bitácora y recibió 403; se mantuvo la denegación y el acceso
a Inventario continuó correctamente. No se amplió ningún permiso.
