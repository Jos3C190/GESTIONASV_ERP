import type {
  CaptureCheck,
  CaptureConfig,
  CaptureRules,
  CaptureState
} from '$lib/features/document-capture/types';
import { fleetApi, type CirculationConfirmed } from '../api';

const FIELDS: CaptureConfig<CirculationConfirmed>['fields'] = {
  plate: { label: 'Placa', wide: true },
  expires: { label: 'Vence', hint: 'MM-AAAA' },
  issued: { label: 'Emisión', hint: 'MM-DD-AAAA' },
  year: { label: 'Año', numeric: true },
  brand: { label: 'Marca' },
  model: { label: 'Modelo' },
  color: { label: 'Color' },
  chassis: { label: 'Número de chasis' },
  engine: { label: 'Número de motor' },
  vin: { label: 'VIN' }
};

/** The API names vehicle columns; the review form names what is printed on the card. */
const FIELD_OF_COLUMN: Record<string, string> = {
  vin: 'vin',
  color: 'color',
  chassis_number: 'chassis',
  engine_number: 'engine'
};

const COLUMN_LABELS: Record<string, string> = {
  vin: 'VIN',
  color: 'color',
  chassis_number: 'chasis',
  engine_number: 'motor'
};

export function filledFields(columns: readonly string[]): string[] {
  return columns.map((column) => FIELD_OF_COLUMN[column] ?? column);
}

/** What to tell the user after confirming, about the vehicle data the card touched. */
export function confirmationNotice(result: {
  filled_fields: string[];
  skipped_fields: string[];
}): string {
  const names = (columns: string[]) =>
    columns.map((column) => COLUMN_LABELS[column] ?? column).join(', ');
  const parts = ['Tarjeta de circulación registrada.'];
  if (result.filled_fields.length > 0) {
    parts.push(`Se completó en el vehículo: ${names(result.filled_fields)}.`);
  }
  if (result.skipped_fields.length > 0) {
    parts.push(
      `No se completó ${names(result.skipped_fields)}: el vehículo está dado de baja o no tienes permiso para editarlo.`
    );
  }
  return parts.join(' ');
}

function forReview<T extends CaptureCheck | CaptureState>(state: T): T {
  return { ...state, fills: filledFields(state.fills ?? []) };
}

export const circulationCaptureRules: CaptureRules = {
  groups: [
    { title: 'Identificación', fields: ['plate', 'expires', 'issued'] },
    {
      title: 'Datos del vehículo',
      fields: ['year', 'brand', 'model', 'color', 'chassis', 'engine', 'vin']
    }
  ],
  expected: { front: ['plate', 'expires'], back: ['year', 'brand', 'model'] },
  unreadableCodes: new Set(['plate_missing', 'expiry_invalid', 'issued_invalid', 'year_invalid']),
  missingPhotos: 'Faltan fotos de la tarjeta.',
  mismatchBlocked: 'Los datos no coinciden con el vehículo.',
  blockingCodes: {
    plate_mismatch:
      'La placa no coincide con la del vehículo. Corrígela si se leyó mal o descarta la captura.'
  }
};

export function circulationCaptureConfig(vehicleId: string): CaptureConfig<CirculationConfirmed> {
  const api = fleetApi.circulationCaptures(vehicleId);
  return {
    ...circulationCaptureRules,
    dialogTitle: 'Capturar tarjeta de circulación',
    title: 'Tarjeta de circulación',
    documentName: 'la tarjeta',
    filePrefix: 'tarjeta-circulacion',
    // El reverso deja mucho en blanco: a ese detector le parece un reflejo.
    ignoredQuality: { back: ['glare'] },
    fields: FIELDS,
    overridePermission: null,
    mismatchStop: 'Estos datos no coinciden con el vehículo.',
    acknowledge: 'Revisé los avisos y los datos coinciden con la tarjeta.',
    confirmLabel: 'Confirmar tarjeta',
    confirmError: 'No se pudo confirmar la tarjeta.',
    fillNote: 'Se completará en el vehículo.',
    api: {
      open: async () => forReview(await api.open()),
      get: async (captureId) => forReview(await api.get(captureId)),
      startUpload: api.startUpload,
      completeUpload: async (captureId, side) =>
        forReview(await api.completeUpload(captureId, side)),
      preview: api.preview,
      check: async (captureId, values) => forReview(await api.check(captureId, values)),
      confirm: (captureId, data) =>
        api.confirm(captureId, {
          values: data.values,
          acknowledged_warnings: data.acknowledged_warnings
        }),
      cancel: api.cancel
    }
  };
}
