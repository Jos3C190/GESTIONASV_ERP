import { describe, expect, it } from 'vitest';
import {
  CARTO_BASEMAP_ATTRIBUTION,
  cartoBasemapUrl,
  cartoTileLayerOptions,
  isCartoBasemapConfigured
} from './maps';

describe('CARTO basemap configuration', () => {
  it('requires a non-empty CARTO key', () => {
    expect(isCartoBasemapConfigured('')).toBe(false);
    expect(isCartoBasemapConfigured('   ')).toBe(false);
    expect(() => cartoBasemapUrl('light', '')).toThrow('PUBLIC_CARTO_BASEMAP_API_KEY is required');
  });

  it('builds authenticated light and dark tile URLs', () => {
    expect(cartoBasemapUrl('light', ' key/with spaces ')).toBe(
      'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png?key=key%2Fwith%20spaces'
    );
    expect(cartoBasemapUrl('dark', 'carto-key')).toBe(
      'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?key=carto-key'
    );
  });

  it('keeps the required OpenStreetMap and CARTO attribution visible', () => {
    const options = cartoTileLayerOptions();

    expect(options.attribution).toBe(CARTO_BASEMAP_ATTRIBUTION);
    expect(options.attribution).toContain('OpenStreetMap');
    expect(options.attribution).toContain('CARTO');
    expect(options.maxZoom).toBe(20);
  });
});
