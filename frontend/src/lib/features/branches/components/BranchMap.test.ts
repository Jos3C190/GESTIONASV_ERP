import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import BranchMap from './BranchMap.svelte';

describe('BranchMap CARTO configuration', () => {
  it('shows a controlled unavailable state when no basemap key is configured', async () => {
    render(BranchMap, { branches: [], selectedId: null });

    expect(
      await screen.findByText(
        'El mapa no está disponible porque el proveedor CARTO aún no está configurado.'
      )
    ).toBeInTheDocument();
    expect(document.querySelector('#leaflet-script')).not.toBeInTheDocument();
  });
});
