# Guía de Diseño UX/UI — Design System Geist (Vercel)

> **Versión:** `v1.0.0` | **Última actualización:** `22/07/2026`  
> Esta guía es la referencia obligatoria para todo diseño visual y de interacción
> en el ERP System. Se basa en el design system **Geist** de Vercel, adaptado al
> contexto de un panel empresarial. Síguela para mantener consistencia visual en
> cada nuevo módulo, componente o pantalla.

---

## 1. Recursos oficiales de referencia

| Recurso | Enlace | Uso |
|---------|--------|-----|
| Geist Design System | https://vercel.com/geist | Sistema de diseño completo: colores, tipografía, componentes |
| Geist Colors | https://vercel.com/geist/colors | Escala de colores (10 steps, backgrounds, gray, blue, red, amber, green, teal, purple, pink) |
| Geist Typography | https://vercel.com/geist/typography | Tipografía Geist Sans y Geist Mono, escala y uso |
| Geist Components | https://vercel.com/geist/components | Catálogo de componentes (Button, Card, Input, Modal, Badge, Table, etc.) |
| Geist Brands | https://vercel.com/design/brands | Guías de uso de marca (Vercel, Next.js, Turbo, v0, AI SDK) |
| Geist Introduction | https://vercel.com/geist/introduction | Principios del design system |
| Geist Materials | https://vercel.com/geist/materials | Sombras, elevación, materiales |
| Geist Badge | https://vercel.com/geist/badge | Componente Badge (variantes, pill) |
| Geist Button | https://vercel.com/geist/button | Componente Button (variantes, tamaños) |
| Geist Card | https://vercel.com/geist/card | Componente Card |
| Geist Input | https://vercel.com/geist/input | Componente Input |
| Geist Modal | https://vercel.com/geist/modal | Componente Modal |
| Geist Table | https://vercel.com/geist/table | Componente Table |
| Geist Skeleton | https://vercel.com/geist/skeleton | Componente Skeleton (loading) |
| Geist Spinner | https://vercel.com/geist/spinner | Componente Spinner |
| Geist Toast | https://vercel.com/geist/toast | Componente Toast (notificaciones) |
| Geist Tabs | https://vercel.com/geist/tabs | Componente Tabs |
| Geist Empty State | https://vercel.com/geist/empty-state | Componente Empty State |
| Geist Error | https://vercel.com/geist/error | Componente Error |
| Geist Toggle | https://vercel.com/geist/toggle | Componente Toggle/Switch |
| Geist Tooltip | https://vercel.com/geist/tooltip | Componente Tooltip |
| Geist Snippet | https://vercel.com/geist/snippet | Componente Snippet (código) |
| Geist Pagination | https://vercel.com/geist/pagination | Componente Pagination |
| Geist Progress | https://vercel.com/geist/progress | Componente Progress |
| Geist Avatar | https://vercel.com/geist/avatar | Componente Avatar |
| Geist Switch | https://vercel.com/geist/switch | Componente Switch |
| Geist Checkbox | https://vercel.com/geist/checkbox | Componente Checkbox |
| Geist Select | https://vercel.com/geist/select | Componente Select |
| Geist Textarea | https://vercel.com/geist/textarea | Componente Textarea |
| Geist Label | https://vercel.com/geist/label | Componente Label |
| Geist Separator | https://vercel.com/geist/separator | Componente Separator |
| Geist Status Dot | https://vercel.com/geist/status-dot | Componente Status Dot |
| Geist Collapse | https://vercel.com/geist/collapse | Componente Collapse |
| Geist Menu | https://vercel.com/geist/menu | Componente Menu |
| Geist Drawer | https://vercel.com/geist/drawer | Componente Drawer |
| Geist Command Menu | https://vercel.com/geist/command-menu | Componente Command Menu (Cmd+K) |
| Geist Loading Dots | https://vercel.com/geist/loading-dots | Componente Loading Dots |
| Geist Context Menu | https://vercel.com/geist/context-menu | Componente Context Menu |
| Geist Banner | https://vercel.com/geist/banner | Componente Banner |
| Geist Note | https://vercel.com/geist/note | Componente Note (callout) |
| Geist Dots Menu | https://vercel.com/geist/dots-menu | Componente Dots Menu (overflow) |
| Geist Radio | https://vercel.com/geist/radio | Componente Radio |
| Geist Slider | https://vercel.com/geist/slider | Componente Slider |
| Geist Gauge | https://vercel.com/geist/gauge | Componente Gauge |
| Geist Breadcrumbs | https://vercel.com/geist/breadcrumbs | Componente Breadcrumbs |
| Geist Calendar | https://vercel.com/geist/calendar | Componente Calendar |
| Geist Combobox | https://vercel.com/geist/combobox | Componente Combobox |
| Geist Multi Select | https://vercel.com/geist/multi-select | Componente Multi Select |
| Geist Show More | https://vercel.com/geist/show-more | Componente Show More |
| Geist Scroller | https://vercel.com/geist/scroller | Componente Scroller |
| Geist Phone | https://vercel.com/geist/phone | Componente Phone |
| Geist Video | https://vercel.com/geist/video | Componente Video |
| Geist Browser | https://vercel.com/geist/browser | Componente Browser |
| Geist Book | https://vercel.com/geist/book | Componente Book |
| Geist File Tree | https://vercel.com/geist/file-tree | Componente File Tree |
| Geist JSON View | https://vercel.com/geist/json-view | Componente JSON View |
| Geist Keyboard Input | https://vercel.com/geist/keyboard-input | Componente Keyboard Input |
| Geist Middle Truncate | https://vercel.com/geist/middle-truncate | Componente Middle Truncate |
| Geit Clearable Input | https://vercel.com/geist/clearable-input | Componente Clearable Input |
| Geist Search Input | https://vercel.com/geist/search-input | Componente Search Input |
| Geist Split Button | https://vercel.com/geist/split-button | Componente Split Button |
| Geist Text With Copy | https://vercel.com/geist/text-with-copy-button | Componente Text With Copy |
| Geist Copy Button | https://vercel.com/geist/copy-button | Componente Copy Button |
| Geist Fieldset | https://vercel.com/geist/fieldset | Componente Fieldset |
| Geist Description | https://vercel.com/geist/description | Componente Description |
| Geist Feedback | https://vercel.com/geist/feedback | Componente Feedback |
| Geist Entity | https://vercel.com/geist/entity | Componente Entity |
| Geist Choicebox | https://vercel.com/geist/choicebox | Componente Choicebox |
| Geist Code Block | https://vercel.com/geist/code-block | Componente Code Block |
| Geist Code | https://vercel.com/geist/code | Componente Code |
| Geist Context Card | https://vercel.com/geist/context-card | Componente Context Card |
| Geist Destructive Modal | https://vercel.com/geist/destructive-action-modal | Componente Destructive Action Modal |
| Geist Error Card | https://vercel.com/geist/error-card | Componente Error Card |
| Geist Grid | https://vercel.com/geist/grid | Componente Grid |
| Geist Load More | https://vercel.com/geist/load-more-button | Componente Load More Button |
| Geist Pill | https://vercel.com/geist/badge#pill | Componente Pill (badge pequeño) |
| Geist Project Banner | https://vercel.com/geist/project-banner | Componente Project Banner |
| Geist Relative Time | https://vercel.com/geist/relative-time-card | Componente Relative Time Card |
| Geist Sheet | https://vercel.com/geist/sheet | Componente Sheet |
| Geist Theme Switcher | https://vercel.com/geist/theme-switcher | Componente Theme Switcher |

---

## 2. Principios de diseño Geist

### 2.1 Claridad sobre decoración
- Cada elemento visual debe comunicar función, no decoración.
- Elimina cualquier adorno que no aporte claridad o jerarquía.
- "Si tienes que preguntarte si algo es necesario, probablemente no lo es."

### 2.2 Densidad sin saturación
- Los paneles ERP requieren mucha información visible, pero el aire (espaciado)
  es lo que hace que la densidad sea legible, no agobiante.
- `gap-4` o `gap-6` entre tarjetas, `p-5` o `p-6` interno.
- Nunca apilar más de 4-5 elementos sin un separador o salto de sección.

### 2.3 Consistencia radical
- Un mismo tipo de elemento (botón, badge, tarjeta) se ve idéntico en toda la app.
- Usa los componentes de `lib/components/ui/` — no crees estilos ad-hoc.
- Si necesitas una variación nueva, extiende el componente, no lo dupliques.

### 2.4 Feedback inmediato
- Todo botón tiene `active:scale-[0.98]` (sutil, 150ms).
- Todo hover de tarjeta tiene `hover-lift` (translateY -1px + shadow).
- Todo input tiene `focus:shadow-glow` (ring azul sutil).
- Todo loading tiene skeleton con shimmer (no spinners genéricos).

---

## 3. Tokens de color

### 3.1 Escala Geist (10 steps por color)

Cada color tiene 10 steps (`100` a `1000`), mapeados a uso específico:

| Step | Uso |
|------|-----|
| `100` | Fondo de componente (default) |
| `200` | Fondo de componente (hover) |
| `300` | Fondo de componente (active) |
| `400` | Borde (default) |
| `500` | Borde (hover) |
| `600` | Borde (active) |
| `700` | Fondo de alto contraste |
| `800` | Fondo de alto contraste (hover) |
| `900` | Texto secundario e iconos |
| `1000` | Texto primario e iconos |

### 3.2 Tokens implementados en este proyecto

Ver `src/app.css` y `tailwind.config.js` para los valores exactos de cada token.

**Light mode:**
- `--surface`: blanco puro `255 255 255`
- `--surface-muted`: gris muy claro `250 250 250`
- `--border`: gris claro `233 233 233`
- `--foreground`: casi negro `17 17 17`
- `--primary`: Geist blue `0 112 243`

**Dark mode:**
- `--surface`: negro puro `0 0 0`
- `--surface-elevated`: `10 10 10`
- `--border`: `26 26 26`
- `--foreground`: `250 250 250`
- `--primary`: `0 168 243`

### 3.3 Reglas de uso de color

1. **Un solo acento dominante**: el azul Geist (`--primary`) es el único color
   "fuerte" de la UI. Se usa para: links, focus rings, botones primarios,
   indicadores activos. Nunca usar azul para fondos grandes.

2. **Colores semánticos solo en badges**: éxito/advertencia/error van
   exclusivamente en componentes `Badge` con la variante "suave"
   (fondo al 8-10% + borde al 15%). Nunca usar un color semántico como
   fondo de una tarjeta o sección completa.

3. **Paleta categórica de gráficos**: definida en DonutChart como 5 tonos
   derivados del azul (`0 112 243`, `59 130 246`, `14 165 233`,
   `100 116 139`, `148 163 184`). Reutilizar esta paleta en todos los
   gráficos del sistema. Documentar nuevas paletas aquí.

4. **Bordes hairline**: siempre `1px` con color de `--border`. En oscuro,
   `--border` es `26 26 26` (visible sobre negro). Nunca usar bordes
   gruesos o con sombra dura.

5. **Sombras**: máximas 3 niveles (`shadow-soft`, `shadow-lifted`,
   `shadow-floating`). Todas con opacidad baja (4-10%). La elevación
   se comunica con borde + cambio de tono, no con sombras pesadas.

---

## 4. Tipografía

### 4.1 Fuentes

- **Geist Sans**: todo texto de interfaz. Los archivos variables se sirven
  desde `frontend/static/fonts` para que la métrica no dependa de un CDN.
- **Geist Mono**: todos los números (KPIs, tablas, ejes de gráficos, IDs y
  códigos).
- `system-ui` queda como fallback accesible si el navegador no puede cargar
  las fuentes locales. La licencia SIL OFL se conserva junto a los archivos.

### 4.2 Escala tipográfica

| Uso | Tamaño | Peso | Clase Tailwind |
|-----|--------|------|----------------|
| Título de página (header) | 15px | 600 | `text-[15px] font-semibold` |
| Título de tarjeta | 13px | 600 | `text-sm font-semibold` |
| Número de KPI | 24px | 700 mono | `text-2xl font-bold font-mono tabular-nums` |
| Texto de cuerpo | 13px | 400 | `text-[13px]` |
| Label de KPI | 11px | 500 uppercase | `text-[11px] font-medium uppercase tracking-wide` |
| Texto auxiliar | 11px | 400 | `text-[11px]` |
| Badge | 12px | 600 | `text-xs font-semibold` |
| Header de tabla | 11px | 500 uppercase | `text-[11px] font-medium uppercase tracking-wide` |
| Celda de tabla | 13px | 400 | `text-[13px]` |
| Número en tabla | 12px | 400 mono | `text-[12px] tabular-nums font-mono` |

### 4.3 Regla no negociable

**Todo número va en `font-mono` con `tabular-nums`** — KPIs, tablas, ejes
de gráficos, contadores. Los números deben alinearse verticalmente entre sí.

---

## 5. Componentes

### 5.1 Componentes existentes (`lib/components/ui/`)

| Componente | Archivo | Uso |
|------------|---------|-----|
| Button | `Button.svelte` | 5 variantes (primary=bg-foreground, secondary, ghost, danger, success), 3 tamaños |
| Card | `Card.svelte` | Contenedor con borde + shadow-soft + hover-lift |
| Modal | `Modal.svelte` | Overlay con backdrop blur, animate-fade-scale, 3 tamaños |
| Badge | `Badge.svelte` | 5 variantes suaves (success, warning, danger, neutral, primary) |
| Avatar | `Avatar.svelte` | Circular con iniciales, color determinístico, ring-2 |
| AvatarGroup | `AvatarGroup.svelte` | Superposición -8px con burbuja +N |
| Sidebar | `Sidebar.svelte` | Glassmorphism, items filtrados por permisos, colapsable |
| ThemeToggle | `ThemeToggle.svelte` | Rotación de icono al cambiar tema |
| FormField | `FormField.svelte` | Label + input/select + error, focus glow |
| Callout | `Callout.svelte` | Banner informativo con icono SVG + botón cerrar |

### 5.2 Componentes del dashboard (`lib/features/dashboard/components/`)

| Componente | Archivo | Uso |
|------------|---------|-----|
| KpiCard | `KpiCard.svelte` | Label + número + trend badge + sparkline SVG |
| AreaChart | `AreaChart.svelte` | Gráfico de área responsivo con curva Catmull-Rom, crosshair, tooltip |
| DonutChart | `DonutChart.svelte` | Dona SVG con paleta categórica, padAngle, leyenda |
| ProgressRing | `ProgressRing.svelte` | Anillo con color dinámico por umbral |
| ActivityFeed | `ActivityFeed.svelte` | Timeline vertical desde bitácora real |
| SummaryTable | `SummaryTable.svelte` | Tabla con hover, avatares, badges |

### 5.3 Reglas de componentes

1. **Ningún componente tiene datos mock hardcodeados dentro** — todos
   reciben datos por props desde la página.

2. **Props tipadas con TypeScript** — sin `any`.

3. **Estados completos**: loading (skeleton), empty (mensaje accionable),
   error (mensaje claro). Nunca mostrar una pantalla vacía sin explicación.

4. **Accesibilidad**: `aria-label` en iconos SVG, `aria-current="page"` en
   enlaces activos, `role="dialog"` en modales, focus visible con
   `focus-visible:shadow-glow`.

---

## 6. Layout

### 6.1 Shell de la aplicación

```
┌─────────┬──────────────────────────────────┐
│         │ Header (h-14, breadcrumb + search + theme + logout) │
│ Sidebar ├──────────────────────────────────┤
│ (w-60)  │                                  │
│         │ Main content (scroll-y-auto)     │
│         │                                  │
└─────────┴──────────────────────────────────┘
```

- Sidebar: `w-60` (240px) expandible, `w-[52px]` colapsado.
- Header: `h-14` (56px), fijo, plano (sin glass/blur).
- Main: `overflow-y-auto`, padding `p-6 md:p-8`.

### 6.2 Bento grid (dashboard)

- KPIs: 4 columnas en desktop, 2 en mobile.
- Gráfico principal: 2/3 del ancho + donut 1/3.
- Actividad: 2/3 + widgets 1/3, altura fija con scroll interno.
- Tabla: ancho completo al final.
- `gap-4` entre tarjetas, `p-5` interno.

### 6.3 Tablas

- Headers: `text-[11px] font-medium uppercase tracking-wide text-foreground-subtle`.
- Filas: `hover:bg-surface-hover/50`, `border-b border-border/50`.
- Números: alineados a la derecha, `font-mono tabular-nums`.
- Badges de estado en columna dedicada.
- Paginación: Anterior/Siguiente al pie, `text-xs text-foreground-subtle`.

### 6.4 Modales

- Backdrop: `bg-black/50 backdrop-blur-sm` (no `bg-black/60`).
- Container: `animate-fade-scale rounded-3xl shadow-floating`.
- Header: `border-b border-border px-6 py-4`, título `text-lg font-bold`.
- Body: `px-6 py-5`.
- Close: botón `h-8 w-8` con icono X.

---

## 7. Gráficos

### 7.1 Reglas generales

1. **SVG nativo** (sin librerías pesadas) — control total del estilo.
2. **Curvas suaves** — Catmull-Rom → Bezier, nunca zigzag crudo.
3. **Gradientes reales** — `linearGradient` con stops de opacidad decreciente.
4. **Ticks bonitos** — redondear a múltiplos limpios (25/50/100/500), máx 4-5 ticks.
5. **Crosshair + tooltip** — línea vertical + círculo + tarjeta flotante al hover.
6. **Responsivo** — `ResizeObserver` para medir el contenedor real.
7. **Accesibilidad** — `aria-label` describiendo la tendencia.
8. **Animación** — `stroke-dashoffset` 700ms ease-out (respeta `prefers-reduced-motion`).

### 7.2 Paleta categórica

Usar siempre esta paleta para gráficos categóricos (donas, barras):

```
const CHART_PALETTE = [
  '0 112 243',    // Geist blue (primary)
  '59 130 246',   // blue-400
  '14 165 233',   // sky-500
  '100 116 139',  // slate-500 (neutro)
  '148 163 184',  // slate-400 (neutro claro)
];
```

---

## 8. Estados

### 8.1 Loading (skeleton)

- Usar clase `.skeleton` (shimmer animado, respeta reduced-motion).
- El skeleton debe tener el mismo layout que el contenido final.
- Simular un delay de 400ms al montar para poder visualizarlo.

### 8.2 Empty state

- Icono en círculo `bg-surface-muted` (28px).
- Mensaje en `text-sm text-foreground-muted`.
- Botón de acción accionable (ej: "Crear departamento").

### 8.3 Error

- Banner `border-danger/30 bg-danger/10` con `role="alert"`.
- Texto en `text-sm text-danger`.
- Nunca mostrar stack traces al usuario.

### 8.4 Success

- Badge `badge-success` con check icon.
- Texto consistente: "Usuario creado" (no "Operación exitosa").

---

## 9. Microinteracciones

| Elemento | Interacción | Duración |
|----------|-------------|----------|
| Button hover | `hover:bg-foreground-muted` | 150ms |
| Button active | `active:scale-[0.98]` | instant |
| Card hover | `translateY(-1px) + shadow-lg` | 200ms |
| Modal entrance | `scale(0.97) + translateY(8px) → 1, 0` | 180ms |
| Sidebar collapse | `w-60 → w-[52px]` | 200ms |
| Theme toggle | Icon rotation 180deg | 300ms |
| Input focus | `shadow-glow` (ring azul) | 150ms |
| Tabla hover | `bg-surface-hover/50` | 150ms |
| Sparkline | stroke-dashoffset animation | 700ms |
| AreaChart | stroke-dashoffset animation | 700ms |

---

## 10. Responsividad

| Breakpoint | Comportamiento |
|------------|----------------|
| ≥1280px (desktop) | Grid completo, sidebar expandido, 4 KPIs en fila |
| 768-1023px (tablet) | 2 columnas, tarjetas grandes a ancho completo |
| ≤640px (mobile) | 1 columna, sidebar drawer, KPIs en 2 cols, tabla → cards |

Reglas:
- **Mobile-first**: diseñar desde 375px y expandir.
- **Sin scroll horizontal** no intencional en ningún breakpoint.
- **Tablas en mobile**: scroll horizontal dentro de la tabla, o transformación a cards.
- **Gráficos fluidos**: `width: 100%` con contenedor que controla el alto.

---

## 11. Accesibilidad

1. **Contraste AA mínimo** en todo texto sobre fondo, incluidos labels grises.
2. **Foco visible**: `:focus-visible { box-shadow: var(--shadow-glow); }`.
3. **Navegación por teclado**: todos los controles interactivos accesibles con Tab.
4. **ARIA**: `role="navigation"` en sidebar, `role="dialog"` + `aria-modal="true"` en modales,
   `aria-current="page"` en enlaces activos, `aria-label` en iconos SVG de gráficos.
5. **`prefers-reduced-motion`**: desactivar shimmer, animaciones de entrada y transiciones.
6. **Estados con color + texto**: nunca usar solo color para indicar estado
   (accesibilidad para daltonismo). Badge siempre lleva texto + color + icono.

---

## 12. Checklist para nuevos componentes

Antes de crear un componente nuevo, verifica:

- [ ] ¿Existe ya un componente similar en `lib/components/ui/` que pueda extender?
- [ ] ¿Usa los tokens del design system (no colores hardcoded)?
- [ ] ¿Tiene estado de loading (skeleton)?
- [ ] ¿Tiene estado de empty (mensaje accionable)?
- [ ] ¿Tiene estado de error (mensaje claro)?
- [ ] ¿Es responsivo (mobile-first)?
- [ ] ¿Tiene `aria-label` en elementos no textuales?
- [ ] ¿Respeta `prefers-reduced-motion`?
- [ ] ¿Usa `tabular-nums` en números?
- [ ] ¿No tiene datos hardcodeados (todo por props)?
- [ ] ¿Está tipado con TypeScript (sin `any`)?

---

## 13. Referencias de inspiración

- **Vercel Dashboard**: https://vercel.com/dashboard — referencia directa de layout, densidad, microinteracciones.
- **Vercel Analytics**: https://vercel.com/docs/analytics — referencia de gráficos y KPIs.
- **Linear**: densidad de información elegante, microinteracciones sutiles, tipografía cuidada.
- **Apple HIG**: claridad, jerarquía, feedback inmediato, consistencia.
- **Dribbble/Pinterest**: busca "admin dashboard" para inspiración de layouts bento y tratamiento de datos.
