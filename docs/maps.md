# Mapas base de sucursales

El ERP utiliza Leaflet con los mapas base raster de CARTO. Google Maps permanece
como integración opcional y no es necesario configurarlo para usar los mapas de
sucursales.

## Clave de CARTO

CARTO exige una clave propia para todas las solicitudes de mapas base. Solicítela
en <https://carto.com/basemaps/apikey/> indicando los dominios donde funcionará el
ERP, por ejemplo `localhost:5173` para desarrollo y el dominio HTTPS de producción.

Configure la clave en el archivo `.env` local o en las variables del despliegue:

```dotenv
PUBLIC_CARTO_BASEMAP_API_KEY=clave_emitida_por_carto
```

La clave se incorpora al frontend durante la construcción productiva. Después de
modificarla es necesario reconstruir el frontend. En desarrollo basta con reiniciar
el servicio. Si el navegador conserva mosaicos antiguos con la marca de agua, haga
una recarga forzada después del reinicio.

La clave es visible para el navegador por diseño. Debe registrarse para los dominios
del ERP, vigilar su consumo y no reutilizarse en proyectos ajenos. No debe colocarse
una clave real en `.env.example` ni en Git.

## Cumplimiento

Todos los componentes usan una configuración común que:

- incorpora la clave mediante el parámetro `key`;
- conserva visible la atribución de OpenStreetMap y CARTO;
- evita solicitar mosaicos cuando la clave no está configurada;
- mantiene Google Maps como alternativa estrictamente opcional.

Las condiciones vigentes de CARTO y sus límites de uso deben revisarse antes de un
despliegue comercial: <https://carto.com/legal/basemap-terms/>.
