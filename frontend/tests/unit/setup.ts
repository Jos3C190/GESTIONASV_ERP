import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

vi.mock('$app/env/public', () => ({
  PUBLIC_API_URL: 'http://localhost:8000',
  PUBLIC_CARTO_BASEMAP_API_KEY: '',
  PUBLIC_GOOGLE_MAPS_API_KEY: ''
}));
vi.mock('$app/env', () => ({ browser: true, dev: true, building: false, version: 'test' }));
