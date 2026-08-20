import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import type { CapacitySummary } from '../types';
import CapacityScopePath from './CapacityScopePath.svelte';

const metric = (utilizationPct: number) => ({
  certified: 120,
  operational: 100,
  occupied: 75,
  reserved: 10,
  projected: 85,
  available: 15,
  utilizationPct
});

const summary: CapacitySummary = {
  scopeType: 'location',
  warehouseId: 'warehouse-1',
  locationId: 'location-1',
  measurementStatus: 'complete',
  status: 'warning',
  limitingMetric: 'weight',
  weight: metric(85),
  volume: metric(60),
  effectiveUtilizationPct: 85,
  unmeasuredHandlingUnits: 0,
  unmeasuredReservations: 0,
  scopePath: [
    {
      scopeType: 'location',
      scopeId: 'location-1',
      code: 'P01',
      name: 'P01',
      measurementStatus: 'complete',
      status: 'warning',
      limitingMetric: 'weight',
      weight: metric(85),
      volume: metric(60),
      effectiveUtilizationPct: 85,
      unmeasuredHandlingUnits: 0,
      unmeasuredReservations: 0
    },
    {
      scopeType: 'capacity_group',
      scopeId: 'rack-a',
      code: 'RACK-A',
      name: 'Rack A',
      measurementStatus: 'complete',
      status: 'available',
      limitingMetric: 'weight',
      weight: metric(50),
      volume: metric(40),
      effectiveUtilizationPct: 50,
      unmeasuredHandlingUnits: 0,
      unmeasuredReservations: 0
    }
  ],
  limitingScope: { scopeType: 'location', scopeId: 'location-1', code: 'P01', name: 'P01' }
};

describe('CapacityScopePath', () => {
  it('shows the physical path and its limiting scope', () => {
    render(CapacityScopePath, { props: { summary } });
    expect(screen.getByText('RACK-A')).toBeInTheDocument();
    expect(screen.getByText('Cuello de botella')).toBeInTheDocument();
    expect(screen.getAllByText(/Ocupado 75 kg/)).toHaveLength(2);
  });
});
