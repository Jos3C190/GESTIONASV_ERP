import { defineEnvVars } from '@sveltejs/kit/env';

/** Un valor opcional: vacío cuando la variable no está definida. */
const optional = (value: string | undefined): string => value?.trim() ?? '';

export const variables = defineEnvVars({
  PUBLIC_API_URL: {
    public: true,
    description: 'URL base de la API; por defecto, la del entorno local.',
    schema: (value: string | undefined): string => value?.trim() || 'http://localhost:8000'
  },
  PUBLIC_CARTO_BASEMAP_API_KEY: {
    public: true,
    static: true,
    description: 'Clave del mapa base de CARTO (opcional).',
    schema: optional
  },
  PUBLIC_GOOGLE_MAPS_API_KEY: {
    public: true,
    static: true,
    description: 'Clave de Google Maps (opcional).',
    schema: optional
  }
});
