# GPS en un servidor en la nube

Guía para pasar la conexión de GPS de la red local a un servidor con dirección pública. El desarrollo local no usa nada de esto: sigue con `compose.yaml` y `TRACCAR_PUBLIC_URL` apuntando a la IP de la PC.

**Estado:** preparado, sin desplegar. Se validó la configuración y el paso por Nginx en local; nunca se ha ejecutado en un servidor real.

## Cómo queda

| Quién | Entra por | Cifrado |
|---|---|---|
| Teléfono con la app | `https://gps.tuempresa.com` → Nginx → `traccar:5055` | Sí, con el TLS del despliegue |
| GPS instalado | `gps.tuempresa.com:<puerto del modelo>` → `traccar` | Depende del modelo; muchos no lo admiten |
| Usuarios del ERP | El dominio del ERP → Nginx | Sí, con el TLS del despliegue |
| Backend del ERP | `traccar:8082`, red interna de Docker | No sale del servidor |

La interfaz web de Traccar (`8082`) y el puerto de la app (`5055`) no se publican en producción.

## Antes de desplegar

Hay que decidir esto; el repositorio no lo resuelve:

1. **Dónde alojarlo.** Traccar necesita un servidor siempre encendido con puertos abiertos, como un VPS.
2. **TLS.** `compose.prod.yaml` asume que el TLS termina antes de Nginx, igual que para el resto del ERP. Hay que resolverlo con un balanceador o un proxy del proveedor, para el dominio del ERP y para `gps.tuempresa.com`.
3. **Modelos de GPS.** Solo los que se vayan a comprar. Antes de comprar, conviene confirmar el puerto en <https://www.traccar.org/devices/> y si el modelo admite cifrado.
4. **Cuánto tiempo guardar las posiciones.** Ver "Pendiente".
5. **Tratamiento de datos.** Se guarda la ubicación de personas: quién la ve, cuánto tiempo se conserva y cómo se avisa a los conductores.

## Pasos

1. **DNS:** apunta `gps.tuempresa.com` al servidor. Nginx reconoce cualquier nombre que empiece por `gps.`. Usa un dominio y no una IP: al cambiar de servidor no habrá que reconfigurar cada equipo.
2. **Variables** en el `.env` del servidor:

   ```bash
   TRACCAR_URL=http://traccar:8082
   TRACCAR_USER=<cuenta de servicio>
   TRACCAR_PASSWORD=<contraseña propia>
   TRACCAR_PUBLIC_URL=https://gps.tuempresa.com
   TRACCAR_TRACKER_MODELS=gt06,teltonika
   ```

   `TRACCAR_TRACKER_MODELS` decide qué modelos ofrece el asistente. Sin definirla, en producción no ofrece ninguno.
3. **Puertos de GPS:** en `compose.prod.yaml`, servicio `traccar`, descomenta solo los puertos de esos mismos modelos y cambia `ports: !override []` por `ports: !override`. Ábrelos también en el firewall del proveedor.
4. **Arranque:**

   ```bash
   docker compose -f compose.yaml -f compose.prod.yaml --profile prod --profile tracking up -d --build
   ```

## Comprobar

1. Desde fuera del servidor, `https://gps.tuempresa.com/?id=prueba-sin-registrar&lat=13.3&lon=-87.8` debe responder `400`: es Traccar rechazando un identificador que no existe. Un `502` significa que Traccar no está corriendo.
2. Los puertos `8082`, `5055` y `5432` no deben responder desde fuera.
3. Conecta un teléfono con datos móviles, sin Wi-Fi, y sigue el asistente hasta "¡Listo!".
4. Conecta un GPS real de cada modelo elegido. Este paso nunca se ha probado.

## Riesgos que siguen ahí

- **Sin contraseña al reportar:** quien conozca un identificador puede enviar posiciones falsas. Los de teléfono son aleatorios; el IMEI de un GPS es más predecible. Nginx limita a 10 peticiones por segundo por origen, y solo protege la ruta de los teléfonos.
- **Límite compartido:** si hay un proxy delante de Nginx, todos llegan con su misma IP y comparten ese límite. Para unos 14 vehículos sobra; con muchos más, hay que configurar la IP real.
- **GPS sin cifrar:** los puertos de GPS van directo a Traccar, sin límite ni cifrado propios.

## Simulador para demostraciones

El simulador permanece apagado por defecto. Para habilitarlo manteniendo
`ENVIRONMENT=production`, configure ambas variables en el backend y en
`tracking-monitor`, y recree esos servicios con la nueva versión del código:

```dotenv
TRACKING_SIMULATOR_ENABLED=true
TRACKING_SIMULATOR_ALLOW_PRODUCTION=true
```

El panel conserva el permiso `tracking:simulate` y el alcance por empresa y
sucursal. Las posiciones, recorridos y alertas simuladas siguen identificadas
como tales; durante una sesión, el seguimiento del vehículo usa su GPS virtual.
Utilice vehículos destinados a pruebas y finalice las sesiones al terminar.
Para deshabilitarlo, establezca `TRACKING_SIMULATOR_ENABLED=false` en ambos
servicios; el monitor cierra las sesiones abiertas en su siguiente ciclo.

En el VPS local de esta instalación, `python -B scripts/enable-vps-tracking-simulator.py`
habilita la opción sobre la imagen actual y comprueba que producción y las cookies
seguras sigan activas. `--disable` revierte las banderas. Para mantener la opción
después de las actualizaciones automáticas, los cambios de configuración del código
deben publicarse también en `develop`; el script no publica commits.

## Pendiente

- **Borrado de posiciones antiguas.** La [referencia de configuración de Traccar](https://www.traccar.org/configuration-file/) no documenta una opción para esto, y `database.positionPeriod` solo limita consultas, no borra. La tabla crecerá hasta que se defina una tarea propia, con respaldo previo y probada con datos de copia.
- **Base de datos.** Traccar comparte el servidor de Postgres del ERP en una base propia. Su [guía de Docker](https://www.traccar.org/docker/) recomienda TimescaleDB o MySQL para producción, así que conviene medir el crecimiento antes de crecer en flota.
- **Captura de licencias.** `compose.prod.yaml` apaga el lector (`VLM_ENABLED=false`) porque necesita GPU, y un VPS normal no la tiene. En ese caso, los datos de la licencia se escriben a mano.
