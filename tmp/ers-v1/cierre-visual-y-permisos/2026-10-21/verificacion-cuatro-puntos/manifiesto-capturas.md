# Manifiesto de capturas V02

**Corte:** 21/10/2026. El directorio `capturas/` está vacío; no se declara ninguna imagen archivada.

En la continuación del 21/10, `cua.getTab` para `http://localhost:5174/inventory/trace` fue rechazado por la política de seguridad de URL. La inspección terminó ahí y no se probó una vía alterna para acceder a la misma sesión. El scorecard de código estático se archiva separado y no cuenta como evidencia visual: [crítica estática](continuacion-pendientes/critico-ui-estatico.md). V02 conserva estado **ABIERTO**.

La capacidad de navegador disponible permitió inspección de árbol accesible y observación en sesión. No ofreció una operación documentada para guardar la imagen de la sesión en este directorio. La inspección de métodos documentados confirmó observación (`getScreenshot`) pero no exportación a un archivo local; el intento anterior de exportación fue bloqueado. No se intentó otro mecanismo de extracción ni se presenta el árbol accesible como PNG.

| Familia | UI observada reutilizable | PNG escritorio | PNG móvil | Temas | Estado V02 |
| --- | --- | --- | --- | --- | --- |
| Matriz/bodega | Evidencia histórica citada en cierre | No archivado | No archivado | Claro/oscuro no completos | ABIERTO |
| Recepción/lotes/medidas/etiqueta | HU de café, QR público, identidad de lote; ver `v03-ui-trace-qr-division-cancel-2026-10-21.md` | No archivado | No archivado | No completos | ABIERTO |
| Demanda/traslados/incidencias | Traslado 8+2 y demanda SCR observados | No archivado | No archivado | No completos | ABIERTO |
| Ajustes/correcciones/adjuntos | Corrección de ajuste completada; ver `v04-ui-operations-2026-10-21.md` | No archivado | No archivado | No completos | ABIERTO |
| Clientes/cotización/venta | Venta ficticia con dos entregas observada | No archivado | No archivado | No completos | ABIERTO |
| Entregas/devoluciones | Devolución mixta 2 aceptadas + 1 rechazada | No archivado | No archivado | No completos | ABIERTO |
| Kardex/conciliación | Conciliación SQL/UI enlazada en registros anteriores | No archivado | No archivado | No completos | ABIERTO |

**Próxima acción:** usar un navegador de prueba con función documentada de exportación PNG; por cada familia guardar escritorio y 390×844 en claro y oscuro, y añadir perfil, ruta, estado y fecha. La cifra máxima es 28 imágenes base, con capturas adicionales solo para estados de corrección que las imágenes base no muestren.
