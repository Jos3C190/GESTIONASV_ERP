import { api, type TrackingAlertKind, type TrackingAlertOut } from '$lib/api/client';
import { company } from '$lib/stores/company.svelte';
import { permissions } from '$lib/stores/permissions.svelte';

export const ALERT_KIND_LABELS: Record<TrackingAlertKind, string> = {
  arrived: 'Llegada',
  delayed: 'Retraso',
  long_stop: 'Parada larga',
  gps_lost: 'Sin señal GPS',
  off_route: 'Fuera de ruta'
};

const POLL_MS = 30_000;

/** Ordena primero lo crítico y lo no reconocido; dentro de cada grupo, lo más reciente. */
export function sortAlerts(items: TrackingAlertOut[]): TrackingAlertOut[] {
  const rank = { critical: 0, warning: 1, info: 2 } as const;
  return [...items].sort(
    (a, b) =>
      Number(!!a.acknowledged_at) - Number(!!b.acknowledged_at) ||
      rank[a.severity] - rank[b.severity] ||
      b.opened_at.localeCompare(a.opened_at)
  );
}

/**
 * Alertas abiertas de los traslados de las sucursales del usuario. Una sola consulta
 * periódica alimenta el indicador del encabezado y la pestaña de Seguimiento.
 */
function createAlertsStore() {
  let items = $state<TrackingAlertOut[]>([]);
  let monitorActive = $state(true);
  let error = $state<string | null>(null);
  let timer: ReturnType<typeof setInterval> | null = null;
  let subscribers = 0;
  let loadedFor: string | null = null;

  const allowed = () => permissions.hasPermission('tracking:read') && !!company.id;

  async function refresh() {
    if (!allowed()) {
      items = [];
      return;
    }
    const companyId = company.id;
    try {
      const result = await api.tracking.alerts('open');
      if (company.id !== companyId) return;
      items = sortAlerts(result.items);
      monitorActive = result.monitor_active;
      loadedFor = companyId;
      error = null;
    } catch {
      error = 'No se pudieron consultar las alertas.';
    }
  }

  return {
    get items() {
      // Al cambiar de empresa no se muestran las alertas de la anterior.
      return loadedFor === company.id ? items : [];
    },
    get unacknowledged() {
      return this.items.filter((item) => !item.acknowledged_at).length;
    },
    get monitorActive() {
      return monitorActive;
    },
    get error() {
      return error;
    },
    refresh,
    async acknowledge(id: string) {
      const updated = await api.tracking.acknowledgeAlert(id);
      items = sortAlerts(items.map((item) => (item.id === id ? { ...item, ...updated } : item)));
    },
    /** Empieza a consultar mientras haya algún componente que lo use. */
    subscribe(): () => void {
      subscribers++;
      if (subscribers === 1) {
        void refresh();
        timer = setInterval(() => void refresh(), POLL_MS);
      }
      return () => {
        subscribers--;
        if (subscribers === 0 && timer) {
          clearInterval(timer);
          timer = null;
        }
      };
    }
  };
}

export const trackingAlerts = createAlertsStore();
