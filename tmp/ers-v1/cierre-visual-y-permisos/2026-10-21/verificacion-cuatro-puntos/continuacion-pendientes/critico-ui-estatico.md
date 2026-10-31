# Revisión estática de UI — continuación final B01–B08

**Fecha:** 21/10/2026 · **Modalidad:** lectura de código, sin navegador ni capturas · **Resultado:** no aprueba como aceptación visual.

La evaluación independiente de código rechazó el corte frente al umbral de aceptación visual de **8.5/10**. Accesibilidad quedó en **6.5/10**. Es una valoración estática; no confirma apariencia, flujo ni defectos reproducibles en ejecución.

| Dimensión | Puntaje | Observación estática |
| --- | ---: | --- |
| Dirección visual | 6.5/10 | Sin capturas actuales no se pudo calificar la presentación final. |
| Tipografía y contenido | 7.5/10 | `SalesQuotationDetail.svelte` concentra markup en líneas muy largas. |
| Adaptación responsive | 8/10 | Hay puntos de quiebre en el código; no se demostró 390×844 en vivo. |
| Interacción y movimiento | 7/10 | Hay estilos globales de foco y movimiento reducido; el foco del diálogo no se probó. |
| Consistencia | 8/10 | Se reutilizan tokens; conviven estilos directos y el componente de botones. |
| Accesibilidad | 6.5/10 | Se señalan estados de carga sin `role="status"` en los tres componentes listados abajo. |
| Código y mantenibilidad | 7/10 | Se recomienda formatear el detalle de cotización. |
| Estados de interfaz | 7/10 | Requieren comprobación visual dinámica. |

Observaciones para comprobar en una sesión visual autorizada:

- `frontend/src/lib/features/sales/components/SaleDetail.svelte:142`: estado de carga sin anuncio accesible.
- `frontend/src/lib/features/sales/components/SalesQuotationDetail.svelte:81`: estado de carga sin anuncio accesible; markup muy comprimido.
- `frontend/src/lib/features/purchases/components/PurchaseVerificationEditor.svelte:303`: estado de carga sin anuncio accesible.

No se modificó producto por estos comentarios: no se reprodujeron como falla en vivo y la inspección del navegador quedó bloqueada por la política de seguridad de la herramienta. La siguiente comprobación es visual con captura permitida, teclado/lector accesible y tamaños objetivo; después, confirmar si el estado de carga carece realmente de anuncio. No atribuir el puntaje estático a una prueba de navegador.
