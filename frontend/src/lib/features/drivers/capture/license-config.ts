import type {
  CaptureConfig,
  CaptureRules,
  CaptureValues
} from '$lib/features/document-capture/types';
import { driversApi, type Driver, type LicenseValues } from '../api';

export const EMPTY_VALUES: LicenseValues = {
  license_class: null,
  expires: null,
  number: null,
  surnames: null,
  given_names: null,
  dui: null,
  issued: null,
  birth: null,
  control_number: null
};

const FIELDS: CaptureConfig<Driver>['fields'] = {
  license_class: { label: 'Clase', hint: 'Como aparece, por ejemplo D LIVIANA' },
  expires: { label: 'Vence', hint: 'MM-AAAA' },
  number: { label: 'Número de licencia' },
  surnames: { label: 'Apellidos' },
  given_names: { label: 'Nombres' },
  dui: { label: 'DUI', hint: '########-#' },
  issued: { label: 'Expedición', hint: 'DD.MM.AAAA' },
  birth: { label: 'Nacimiento', hint: 'DD.MM.AAAA' },
  control_number: { label: 'Número de control' }
};

export const licenseCaptureRules: CaptureRules = {
  /** Grouped by what the person checks together, not by the side each value is printed on. */
  groups: [
    { title: 'Datos del titular', fields: ['surnames', 'given_names', 'dui', 'birth'] },
    {
      title: 'Datos de la licencia',
      fields: ['license_class', 'number', 'expires', 'issued', 'control_number']
    }
  ],
  expected: { front: ['expires', 'number', 'dui'], back: ['issued'] },
  unreadableCodes: new Set([
    'expiry_invalid',
    'number_missing',
    'number_format',
    'dui_missing',
    'dui_format',
    'issued_invalid'
  ]),
  missingPhotos: 'Faltan fotos de la licencia.',
  mismatchBlocked: 'Los datos no coinciden con el empleado.'
};

export function licenseCaptureConfig(driverId: string): CaptureConfig<Driver> {
  return {
    ...licenseCaptureRules,
    dialogTitle: 'Capturar licencia de conducir',
    title: 'Licencia de conducir',
    documentName: 'la licencia',
    filePrefix: 'licencia',
    fields: FIELDS,
    overridePermission: 'drivers:license_override',
    mismatchStop:
      'Estos datos no coinciden con el empleado. Corrígelos o pide autorización a un administrador.',
    acknowledge: 'Revisé los avisos y los datos coinciden con la licencia.',
    confirmLabel: 'Confirmar licencia',
    confirmError: 'No se pudo confirmar la licencia.',
    api: {
      open: () => driversApi.openCapture(driverId),
      get: (captureId) => driversApi.getCapture(driverId, captureId),
      startUpload: (captureId, side, data) =>
        driversApi.startCaptureUpload(driverId, captureId, side, data),
      completeUpload: (captureId, side) =>
        driversApi.completeCaptureUpload(driverId, captureId, side),
      preview: (captureId, side) => driversApi.capturePreview(driverId, captureId, side),
      check: async (captureId, values: CaptureValues) => ({
        issues: await driversApi.checkCapture(driverId, captureId, values as LicenseValues)
      }),
      confirm: (captureId, data) =>
        driversApi.confirmCapture(driverId, captureId, {
          ...data,
          values: data.values as LicenseValues
        }),
      cancel: (captureId) => driversApi.cancelCapture(driverId, captureId)
    }
  };
}
