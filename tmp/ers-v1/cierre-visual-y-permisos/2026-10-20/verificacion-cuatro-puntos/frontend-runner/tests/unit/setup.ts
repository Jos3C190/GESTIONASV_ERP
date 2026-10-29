import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

vi.mock('$env/dynamic/public', () => ({ env: {} }));
vi.mock('$env/static/public', () => ({
  PUBLIC_CARTO_BASEMAP_API_KEY: '',
  PUBLIC_GOOGLE_MAPS_API_KEY: ''
}));
vi.mock('$app/environment', () => ({ browser: true, dev: true, building: false, version: 'test' }));
