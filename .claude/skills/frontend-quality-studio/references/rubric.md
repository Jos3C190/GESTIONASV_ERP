# Rúbrica del Crítico/Juez

Puntúa cada categoría de 0 a 10. Para cada una, escribe primero la evidencia concreta (qué ves, elemento por elemento) y después el número — nunca al revés. Un número sin evidencia específica no es una crítica real, es una opinión disfrazada de rigor.

**Veredicto:**
- **Aprobado**: promedio ≥ 8.5 **y** ninguna categoría por debajo de 7.
- **Rechazado**: cualquier otro caso. Un solo 5 en Accesibilidad no se compensa con un 10 en Tipografía — un producto enterprise no puede tener un fallo grave en un área aunque brille en otra.

Calibra siempre contra productos reales (Vercel, Linear, Stripe, Raycast, Apple, o la referencia que el usuario haya dado), no contra "está bien para algo hecho rápido por una IA".

---

### 1. Distinción visual y dirección de arte
¿Esto podría ser el resultado por defecto de cualquier prompt parecido, o refleja decisiones tomadas para este brief específico? Revisa contra los "tells" genéricos conocidos: fondo crema + acento terracota, tarjetas idénticas con la misma sombra gris suave, fondo casi negro con un único acento neón, eyebrows en mayúsculas sobre cada título, flechas al final de los botones, puntos medios uniendo metadatos. La presencia de uno de estos no descalifica automáticamente (a veces es la elección correcta), pero si aparecen sin una razón ligada al brief, es una señal de piloto automático.

### 2. Tipografía y sistema de contenido
Escala tipográfica coherente y deliberada, pesos y tracking con propósito, longitud de línea legible (idealmente <80 caracteres). El copy suena a la voz del producto y usa lenguaje que el usuario final entendería, no jerga interna del sistema. Sin lorem ipsum ni placeholders genéricos en un entregable final.

### 3. Layout, jerarquía y responsive real
La organización visual comunica qué es más importante, no solo se ve ordenada. El diseño funciona en mobile, tablet y desktop de verdad — no solo "no se rompe", sino que la jerarquía se adapta con criterio en cada tamaño. Alineación consistente, ritmo de espaciado que sigue una escala, no valores sueltos.

### 4. Micro-interacciones y motion
El motion (si existe) tiene un propósito claro: responde a una acción del usuario o marca un único momento orquestado importante — no es fade-in-slide-up repetido en cada sección ni una transición idéntica en cada hover. Si no hay motion en absoluto y el producto lo pediría (p. ej. un dashboard interactivo), eso también cuenta en contra.

### 5. Consistencia del sistema de diseño
Los mismos valores de espaciado, radio de borde, color y tipografía se repiten de forma predecible en toda la interfaz — se nota que hay tokens detrás, no valores mágicos sueltos por archivo. Los componentes reutilizables (botones, inputs, cards) se ven y comportan igual en todos los lugares donde aparecen.

### 6. Accesibilidad real
Contraste de color que pasa WCAG AA como mínimo. Foco de teclado visible en todo elemento interactivo. HTML semántico y roles ARIA correctos donde hacen falta. Se respeta `prefers-reduced-motion`. Los formularios tienen labels asociados y mensajes de error anunciables, no solo color para indicar estado.

### 7. Calidad y arquitectura del código
Componentes con responsabilidad clara, sin duplicación de estilos ni de lógica. Nombres que comunican intención. Sin especificidad de CSS peleando consigo misma. Consideración básica de performance (imágenes con dimensiones, nada de recalcular innecesariamente, nada de listas gigantes sin virtualizar si aplica). El código se podría entregar a otro ingeniero mañana sin que tenga que adivinar decisiones.

### 8. Pulido de estados y manejo de casos límite
Loading, vacío, error y éxito están todos resueltos con la misma atención que el estado feliz principal — no solo diseñados, sino con copy que ayuda a decidir qué hacer a continuación. Los errores explican qué pasó y cómo resolverlo, en la voz de la interfaz, no en tono de disculpa humana vaga.

---

## Cómo comunicar el veredicto

```
## ⚖️ Veredicto del Crítico

| Categoría | Puntaje | Evidencia |
|---|---|---|
| Distinción visual | X/10 | ... |
| Tipografía y contenido | X/10 | ... |
| Layout y responsive | X/10 | ... |
| Motion e interacción | X/10 | ... |
| Consistencia del sistema | X/10 | ... |
| Accesibilidad | X/10 | ... |
| Calidad de código | X/10 | ... |
| Estados y casos límite | X/10 | ... |

**Promedio:** X.X/10
**Veredicto:** ✅ Aprobado / ❌ Rechazado — [si rechazado: qué fase debe corregir qué, en 2-4 puntos concretos]
```
