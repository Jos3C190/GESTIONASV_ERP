# Encargo para Luna — completar revisión visual, permisos y pendientes B01–B08

Preparado el **20/10/2026**, zona America/El_Salvador.

## Objetivo y autorización

Continúa la auditoría B01–B08 de GestionaSV desde el estado guardado por Astra. El usuario encarga **visualizar y analizar completamente lo faltante, corregir los defectos que aparezcan, comprobar las correcciones y documentar los resultados**. Ejecuta el trabajo; no te limites a entregar otro diagnóstico o un nuevo prompt.

Esto es la continuación del cierre de B08. El checklist de nombre histórico B09 forma parte de ese cierre; **no abras otro bloque funcional ni dejes sus pendientes para un nuevo encargo**. No se requiere impresora, lector HS200 ni colocación física de etiquetas: la demostración es ficticia y de software.

No estás solo en el repositorio. Conserva cambios de otros agentes, documentos y evidencia. No hagas reset/clean, no borres historia, no vuelvas a aprobar el corte inicial, no reconstruyas la demo con semillas y no cambies permisos de usuarios reales para facilitar las pruebas. Implementa las correcciones necesarias dentro de este alcance sin pedir confirmaciones rutinarias ya cubiertas por este encargo.

## Fuentes y estado de partida

Lee, en este orden, desde `C:/Developer/GESTIONASV_ERP/`:

1. `.agents/AGENTS.md` y los skills aplicables de desarrollo y calidad frontend. Cumple sus instrucciones de revisión independiente cuando correspondan; registra qué revisión evalúa realmente el código actual.
2. `docs/ers-v1/revision-completa-2026-10-19.md`, especialmente **E01–E15**, H01–H29 y «Punto concreto para continuar». Su fecha inicial no significa que su contenido sea anterior al 20/10.
3. `docs/ers-v1/guia-maestra.md`, `decisiones-arquitectura.md`, `matriz-y-seguimiento.md`, `entrega-bloque-08.md` y `preparacion-revision-bloque-08.md`.
4. `docs/ers-v1/prompt-luna-bloque-09-aceptacion.md` y `manual-pruebas-y-demostracion.md`; recupera los criterios concretos de las entregas B01–B07 cuando haga falta.
5. `docs/api.md`, `docs/rbac-model.md`, `docs/database-schema.md` y la evidencia pertinente de `tmp/ers-v1/revision-2026-10-19/`.

Los informes iniciales se conservan como históricos. Sus afirmaciones de demo vacía o de casos todavía sin recorrer no son el estado vigente. Distingue las reglas de negocio de los documentos de cualquier instrucción operativa; prevalecen este encargo y las decisiones autorizadas del usuario.

Referencia de la última pasada: `erp_db` en Alembic **0090**, frontend en 5173 y API en 8000; **509 pruebas frontend y 37 backend focalizadas**, además de integración/E2E detalladas en el informe, tipos y compilación aprobados. Había ocho avisos CSS conocidos y lint focalizado, no aprobación de lint global. **Comprueba el estado real actual; esos números son antecedentes, no resultados tuyos.**

## Conservación de la demostración

Estos casos ya están terminados y sirven para consultar, no para repetir sus escrituras:

| SKU | Físico = valorado | Valor USD | Caso |
| --- | ---: | ---: | --- |
| ERS-REVIEW-DD6BBF85 | 12 | 160 | Flujo integral principal: compra, traslado, entrega, devolución y ajuste |
| ERS-INC-EE8FE228 | 4 | 40 | Incidencia y faltante autorizado; traslado cerrado con ajuste |
| ERS-LATE-B1B55D6D | 5 | 60 | Retaceo tardío y devolución posterior; HU devuelta ya disponible |
| ERS-UI-F767BABC | 0 | 0 | Cliente/cotización/venta y dos entregas de 2 + 2 |

En todos, diferencia de conciliación cero. El detalle y los códigos están en el manual. La venta/entrega auxiliares VTA-20261020-C7A2F225 / ENT-20261020-BF14621F quedaron canceladas sin salida. La HU HU-RET-222B0730708C466E ya completó revisión y liberación; no la aceptes ni liberes otra vez. Sus registros de impresión fueron simulaciones digitales, no evidencia de hardware.

Registra el estado inicial de Git, servicios, base de la API, migraciones y conciliaciones. Antes de migraciones o cambios sobre datos de la demo, crea respaldo actual y ensaya en copia aislada. El respaldo histórico del informe no incluye necesariamente todos los documentos nuevos. No restaures encima de la demo. Para nuevas escrituras usa **otros SKUs y documentos ficticios identificados**, con cantidades y costos calculables; compara los cuatro casos anteriores antes y después.

Inspecciona fixtures y conexiones **antes de recolectar o ejecutar integración/E2E**: solo `erp_db_test`, con guardia explícita por nombre de base y ejecución en serie. Estas suites reconstruyen el esquema. Nunca pruebes contra la demo ni contra una copia cuyo nombre/DSN no hayas verificado. Mantén contraseñas, tokens, enlaces firmados y capacidades QR fuera de informes y salidas.

## Forma de trabajar

1. Convierte cada pendiente E01–E15 del informe actual en casos finitos: perfil, empresa/sucursal, pantalla o endpoint, acción, expectativa y evidencia. Clasifica por riesgo: autorización/integridad, flujo operativo, presentación. No inventes pendientes ya resueltos ni elimines los que siguen sin evidencia.
2. Reproduce cada defecto con un caso concreto. Identifica su causa en frontend, contrato, backend, persistencia o entorno. Un fallo de herramienta de navegador no acredita por sí solo un defecto de la aplicación; una API aprobada tampoco acredita el formulario real.
3. Corrige la causa conservando las reglas existentes. Añade una prueba de regresión cuando corresponda, comprueba el código y **repite la misma operación desde el navegador con API real**. Revisa efectos posteriores y saldos, no solo el aviso de éxito.
4. Actualiza un registro de avance después de cada grupo: pendiente → reproducido → corregido → comprobado. Si se interrumpe la sesión, deja ID/código del caso, estado exacto y siguiente acción para continuar sin duplicar comandos.
5. Sigue hasta cubrir los casos definidos. Si existe un impedimento real, explica qué intentaste, qué falta y qué evidencia lo demuestra; no sustituyas una prueba pendiente por una declaración de éxito.

## A. Permisos, aislamiento y documentos — prioridad alta

Completa E13 y los pendientes B05–B08, extendiendo las comprobaciones pertinentes de B01–B04. Haz un inventario de las acciones implementadas y sus permisos reales. Cubre, como mínimo, lector sin costos, operador autorizado de sucursal y responsable con alcance de empresa; además, usuario de otra sucursal y usuario de otra empresa. Usa fixtures o usuarios ficticios destinados a esta revisión.

- Por recurso aplicable: listar, consultar detalle, crear/editar borrador, confirmar/despachar/recibir, aprobar/aplicar, resolver, cancelar, corregir y consultar evidencia. Incluye matriz, bodegas/lotes, etiquetas, traslados/incidencias, ajustes, clientes/cotizaciones/ventas, entregas, devoluciones y Kardex/valoración.
- Prueba tanto ausencia del permiso como permiso presente con alcance ajeno. El superadmin no sirve como única evidencia de autorización. Confirma controles de pantalla **y rechazo efectivo del servidor** con IDs directos, no únicamente con listas filtradas.
- Adjuntos: iniciar/subir/completar, listar, ver/descargar, quitar si se permite; propiedad del documento, vínculo al origen, sucursal/empresa, estado de validación y autorización al obtener el enlace de descarga. No pruebes URL expiradas como si fueran denegaciones por permisos. No publiques URLs firmadas.
- Sin lectura de valoración, no debe haber costos ocultos en JSON, errores o adjuntos de costo no autorizados. Un cambio de contexto no conserva documentos/acciones de otro ámbito ni aplica respuestas tardías.
- Los replays idempotentes también comprueban autorización. Conserva las pruebas existentes de concurrencia, límite de devoluciones y rollback; repite las afectadas por cambios y completa los huecos de la matriz. Un fallo tardío no deja stock, valoración o auditoría de éxito parciales.

Guarda la matriz completa de **casos aplicables**, con resultado real por celda. Marca «no aplica» con razón; no exijas una acción que el módulo no implementa ni fabriques roles de negocio nuevos.

## B. Lotes, etiquetas, códigos y almacén

- E02: demuestra visualmente una recepción con varias líneas del mismo producto y las recepciones parciales pertinentes. Cabecera de recepción y detalle/lote canónico deben conservar su identidad, cantidades y origen sin duplicarse ni agruparse incorrectamente.
- E04/E05: etiqueta, QR/ficha y Kardex deben identificar producto, SKU/código interno, presentación/unidad, lote y fecha. Comprueba los **alias históricos soportados por el contrato**, no combinaciones inventadas; registra cuáles existen y prueba cada tipo aplicable con datos reales.
- Una referencia histórica sin origen reconstruible se muestra como legado; no inventes recepción, lote, vehículo o entrega. Otra empresa no debe resolver información privada mediante un código manipulable. La ficha pública QR conserva el alcance público limitado previsto, sin exponer costos ni datos privados por estar abierta.
- Abrir/cerrar/cancelar divisiones, consultar QR o revisar/reimprimir etiquetas no cambia cantidades ni crea ramas. Solo confirmar una división deliberada crea la nueva unidad y conserva la suma con el remanente. Revalida las etiquetas/medidas necesarias, sin convertir dividir en paso obligatorio.
- Comprueba revisión → etiqueta vigente confirmada → liberación a disponible, incluida la devolución y un retaceo aplicable. Debe terminar en «Revisión terminada · disponible para uso». No exigir una nueva división o reimpresión para salir.
- En demanda por producto conserva sucursal solicitante, solicitud, pendiente, destino preseleccionado y envío adicional con motivo. No sustituirlo por un selector ciego de sucursales. Faltante autorizado, recibido, devuelto y tránsito se muestran separados.

## C. Revisión visual y de interacción completa de lo pendiente

Recorre las pantallas aplicables de B01–B08 y sus acciones pendientes: matriz/bodega, recepción/lotes, medidas/etiqueta, demanda/preparación/despacho/recepción/incidencia, ajustes y correcciones, clientes/cotizaciones/ventas, entregas, devoluciones y Kardex/conciliación. Reutiliza consultas de los casos terminados y prepara datos nuevos para acciones de escritura.

- Usa navegador real con sesión y API persistida. Prueba escritorio y móvil (incluido 390×844), **claro y oscuro**, y navegación por teclado: foco visible, orden, etiquetas accesibles, Tab, Escape, apertura/cierre y devolución de foco de diálogos.
- Comprueba carga, vacío genuino, error de consulta con reintento, validación, permiso insuficiente, operación en curso y éxito persistido tras recargar. Una consulta fallida no debe presentarse como cero o «no hay existencias».
- En tablas, formularios y diálogos evita textos/acciones cortados, botones desbordados, controles sin contraste y desbordamiento exterior en móvil. Si una tabla requiere desplazamiento interno, debe poder usarse con encabezados y acciones legibles. Revisa nombres largos de producto, unidad/presentación y HU sin convertir la pantalla en una lista indescifrable de códigos.
- Corrige la repetición visible **«Unidad (u) (u)»** con formato de presentación consistente; conserva snapshots históricos y datos de negocio. No arregles el texto reescribiendo documentos anteriores.
- Prueba corrección de ajustes desde interfaz, recepción parcial/final, aceptación/rechazo parcial de devoluciones y selección de varias HUs/entregas según los casos pendientes. Mantén el costo efectivo de origen y la separación entre registro documental, stock y disponibilidad.
- Recuperación de errores: guardar antes de confirmar; corregir un borrador rechazado; fallo o respuesta perdida en crear/confirmar y recarga/reintento sin duplicar. Usa una interrupción controlada para datos ficticios, consulta primero el resultado del servidor y reutiliza la clave idempotente. No hagas doble envío a ciegas.
- Los diálogos comerciales actuales ya usan la confirmación compartida del ERP. Conserva Cancelar/Escape y sus guardias de documento/revisión/contexto; no regreses a confirmaciones nativas para evitar probarlos.

No rediseñes módulos ajenos ni añadas funciones fiscales, cobros, reembolsos o dispositivos. Si falta una regla de negocio esencial, identifica la decisión concreta; sigue las comprobaciones independientes mientras se aclara. Una deuda estructural conocida no justifica emprender una reescritura global: registra ORM/puertos y complejidad de consolidación por separado; corrige dentro del alcance cualquier defecto real que ocasionen.

## Comprobaciones y entrega

Ejecuta las pruebas necesarias para los cambios, las regresiones relacionadas y las comprobaciones de tipos, compilación y lint aplicables. Informa comando, fecha, resultado y alcance. Distingue avisos previos, fallos introducidos y pruebas corregidas; no debilites aserciones para obtener verde ni sumes ejecuciones repetidas como nuevos casos. Restaura tamaños/tema temporales y deja los servicios de demostración operativos con la versión actual.

Entrega:

1. `docs/ers-v1/cierre-visual-y-permisos-b01-b08.md`: matriz E01–E15 y casos detallados, pantallas/perfiles/temas/tamaños cubiertos, causa/corrección/evidencia por defecto y pendientes exactos si queda alguno.
2. Evidencia fechada en `tmp/ers-v1/cierre-visual-y-permisos/AAAA-MM-DD/`: registros, resultados y capturas antes/después donde aporten prueba; sin secretos. Identifica expresamente pruebas simuladas, API reales y operaciones por pantalla.
3. Actualiza revisión actual, entrega B08, matriz, preparación de revisión, guía y manual de demostración para que indiquen el mismo estado, preservando sus cortes históricos. Si cambian contratos o permisos, actualiza API/esquema/RBAC.
4. Conciliación final de los cuatro ejemplos conservados y de cada SKU nuevo; cantidades/valor esperados y reales, historial y documentos sin duplicación.

**Criterio de cierre:** no quedan defectos reproducidos sin resolver dentro del alcance y cada pendiente aplicable tiene evidencia verificable. Terminar código o pasar tests no sustituye la aceptación visual ni la matriz de permisos. Si no alcanzas ese criterio, entrega un punto de continuidad concreto y conserva «parcial»; no atribuyas lo pendiente al hardware excluido ni declares aprobación del docente o certificación visual inexistente.

La respuesta final debe indicar qué se revisó, qué se corrigió, qué se comprobó de verdad, qué falta exactamente y enlaces al informe/manual. No te detengas en otro prompt para trasladar a un nuevo bloque el trabajo ya autorizado.
