import { render, screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import type { CapacitySummary } from '../types';
import CapacitySummaryPanel from './CapacitySummaryPanel.svelte';

const overCertifiedSummary: CapacitySummary = {
  scopeType: 'warehouse',
  warehouseId: 'warehouse-1',
  locationId: null,
  measurementStatus: 'complete',
  status: 'over_certified',
  limitingMetric: 'weight',
  weight: {
    certified: 100,
    operational: 90,
    occupied: 110,
    reserved: 0,
    projected: 110,
    available: -20,
    utilizationPct: 122.222222
  },
  volume: {
    certified: 50,
    operational: 45,
    occupied: 20,
    reserved: 0,
    projected: 20,
    available: 25,
    utilizationPct: 44.444444
  },
  effectiveUtilizationPct: 122.222222,
  unmeasuredHandlingUnits: 0,
  unmeasuredReservations: 0,
  scopePath: [],
  limitingScope: null
};

describe('CapacitySummaryPanel', () => {
  it('presenta el exceso certificado como peligro de seguridad no autorizable', () => {
    render(CapacitySummaryPanel, { props: { summary: overCertifiedSummary } });

    expect(screen.getByText('Límite certificado excedido')).toHaveClass('text-danger');
    const alert = screen.getByRole('alert');
    expect(within(alert).getByText('Peligro de seguridad')).toBeInTheDocument();
    expect(alert).toHaveTextContent('Ninguna excepción operativa autoriza este exceso');
    expect(alert).toHaveTextContent('Detenga nuevos ingresos');
  });
});
