# El Crítico como subagente real en Codex

Esto aplica si estás corriendo dentro de Codex (CLI, extensión de IDE, o la app). Codex tiene un mecanismo de subagentes genuino: un hilo hijo que arranca con **una ventana de contexto limpia** — no hereda tu conversación ni el razonamiento que usaste para construir lo que le vas a pedir que revise, salvo que se lo copies explícitamente en el prompt de la tarea. Esa es exactamente la propiedad que necesita un Crítico honesto: alguien que juzga el resultado sin haber vivido las decisiones y las justificaciones que lo produjeron.

Usar esto en vez de simular el rol de Crítico en el mismo hilo que diseñó e implementó es la diferencia entre "le pido a Claude/Codex que se autoevalúe" y "hay un juez que de verdad no sabe cómo se hizo el truco".

## Configuración (una vez por proyecto)

1. Copia `assets/critico-ui.toml` a `.codex/agents/critico-ui.toml` en la raíz del repo (o a `~/.codex/agents/critico-ui.toml` si quieres tenerlo disponible en todos tus proyectos, no solo este).
2. Nada más que instalar — Codex no spawnea subagentes automáticamente solo porque el archivo exista. Hay que pedírselo explícitamente cada vez, como se ve abajo.

El archivo ya viene configurado con `sandbox_mode = "read-only"`: el Crítico estructuralmente no puede editar código, así que ni por accidente ni por "ayudar" va a arreglar algo en vez de rechazarlo — solo puede puntuar y explicar.

## Cómo invocarlo en la Fase 5 del flujo

En vez de que el mismo hilo que hizo Diseño e Ingeniería se ponga el sombrero de Crítico, delega explícitamente con una instrucción parecida a esta:

```
Spawn critico-ui para revisar [ruta del componente/carpeta, o la URL del preview] contra la rúbrica de frontend-quality-studio. Dale solo el artefacto final y, si aplica, el plan de diseño de la Fase 2 — no le copies el razonamiento ni las justificaciones que usamos para construirlo. Espera su resultado y tráelo de vuelta como el veredicto oficial.
```

Lo importante de esa instrucción no es la sintaxis exacta sino dos cosas:
- Que sea Codex quien decide activamente delegar (no pasa solo).
- Que el prompt de la tarea del subagente **no incluya** el razonamiento previo — pásale el resultado, no el proceso. Si copias y pegas el hilo completo de Diseño+Ingeniería en la tarea del subagente, le estás devolviendo exactamente el contexto que queríamos que no tuviera.

## Qué pasa si rechaza

Toma el feedback del subagente tal cual (el `references/rubric.md` de este skill ya define el formato del veredicto) y vuelve a las Fases 2/3 del flujo principal. Para la re-revisión, **spawnea un critico-ui nuevo** en vez de reutilizar el mismo hilo — un hilo que ya emitió un veredicto tiende a anclarse a lo que dijo antes en vez de mirar la versión corregida con ojos frescos.

## Detalles que conviene saber

- **Los subagentes no se activan solos.** Codex solo los spawnea cuando se lo pides directamente en el prompt, o cuando estas instrucciones del skill se lo piden por ti — por eso la línea de arriba es algo literal para escribir o pegar, no un modo que se prenda solo.
- **El sandbox es un piso, no una garantía absoluta.** El subagente hereda como mínimo la política de aprobación/sandbox de la sesión padre. Si tu sesión principal corre en un modo muy permisivo que sobreescribe todo, revisa la sección `[agents]` de tu `.codex/config.toml` para confirmar que `sandbox_mode = "read-only"` del TOML realmente se respeta.
- **Profundidad de anidamiento.** Por defecto `max_depth = 1`, así que critico-ui no puede spawnear sus propios sub-subagentes — no lo necesita para este rol.
- **Extiende el mismo patrón a QA.** Si además quieres que la Fase 4 (QA) tenga ojos frescos y no solo el mismo hilo que construyó, duplica el TOML como `qa-uiux.toml`: `sandbox_mode = "read-only"` si solo va a inspeccionar, o `"workspace-write"` si necesita correr una suite de tests de verdad.
