# Solución de Problemas y Preguntas Frecuentes (Troubleshooting & FAQ)

> **Versión:** `v1.0.0` | **Última actualización:** `22/07/2026`  

Este documento reúne las soluciones a los problemas más comunes encontrados durante el desarrollo local, ejecución con Docker y despliegue del ERP System.

---

## 1. Problemas de Docker y Base de Datos (PostgreSQL)

### 1.1 El contenedor de PostgreSQL no inicia o marca "Unhealthy"

**Síntomas:**
El backend falla al iniciar indicando `CannotConnectNowError` o `ConnectionRefusedError: [Errno 111] Connect call failed ('127.0.0.1', 5432)`.

**Causas comunes:**
- El puerto `5432` está ocupado por una instancia local de PostgreSQL ejecutándose fuera de Docker.
- El contenedor de Postgres no ha completado su proceso de inicialización (healthcheck en progreso).

**Solución:**
1. Verificar si hay un servicio de PostgreSQL corriendo localmente en el host:
   - **Windows (PowerShell):** `Get-Service -Name *postgres*` (detenerlo con `Stop-Service postgresql-x64-16` si aplica).
   - **Linux/macOS:** `sudo systemctl stop postgresql` o `brew services stop postgresql`.
2. Verificar el estado de salud del contenedor:
   ```bash
   docker compose ps
   ```
3. Ver los logs de PostgreSQL:
   ```bash
   docker compose logs db --tail=50
   ```

---

### 1.2 Puertos ocupados (5432, 8000, 5173)

**Síntomas:**
`Error response from daemon: driver failed programming external connectivity on endpoint erp-frontend: Bind for 0.0.0.0:5173 failed: port is already allocated`.

**Solución:**
Identificar y liberar el proceso que está ocupando el puerto:

- **Windows PowerShell:**
  ```powershell
  Get-NetTCPConnection -LocalPort 5173 | Select-Object OwningProcess
  Stop-Process -Id <PID> -Force
  ```
- **macOS / Linux:**
  ```bash
  lsof -i :5173
  kill -9 <PID>
  ```

---

### 1.3 Limpieza total y reinicio del entorno (Wipe Destructivo)

Si la base de datos o el volumen de Docker queda en un estado corrupto o inconsistente:

```bash
make clean
make setup
```

O manualmente:
```bash
docker compose down -v --remove-orphans
docker compose up -d --build
docker compose exec backend python -m seed.seed_data
```

La semilla guarda el marcador `seed.grupo_lorena.initialized` en `app_meta` y,
después del primer setup, los reinicios normales no modifican datos de negocio.
Para reconciliar deliberadamente los registros canónicos use
`FORCE_SEED=true`; esta opción puede restaurar registros de demostración enviados
a la papelera y no debe habilitarse de forma permanente.

---

## 2. Problemas de Backend y Alembic (FastAPI)

### 2.1 Error de Alembic: "Multiple head revisions present"

**Síntomas:**
Al intentar ejecutar `alembic upgrade head`, el sistema lanza:
`alembic.util.exc.CommandError: Multiple head revisions are present for given argument 'head'`.

**Causa:**
Dos desarrolladores crearon migraciones paralelas independientemente en ramas distintas de Git.

**Solución:**
Unificar las revisiones en un punto de fusión (merge revision):

```bash
docker compose exec backend alembic merge heads -m "merge parallel migrations"
docker compose exec backend alembic upgrade head
```

---

### 2.2 Error 401 Unauthorized en Swagger UI (`/docs`)

**Síntomas:**
Los endpoints en Swagger responden `401 Unauthorized` a pesar de haber ingresado credenciales.

**Solución:**
1. Ir al botón **Authorize** (candado verde) en la parte superior derecha de `http://localhost:8000/docs`.
2. En el campo `username` ingresar: `superadmin`
3. En el campo `password` ingresar: `Cambio!Seguro2026`
4. Presionar **Authorize** y cerrar el modal. El token `Bearer` quedará inyectado en todas las peticiones posteriores de Swagger.

---

### 2.3 ¿Cómo ver las consultas SQL en consola? (SQLAlchemy Echo Log)

Para inspeccionar las sentencias SQL reales ejecutadas en la base de datos:

1. Editar el archivo `.env`:
   ```env
   ECHO_SQL=true
   LOG_LEVEL=DEBUG
   ```
2. Reiniciar el contenedor del backend: `docker compose restart backend`.
3. Ver los logs en tiempo real: `make logs`.

---

## 3. Problemas de Frontend y SvelteKit 5

### 3.1 Errores de Runes en Svelte 5 (`$state is not defined`)

**Síntomas:**
El compilador marca error de sintaxis al utilizar `$state()`, `$derived()`, o `$effect()`.

**Causas:**
- La extensión de Svelte en el editor no está actualizada para Svelte 5.
- El archivo `.svelte` se está compilando en modo Svelte 4.

**Solución:**
- Asegurarse de tener instalada la extensión oficial **Svelte for VS Code** (versión 108+).
- En Svelte 5, las Runes son palabras clave globales del compilador, **no requieren importación** (`import { state } from 'svelte'` es incorrecto).

---

### 3.2 Error de CORS en peticiones del Frontend al Backend

**Síntomas:**
En la consola del navegador: `Access to fetch at 'http://localhost:8000/api/v1/...' from origin 'http://localhost:5173' has been blocked by CORS policy`.

**Solución:**
1. Abrir `.env` en la raíz del proyecto.
2. Verificar que `BACKEND_CORS_ORIGINS` incluya el puerto del frontend:
   ```env
   BACKEND_CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
   ```
3. Reiniciar el backend: `docker compose restart backend`.

---

## 4. Preguntas Frecuentes (FAQ)

### ¿Cómo re-sembrar la base de datos sin borrar las tablas?
Ejecuta el script de semilla directo:
```bash
make seed
```
Este comando solo actúa si el bootstrap no tiene marcador. Para reconciliar
deliberadamente el dataset canónico, ejecute `FORCE_SEED=true make seed`; revise
antes la papelera porque esa operación puede restaurar registros de demostración.

---

### ¿Cómo restablecer la contraseña del usuario `superadmin`?
Puedes ejecutar un script rápido interactivo desde el contenedor de backend:
```bash
docker compose exec backend python -c "
import asyncio
from app.infrastructure.db.session import AsyncSessionLocal
from app.infrastructure.db.models.user import UserModel
from app.core.security import get_password_hash
from sqlalchemy import select

async def reset_pass():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(UserModel).where(UserModel.username == 'superadmin'))
        user = result.scalar_one_or_none()
        if user:
            user.hashed_password = get_password_hash('Cambio!Seguro2026')
            await session.commit()
            print('Contraseña de superadmin restablecida con éxito.')
        else:
            print('Usuario superadmin no encontrado.')

asyncio.run(reset_pass())
"
```

---

### ¿Dónde puedo consultar los logs de los contenedores?
```bash
make logs              # Ver logs de todos los servicios
docker compose logs -f backend   # Ver logs continuos del backend
docker compose logs -f frontend  # Ver logs continuos del frontend
```
