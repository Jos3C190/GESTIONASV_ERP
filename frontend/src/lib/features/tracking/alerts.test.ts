import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { TrackingAlertOut } from '$lib/api/client';
import AlertsPanel from './AlertsPanel.svelte';
import { sortAlerts } from './alerts.svelte';

function alert(patch: Partial<TrackingAlertOut>): TrackingAlertOut {
  return {
    id: 'a',
    transfer_id: 't1',
    transfer_code: 'TR-1',
    vehicle_code: 'FL-001',
    kind: 'delayed',
    severity: 'warning',
    message: 'Va 35 min atrasado.',
    details: {},
    opened_at: '2026-10-30T14:00:00Z',
    last_seen_at: '2026-10-30T14:00:00Z',
    resolved_at: null,
    acknowledged_at: null,
    ...patch
  };
}

afterEach(() => cleanup());

describe('tracking alerts', () => {
  it('puts unacknowledged critical alerts first', () => {
    const sorted = sortAlerts([
      alert({ id: 'seen', severity: 'critical', acknowledged_at: '2026-10-30T14:05:00Z' }),
      alert({ id: 'info', severity: 'info', kind: 'arrived' }),
      alert({ id: 'gps', severity: 'critical', kind: 'gps_lost' }),
      alert({ id: 'late', opened_at: '2026-10-30T14:10:00Z' })
    ]);
    expect(sorted.map((item) => item.id)).toEqual(['gps', 'late', 'info', 'seen']);
  });

  it('opens the transfer and acknowledges from the panel', async () => {
    const onopen = vi.fn();
    const onacknowledge = vi.fn().mockResolvedValue(undefined);
    render(AlertsPanel, {
      alerts: [alert({ id: 'x' })],
      now: Date.parse('2026-10-30T14:30:00Z'),
      onopen,
      onacknowledge
    });
    expect(screen.getByText('Retraso')).toBeVisible();
    await fireEvent.click(screen.getByText('Va 35 min atrasado.'));
    expect(onopen).toHaveBeenCalledWith(expect.objectContaining({ transfer_id: 't1' }));
    await fireEvent.click(screen.getByRole('button', { name: 'Reconocer' }));
    expect(onacknowledge).toHaveBeenCalledWith(expect.objectContaining({ id: 'x' }));
  });

  it('explains when no alerts can be raised', () => {
    render(AlertsPanel, {
      alerts: [],
      now: Date.now(),
      monitorActive: false,
      onopen: vi.fn(),
      onacknowledge: vi.fn()
    });
    expect(screen.getByText(/no se generan alertas/)).toBeVisible();
  });
});
