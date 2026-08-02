import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

vi.mock('$env/dynamic/public', () => ({ env: {} }));
vi.mock('$app/environment', () => ({ browser: true, dev: true, building: false, version: 'test' }));
