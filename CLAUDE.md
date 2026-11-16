# CLAUDE.md

**GestionaSV**: ERP multiempresa y multisucursal (FastAPI + SvelteKit 5 + PostgreSQL 16 + Docker).
Empresa de demostración: Grupo Lorena (El Salvador). Área en construcción: ventas y facturación electrónica (DTE).

## Reglas del proyecto

Las reglas de arquitectura, frontend, localización, seguridad y el ciclo de ingeniería están en
`.agents/AGENTS.md` y son obligatorias:

@.agents/AGENTS.md

## Comandos

Usar Git Bash en Windows. Todo corre en Docker Compose.

- `make up` / `make down`: levantar o detener el entorno de desarrollo.
- `make test`: todas las pruebas; `make test-backend`, `make test-frontend`, `make test-unit`.
- `make lint` y `make fmt`: lint y formato de backend y frontend.
- `make reset-db` y `make clean` son DESTRUCTIVOS: no ejecutarlos sin confirmación explícita.

## Forma de trabajo (continuidad entre sesiones)

La sesión puede cortarse en cualquier momento al llegar al límite de uso, y el trabajo puede
continuarlo otra sesión sin contexto previo. Por eso:

1. **Plan en archivo.** Todo plan de implementación se escribe en `PLAN.md` (raíz del proyecto)
   antes de tocar código, en pasos pequeños con casillas `- [ ]` / `- [x]`. Cada paso indica los
   archivos que toca y cómo verificar que está terminado. Si `PLAN.md` ya existe con un plan
   en curso, se continúa ese plan en lugar de crear otro.
2. **Progreso continuo.** Al terminar cada paso: marcarlo `[x]` en `PLAN.md` y hacer un commit
   `Paso N: <descripción>` antes de empezar el siguiente. No acumular cambios grandes sin commit.
3. **Estado actual.** Mantener al final de `PLAN.md` una sección `## Estado actual` con: paso en
   curso y lo que falta, decisiones tomadas y su motivo, problemas encontrados y comandos útiles.
   Escribirla para que la entienda una sesión nueva sin contexto.
4. **Instrucciones del usuario.** Las correcciones o decisiones importantes que dé el usuario
   durante el trabajo se registran también en `PLAN.md`.
5. **Al retomar.** Leer `PLAN.md` completo y revisar `git status` y `git log --oneline -10`. Si hay
   cambios sin commit del paso interrumpido, revisarlos e informar al usuario antes de descartar
   nada. Resumir dónde quedó el trabajo y continuar desde el primer paso pendiente.
6. **Una sola sesión activa** trabaja en este proyecto a la vez.
