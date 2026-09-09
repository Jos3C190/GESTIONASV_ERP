# Checklist de QA

Recorre esto de forma literal, ítem por ítem. Marca cada uno con evidencia (qué se probó, qué se encontró), no solo un check vacío. Si una categoría entera sale limpia, es más probable que no se haya probado en serio que que esté perfecta — vuelve a mirarla antes de darla por buena.

## Funcional
- [ ] Cada acción interactiva (botón, link, control) hace lo que su texto dice que hace.
- [ ] Los formularios validan entradas inválidas y muestran un mensaje específico, no genérico.
- [ ] Doble clic / envío repetido en una acción no duplica el efecto ni rompe el estado.
- [ ] La navegación (si existe) refleja el estado actual (p. ej. el item activo se ve activo).

## Estados
- [ ] Estado de carga: existe y no es solo un spinner genérico sin contexto si el contenido tarda.
- [ ] Estado vacío: tiene mensaje y, si aplica, una acción para salir de ese estado — no es una pantalla en blanco.
- [ ] Estado de error: explica qué pasó y qué hacer, en la voz de la interfaz.
- [ ] Estado de éxito/confirmación: existe cuando la acción lo amerita (guardar, enviar, eliminar).
- [ ] Estados disabled se ven visualmente distintos de los habilitados, no solo con opacidad genérica.

## Responsive
- [ ] Probado en un ancho móvil real (~375px), no solo "se ve bien" en desktop achicado.
- [ ] Probado en tablet (~768px) — revisa específicamente puntos de quiebre intermedios, donde suelen aparecer huecos raros.
- [ ] Probado en desktop ancho (1280px+) — el contenido no se estira sin límite ni deja espacios vacíos incómodos.
- [ ] Ningún texto se corta ni se superpone en ningún tamaño probado.
- [ ] Los targets táctiles en mobile tienen un tamaño razonable para el dedo (no botones minúsculos pegados entre sí).

## Accesibilidad
- [ ] Todo elemento interactivo es alcanzable con Tab y muestra un foco visible (no `outline: none` sin reemplazo).
- [ ] El orden de tabulación sigue el orden visual/lógico de la página.
- [ ] El contraste de texto sobre fondo pasa WCAG AA (4.5:1 texto normal, 3:1 texto grande) — verifícalo, no lo asumas por "se ve legible".
- [ ] Las imágenes informativas tienen `alt` descriptivo; las decorativas están marcadas como tales.
- [ ] Los inputs de formulario tienen `label` asociado (no solo placeholder).
- [ ] Si hay animaciones, se respeta `prefers-reduced-motion`.
- [ ] Roles ARIA solo donde el HTML semántico no alcanza — no ARIA redundante sobre elementos que ya lo tienen implícito.

## Performance y robustez básica
- [ ] Las imágenes tienen dimensiones declaradas (evita layout shift al cargar).
- [ ] No hay errores en consola.
- [ ] Listas largas o tablas grandes no re-renderizan todo en cada interacción menor.
- [ ] El primer render no depende de una animación para mostrar contenido (evita pantallas en blanco mientras algo hace fade-in).

## Consistencia visual
- [ ] Los mismos componentes (botones, cards, inputs) se ven idénticos en todos los lugares donde aparecen, salvo que la diferencia sea intencional.
- [ ] El espaciado sigue una escala reconocible, no valores sueltos que casi coinciden pero no exactamente.
- [ ] Los radios de borde son consistentes entre elementos del mismo nivel de jerarquía.
