import { describe, expect, it } from 'vitest';
import { documentState, vehicleAlerts } from './alerts';
import { DEMO_VEHICLES, type FleetVehicle } from './mock-data';

const base = DEMO_VEHICLES.find((vehicle) => vehicle.id === 'FL-006')!;
const vehicle = (patch: Partial<FleetVehicle>): FleetVehicle => ({ ...base, ...patch });

describe('fleet alerts', () => {
  it('reports nothing when documents and service are far away', () => {
    expect(vehicleAlerts(base)).toEqual([]);
  });

  it('warns about documents expiring soon with a relative label', () => {
    const alerts = vehicleAlerts(
      vehicle({ documents: [{ kind: 'insurance', expires: '2026-11-02' }] })
    );
    expect(alerts).toEqual([{ tone: 'warning', label: 'Seguro vence en 5 días', days: 5 }]);
  });

  it('uses hoy and mañana for the closest dates', () => {
    expect(
      vehicleAlerts(vehicle({ documents: [{ kind: 'insurance', expires: '2026-10-28' }] }))[0]
        ?.label
    ).toBe('Seguro vence hoy');
    expect(vehicleAlerts(vehicle({ serviceDue: '2026-10-29' }))[0]?.label).toBe('Servicio mañana');
  });

  it('puts expired items first and agrees the label with the document gender', () => {
    const alerts = vehicleAlerts(
      vehicle({
        serviceDue: '2026-10-31',
        documents: [
          { kind: 'inspection', expires: '2026-10-20' },
          { kind: 'insurance', expires: '2026-10-01' }
        ]
      })
    );
    expect(alerts.map((alert) => alert.label)).toEqual([
      'Seguro vencido',
      'Revisión técnica vencida',
      'Servicio en 3 días'
    ]);
  });

  it('describes document state for the detail list', () => {
    expect(documentState({ kind: 'insurance', expires: '2026-10-27' })).toEqual({
      tone: 'danger',
      label: 'Vencido'
    });
    expect(documentState({ kind: 'insurance', expires: '2027-10-27' }).label).toBe('Vigente');
  });
});
