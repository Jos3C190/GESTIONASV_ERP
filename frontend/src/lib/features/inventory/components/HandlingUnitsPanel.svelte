<script lang="ts">
  import { goto } from '$app/navigation';
  import { onDestroy, tick } from 'svelte';
  import Badge from '$lib/components/ui/Badge.svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import { listLocations } from '$lib/features/locations/services';
  import type { LocationOut } from '$lib/features/locations/types';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import { inventoryApi } from '../services';
  import { physicalKardexHref } from '../kardex';
  import type { HandlingUnit, PhysicalMeasuresInput, StockStatus } from '../types';
  import GroupedPutawayPanel from './GroupedPutawayPanel.svelte';
  import HandlingUnitLabelDialog from './HandlingUnitLabelDialog.svelte';

  interface Props {
    warehouseId: string;
    contextKey?: string;
    focusHandlingUnitId?: string;
    canVerify?: boolean;
    canReadRetaceos?: boolean;
    canVerifyRetaceos?: boolean;
    canRelease?: boolean;
    canTransfer?: boolean;
    canPrepareSplit?: boolean;
    onverified?: () => void;
  }

  type MeasurementMethod = 'volume' | 'dimensions';
  type MeasurementField = 'weight' | 'volume' | 'length' | 'width' | 'height';

  const STOCK_STATUS_OPTIONS: { value: StockStatus; label: string }[] = [
    { value: 'available', label: 'Disponible' },
    { value: 'quarantine', label: 'Cuarentena' },
    { value: 'blocked', label: 'Bloqueada' },
    { value: 'damaged', label: 'Dañada' },
    { value: 'in_transit', label: 'En tránsito' }
  ];

  const inputClass =
    'mt-1 h-9 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary';

  let {
    warehouseId,
    contextKey = '',
    focusHandlingUnitId,
    canVerify = false,
    canReadRetaceos = false,
    canVerifyRetaceos = false,
    canRelease = false,
    canTransfer = false,
    canPrepareSplit = false,
    onverified
  }: Props = $props();

  let units = $state<HandlingUnit[]>([]);
  let selectedQrUnit = $state<HandlingUnit | null>(null);
  let locationCodes = $state<Map<string, string>>(new Map());
  let eligibleReleaseLocations = $state<Array<{ id: string; code: string; label: string }>>([]);
  let splittingUnitId = $state<string | null>(null);
  let splitQuantityBase = $state<number | undefined>(undefined);
  let splitDestinationLocationId = $state('');
  let splitError = $state<string | null>(null);
  let releaseLocationByUnitId = $state<Record<string, string>>({});
  let loading = $state(true);
  let error = $state<string | null>(null);
  let locationWarning = $state<string | null>(null);
  let success = $state<string | null>(null);
  let successKind = $state<'general' | 'split'>('general');
  let search = $state('');
  let locationFilter = $state('');
  let statusFilter = $state<StockStatus | ''>('');
  let includeClosed = $state(false);
  let onlyPendingLabels = $state(false);
  let measuringUnitId = $state<string | null>(null);
  let savingUnitId = $state<string | null>(null);
  let measurementMethod = $state<MeasurementMethod>('volume');
  let weightKg = $state<number | undefined>(undefined);
  let volumeM3 = $state<number | undefined>(undefined);
  let lengthM = $state<number | undefined>(undefined);
  let widthM = $state<number | undefined>(undefined);
  let heightM = $state<number | undefined>(undefined);
  let measurementErrors = $state<Partial<Record<MeasurementField, string>>>({});
  let measurementError = $state<string | null>(null);
  let loadSequence = 0;
  let releaseIdempotencyKeys = new Map<string, { key: string; locationId: string }>();
  let splitIdempotencyKeys = new Map<
    string,
    { key: string; quantity: number; locationId: string }
  >();
  let lastFocusedHandlingUnitId: string | null = null;
  let activeContextKey = '';
  let contextSequence = 0;
  let measurementOperationSequence = 0;
  let dialogContextKey = $derived(
    [
      contextKey,
      warehouseId,
      canVerify,
      canReadRetaceos,
      canVerifyRetaceos,
      canRelease,
      canTransfer,
      canPrepareSplit
    ].join('|')
  );

  onDestroy(() => {
    contextSequence += 1;
    loadSequence += 1;
    measurementOperationSequence += 1;
  });

  function showHandlingUnitQr(unit: HandlingUnit) {
    selectedQrUnit = unit;
  }

  function releaseLocationLabel(location: LocationOut): string {
    return [
      location.code,
      location.area ? `Área ${location.area}` : null,
      location.aisle ? `Pasillo ${location.aisle}` : null,
      location.rack ? `Rack ${location.rack}` : null,
      location.level ? `Nivel ${location.level}` : null,
      location.position ? `Posición ${location.position}` : null
    ]
      .filter((part): part is string => Boolean(part))
      .join(' · ');
  }

  let locationOptions = $derived.by(() =>
    [...locationCodes.entries()]
      .map(([id, code]) => ({ id, code }))
      .sort((left, right) => left.code.localeCompare(right.code, 'es-SV'))
  );

  let filteredUnits = $derived.by(() => {
    const needle = search.trim().toLocaleLowerCase('es-SV');
    return units.filter((unit) => {
      if (locationFilter && unit.location_id !== locationFilter) return false;
      if (statusFilter && unit.stock_status !== statusFilter) return false;
      if (onlyPendingLabels && !unit.release_requirements?.includes('label_confirmation_required'))
        return false;
      if (!needle) return true;
      return [
        unit.product_name,
        unit.product_sku,
        unit.code,
        unit.lot_code,
        unit.receipt_lot_code,
        locationCodes.get(unit.location_id)
      ]
        .filter((value): value is string => Boolean(value))
        .some((value) => value.toLocaleLowerCase('es-SV').includes(needle));
    });
  });

  let pendingMeasurementCount = $derived(units.filter((unit) => isPendingMeasurement(unit)).length);

  async function loadLocationCodes(requestedWarehouseId: string): Promise<{
    codes: Map<string, string>;
    eligibleLocations: Array<{ id: string; code: string; label: string }>;
  }> {
    const codes = new Map<string, string>();
    const eligibleLocations: Array<{ id: string; code: string; label: string }> = [];
    let currentPage = 1;
    let totalPages = 1;

    do {
      const response = await listLocations(requestedWarehouseId, {
        page: currentPage,
        size: 100
      });
      for (const location of response.items) {
        codes.set(location.id, location.code);
        if (
          location.is_active &&
          location.storage_eligible &&
          ['active', 'blocked_out'].includes(location.lifecycle_status)
        ) {
          eligibleLocations.push({
            id: location.id,
            code: location.code,
            label: releaseLocationLabel(location)
          });
        }
      }
      totalPages = Math.max(1, response.meta.pages);
      currentPage += 1;
    } while (currentPage <= totalPages);

    return { codes, eligibleLocations };
  }

  async function loadData(
    requestedWarehouseId: string,
    requestedIncludeClosed: boolean,
    sequence: number,
    requestedContextSequence: number
  ) {
    loading = true;
    error = null;
    locationWarning = null;
    success = null;
    successKind = 'general';
    try {
      const [loadedUnits, locationsResult] = await Promise.all([
        inventoryApi.listHandlingUnits(requestedWarehouseId, {
          includeClosed: requestedIncludeClosed
        }),
        loadLocationCodes(requestedWarehouseId)
          .then((locations) => ({ ...locations, warning: null as string | null }))
          .catch(() => ({
            codes: new Map<string, string>(),
            eligibleLocations: [],
            warning:
              'Las unidades se cargaron, pero no fue posible resolver los códigos de ubicación.'
          }))
      ]);
      if (sequence !== loadSequence || requestedContextSequence !== contextSequence) return;
      units = loadedUnits;
      if (focusHandlingUnitId && focusHandlingUnitId !== lastFocusedHandlingUnitId) {
        const target = loadedUnits.find((unit) => unit.id === focusHandlingUnitId);
        if (target) {
          lastFocusedHandlingUnitId = focusHandlingUnitId;
          search = target.code;
          locationFilter = '';
          statusFilter = '';
          onlyPendingLabels = false;
          if (canMeasure(target)) startMeasurement(target);
          else if (
            canVerify &&
            target.release_requirements?.includes('label_confirmation_required')
          ) {
            showHandlingUnitQr(target);
          }
          await tick();
          document.getElementById(`handling-unit-${focusHandlingUnitId}`)?.scrollIntoView?.({
            block: 'center',
            behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
              ? 'instant'
              : 'smooth'
          });
        }
      }
      eligibleReleaseLocations = locationsResult.eligibleLocations;
      for (const [unitId, attempt] of releaseIdempotencyKeys) {
        const currentUnit = loadedUnits.find((unit) => unit.id === unitId);
        if (
          !currentUnit ||
          currentUnit.stock_status !== 'quarantine' ||
          currentUnit.closed_at != null ||
          currentUnit.location_id !== attempt.locationId
        ) {
          releaseIdempotencyKeys.delete(unitId);
        }
      }
      locationCodes = locationsResult.codes;
      locationWarning = locationsResult.warning;
    } catch (loadError) {
      if (sequence !== loadSequence || requestedContextSequence !== contextSequence) return;
      error =
        loadError instanceof Error
          ? loadError.message
          : 'No se pudieron cargar las unidades logísticas.';
    } finally {
      if (sequence === loadSequence) loading = false;
    }
  }

  function requestLoad() {
    const sequence = ++loadSequence;
    void loadData(warehouseId, includeClosed, sequence, contextSequence);
  }

  $effect(() => {
    const nextContextKey = [
      contextKey,
      warehouseId,
      canVerify,
      canReadRetaceos,
      canVerifyRetaceos,
      canRelease,
      canTransfer,
      canPrepareSplit
    ].join('|');
    void includeClosed;
    void focusHandlingUnitId;
    if (nextContextKey !== activeContextKey) {
      activeContextKey = nextContextKey;
      contextSequence += 1;
      loadSequence += 1;
      measurementOperationSequence += 1;
      units = [];
      locationCodes = new Map();
      eligibleReleaseLocations = [];
      selectedQrUnit = null;
      error = null;
      locationWarning = null;
      success = null;
      successKind = 'general';
      search = '';
      locationFilter = '';
      statusFilter = '';
      onlyPendingLabels = false;
      measuringUnitId = null;
      savingUnitId = null;
      resetMeasurementForm();
      cancelSplit();
      lastFocusedHandlingUnitId = null;
    }
    requestLoad();
  });

  function isPendingMeasurement(unit: HandlingUnit): boolean {
    return (
      unit.stock_status === 'quarantine' &&
      (unit.measurement_status === 'incomplete' || unit.measurement_source === 'split_estimate') &&
      unit.closed_at == null
    );
  }

  function canMeasure(unit: HandlingUnit): boolean {
    return canVerify && isPendingMeasurement(unit);
  }

  function releaseBlockReasons(unit: HandlingUnit): string[] {
    if (unit.stock_status !== 'quarantine' || unit.closed_at != null) return [];
    const reasons: string[] = [];
    for (const reason of unit.release_requirements ?? []) {
      if (reason === 'measurement_required') {
        reasons.push(
          canVerify
            ? 'Verifique las medidas antes de liberar.'
            : 'Un usuario autorizado debe verificar las medidas antes de liberar.'
        );
      } else if (reason === 'expired_lot') {
        reasons.push('El lote está vencido y no se puede liberar.');
      } else if (reason === 'label_confirmation_required') {
        reasons.push(
          canVerify
            ? 'Confirme la impresión y colocación de la etiqueta vigente antes de liberar.'
            : 'Un usuario autorizado debe confirmar la etiqueta vigente antes de liberar.'
        );
      } else if (reason === 'retaceo_not_final') {
        reasons.push(
          canVerifyRetaceos
            ? 'Verifique y cierre el retaceo de esta compra antes de liberar.'
            : 'Un usuario autorizado con permiso retaceos:verify debe verificar y cerrar el retaceo antes de liberar.'
        );
      } else if (reason === 'retaceo_cost_unapplied') {
        reasons.push(
          canVerifyRetaceos
            ? 'Aplique el retaceo verificado al costo del inventario antes de liberar.'
            : 'Un usuario autorizado con permiso retaceos:verify debe aplicar el retaceo al costo antes de liberar.'
        );
      }
    }
    if (unit.measurement_status === 'incomplete') {
      if (!reasons.some((reason) => reason.includes('medidas'))) {
        reasons.push(
          canVerify
            ? 'Verifique las medidas antes de liberar.'
            : 'Un usuario autorizado debe verificar las medidas antes de liberar.'
        );
      }
    }
    if (unit.measurement_source === 'split_estimate') {
      if (!reasons.some((reason) => reason.includes('medidas'))) {
        reasons.push(
          canVerify
            ? 'Verifique las medidas estimadas de esta fracción antes de liberarla.'
            : 'Un usuario autorizado debe verificar las medidas de esta fracción antes de liberarla.'
        );
      }
    }
    if (unit.expiry_date && unit.expiry_date < todayInElSalvador()) {
      if (!reasons.some((reason) => reason.includes('vencido'))) {
        reasons.push('El lote está vencido y no se puede liberar.');
      }
    }
    if (eligibleReleaseLocations.length === 0) {
      reasons.push('No hay ubicaciones activas aptas para almacenar inventario disponible.');
    }
    return reasons;
  }

  function hasRetaceoBlocker(unit: HandlingUnit): boolean {
    return (
      unit.release_requirements?.some(
        (reason) => reason === 'retaceo_not_final' || reason === 'retaceo_cost_unapplied'
      ) ?? false
    );
  }

  function releaseDestination(unit: HandlingUnit): string {
    const selected = releaseLocationByUnitId[unit.id];
    if (selected && eligibleReleaseLocations.some((location) => location.id === selected)) {
      return selected;
    }
    return eligibleReleaseLocations.some((location) => location.id === unit.location_id)
      ? unit.location_id
      : '';
  }

  function canReleaseUnit(unit: HandlingUnit): boolean {
    return (
      canRelease &&
      unit.closed_at == null &&
      unit.stock_status === 'quarantine' &&
      releaseBlockReasons(unit).length === 0 &&
      releaseDestination(unit) !== ''
    );
  }

  function chooseReleaseDestination(unitId: string, destinationLocationId: string) {
    releaseIdempotencyKeys.delete(unitId);
    releaseLocationByUnitId = { ...releaseLocationByUnitId, [unitId]: destinationLocationId };
  }

  function transferBlockReason(unit: HandlingUnit): string | null {
    if (unit.closed_at != null) return 'La unidad está cerrada.';
    if (unit.stock_status !== 'available') return 'Solo se trasladan unidades disponibles.';
    if (unit.measurement_status === 'incomplete') {
      return 'La unidad debe completar su revisión física antes del traslado.';
    }
    if (unit.expiry_date && unit.expiry_date < todayInElSalvador()) {
      return 'El lote está vencido y no se puede trasladar.';
    }
    return null;
  }

  function startTransfer(unit: HandlingUnit) {
    if (!canTransfer || transferBlockReason(unit)) return;
    const query = new URLSearchParams({
      warehouse_id: unit.warehouse_id,
      handling_unit_id: unit.id
    });
    void goto(`/transfers?${query.toString()}`);
  }

  function startSplit(unit: HandlingUnit) {
    if (
      savingUnitId != null ||
      !canPrepareSplit ||
      unit.stock_status !== 'available' ||
      unit.closed_at != null
    )
      return;
    success = null;
    successKind = 'general';
    splitError = null;
    splittingUnitId = splittingUnitId === unit.id ? null : unit.id;
    // Require an explicit quantity so reopening a remainder cannot silently split it in half again.
    splitQuantityBase = undefined;
    splitDestinationLocationId = eligibleReleaseLocations.some(
      (location) => location.id === unit.location_id
    )
      ? unit.location_id
      : (eligibleReleaseLocations[0]?.id ?? '');
  }

  function cancelSplit() {
    splittingUnitId = null;
    splitQuantityBase = undefined;
    splitDestinationLocationId = '';
    splitError = null;
  }

  function requestSplit(unit: HandlingUnit) {
    const quantity = splitQuantityBase;
    if (
      !canPrepareSplit ||
      savingUnitId != null ||
      splittingUnitId !== unit.id ||
      unit.stock_status !== 'available' ||
      unit.closed_at != null ||
      quantity == null ||
      !Number.isFinite(quantity) ||
      quantity <= 0 ||
      quantity >= unit.quantity_base ||
      !eligibleReleaseLocations.some((location) => location.id === splitDestinationLocationId)
    ) {
      splitError = 'Indique una cantidad menor que la unidad y una ubicación apta.';
      return;
    }
    const destination = eligibleReleaseLocations.find(
      (location) => location.id === splitDestinationLocationId
    );
    if (!destination) return;

    confirmation.request({
      kind: 'transfer',
      title: 'Confirmar división de unidad',
      description: `La unidad original conservará el código ${unit.code} y quedará como remanente de ${number(unit.quantity_base - quantity, 6)} unidades base. Se creará otra unidad con ${number(quantity, 6)}. La suma no cambia el inventario. Como cambia la cantidad, la etiqueta anterior dejará de estar vigente. Ambas quedarán en cuarentena: verifica las medidas y confirma una etiqueta vigente para cada una antes de liberarlas.`,
      resourceName: `${unit.code} · nueva unidad ${number(quantity, 6)} + remanente ${number(unit.quantity_base - quantity, 6)} · ${destination.code}`,
      confirmLabel: 'Confirmar división',
      execute: async () => {
        if (savingUnitId != null || splittingUnitId !== unit.id) return;
        savingUnitId = unit.id;
        const previous = splitIdempotencyKeys.get(unit.id);
        const attempt =
          previous?.quantity === quantity && previous.locationId === destination.id
            ? previous
            : { key: crypto.randomUUID(), quantity, locationId: destination.id };
        splitIdempotencyKeys.set(unit.id, attempt);
        splitError = null;
        try {
          const result = await inventoryApi.prepareHandlingUnitSplit(
            unit.id,
            quantity,
            destination.id,
            attempt.key
          );
          splitIdempotencyKeys.delete(unit.id);
          cancelSplit();
          requestLoad();
          success = `División preparada: nueva unidad ${result.split_handling_unit_code} (${number(Number(result.split_quantity_base), 6)}) y remanente ${result.remainder_handling_unit_code} (${number(Number(result.remainder_quantity_base), 6)}). El remanente conserva el código original; el total de inventario no cambia y ambas unidades están en cuarentena.`;
          successKind = 'split';
          onverified?.();
        } finally {
          savingUnitId = null;
        }
      }
    });
  }

  function statusLabel(status: StockStatus): string {
    return STOCK_STATUS_OPTIONS.find((option) => option.value === status)?.label ?? status;
  }

  function statusVariant(
    status: StockStatus
  ): 'success' | 'warning' | 'danger' | 'neutral' | 'primary' {
    if (status === 'available') return 'success';
    if (status === 'quarantine') return 'warning';
    if (status === 'blocked' || status === 'damaged') return 'danger';
    if (status === 'in_transit') return 'primary';
    return 'neutral';
  }

  function measurementLabel(unit: HandlingUnit): string {
    if (unit.measurement_source === 'split_estimate' && unit.measurement_status === 'incomplete') {
      return 'Fraccionada · verificar medidas reales';
    }
    if (unit.measurement_source === 'split_estimate') {
      return 'Fraccionada · medidas estimadas por verificar';
    }
    if (unit.measurement_status === 'verified') return 'Medición verificada';
    if (unit.measurement_status === 'complete') return 'Medición completa';
    return 'Medición pendiente';
  }

  function number(value: number, maximumFractionDigits = 3): string {
    return value.toLocaleString('es-SV', { maximumFractionDigits });
  }

  function baseUnitLabel(unit: HandlingUnit): string {
    return unit.base_unit_name
      ? `${unit.base_unit_name}${unit.base_unit_symbol && !unit.base_unit_name.includes(`(${unit.base_unit_symbol})`) && unit.base_unit_name !== unit.base_unit_symbol ? ` (${unit.base_unit_symbol})` : ''}`
      : (unit.base_unit_symbol ?? 'Unidad sin identificar');
  }

  function todayInElSalvador(): string {
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'America/El_Salvador',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    }).formatToParts(new Date());
    const value = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    return `${value.year}-${value.month}-${value.day}`;
  }

  function physical(value: number | null, unit: string): string {
    return value == null ? 'Sin medir' : `${number(value)} ${unit}`;
  }

  function expiry(value: string | null): string {
    if (!value) return 'Sin vencimiento';
    const parsed = new Date(`${value}T00:00:00`);
    return Number.isNaN(parsed.getTime())
      ? value
      : parsed.toLocaleDateString('es-SV', {
          day: '2-digit',
          month: 'short',
          year: 'numeric'
        });
  }

  function locationCode(unit: HandlingUnit): string {
    return locationCodes.get(unit.location_id) ?? 'Código no disponible';
  }

  function resetMeasurementForm() {
    measuringUnitId = null;
    savingUnitId = null;
    measurementMethod = 'volume';
    weightKg = undefined;
    volumeM3 = undefined;
    lengthM = undefined;
    widthM = undefined;
    heightM = undefined;
    measurementErrors = {};
    measurementError = null;
  }

  function startMeasurement(unit: HandlingUnit) {
    success = null;
    successKind = 'general';
    measurementErrors = {};
    measurementError = null;
    measuringUnitId = unit.id;
    weightKg = unit.actual_gross_weight_kg ?? undefined;
    volumeM3 = unit.actual_volume_m3 ?? undefined;
    lengthM = unit.actual_length_m ?? undefined;
    widthM = unit.actual_width_m ?? undefined;
    heightM = unit.actual_height_m ?? undefined;
    measurementMethod =
      unit.actual_length_m != null && unit.actual_width_m != null && unit.actual_height_m != null
        ? 'dimensions'
        : 'volume';
  }

  function positive(value: number | undefined): number | null {
    return value != null && Number.isFinite(value) && value > 0 ? value : null;
  }

  function validateMeasurement(): PhysicalMeasuresInput | null {
    const errors: Partial<Record<MeasurementField, string>> = {};
    const weight = positive(weightKg);
    if (weight == null) errors.weight = 'Ingrese un peso mayor que cero.';

    let measures: PhysicalMeasuresInput;
    if (measurementMethod === 'volume') {
      const volume = positive(volumeM3);
      if (volume == null) errors.volume = 'Ingrese un volumen mayor que cero.';
      measures = {
        gross_weight_kg: weight,
        volume_m3: volume,
        length_m: null,
        width_m: null,
        height_m: null
      };
    } else {
      const length = positive(lengthM);
      const width = positive(widthM);
      const height = positive(heightM);
      if (length == null) errors.length = 'Ingrese un largo mayor que cero.';
      if (width == null) errors.width = 'Ingrese un ancho mayor que cero.';
      if (height == null) errors.height = 'Ingrese un alto mayor que cero.';
      measures = {
        gross_weight_kg: weight,
        volume_m3: null,
        length_m: length,
        width_m: width,
        height_m: height
      };
    }

    measurementErrors = errors;
    return Object.keys(errors).length === 0 ? measures : null;
  }

  async function verifyMeasurement(event: SubmitEvent, unit: HandlingUnit) {
    event.preventDefault();
    if (!canMeasure(unit) || savingUnitId) return;
    measurementError = null;
    success = null;
    successKind = 'general';
    const measures = validateMeasurement();
    if (!measures) return;

    const operationContextSequence = contextSequence;
    const operationSequence = ++measurementOperationSequence;
    savingUnitId = unit.id;
    try {
      const verified = await inventoryApi.verifyHandlingUnitMeasurements(
        unit.id,
        measures,
        'manual'
      );
      if (
        operationContextSequence !== contextSequence ||
        operationSequence !== measurementOperationSequence
      )
        return;
      // Invalidate reads started before this write. Re-run only an active read;
      // otherwise the enriched mutation response is already authoritative.
      const refreshAfterWrite = loading;
      loadSequence += 1;
      units = units.map((candidate) => (candidate.id === verified.id ? verified : candidate));
      resetMeasurementForm();
      if (refreshAfterWrite) requestLoad();
      successKind = 'general';
      success = `Medidas de ${verified.code} verificadas correctamente.`;
      onverified?.();
    } catch (verifyError) {
      if (
        operationContextSequence === contextSequence &&
        operationSequence === measurementOperationSequence
      ) {
        measurementError =
          verifyError instanceof Error
            ? verifyError.message
            : 'No se pudieron verificar las medidas.';
      }
    } finally {
      if (
        operationContextSequence === contextSequence &&
        operationSequence === measurementOperationSequence &&
        savingUnitId === unit.id
      ) {
        savingUnitId = null;
      }
    }
  }

  function requestRelease(unit: HandlingUnit) {
    if (!canReleaseUnit(unit) || savingUnitId) return;
    success = null;
    successKind = 'general';
    const destinationLocationId = releaseDestination(unit);
    const destinationCode = eligibleReleaseLocations.find(
      (location) => location.id === destinationLocationId
    )?.code;
    if (!destinationCode) return;
    confirmation.request({
      kind: 'release',
      title: 'Liberar inventario',
      description:
        'La unidad pasará de cuarentena a disponible en la ubicación de destino. La cantidad y el costo no cambian; la operación quedará registrada en el historial de inventario.',
      resourceName: `${unit.code} · ${number(unit.quantity_base, 6)} unidades base · ${locationCode(unit)} → ${destinationCode}`,
      confirmLabel: 'Liberar a disponible',
      execute: async () => {
        savingUnitId = unit.id;
        const attempt = releaseIdempotencyKeys.get(unit.id) ?? {
          key: crypto.randomUUID(),
          locationId: unit.location_id
        };
        releaseIdempotencyKeys.set(unit.id, attempt);
        try {
          await inventoryApi.releaseHandlingUnit(unit, destinationLocationId, attempt.key);
          releaseIdempotencyKeys.delete(unit.id);
          units = units.map((candidate) =>
            candidate.id === unit.id
              ? {
                  ...candidate,
                  location_id: destinationLocationId,
                  stock_status: 'available' as const
                }
              : candidate
          );
          successKind = 'general';
          success = `${unit.code} quedó disponible en inventario.`;
          onverified?.();
        } finally {
          savingUnitId = null;
        }
      }
    });
  }
</script>

{#if canRelease}
  <GroupedPutawayPanel {warehouseId} onconfirmed={requestLoad} />
{/if}

<Card class="overflow-hidden">
  <div
    class="flex flex-col gap-4 border-b border-border px-5 py-4 lg:flex-row lg:items-start lg:justify-between"
  >
    <div>
      <div class="flex flex-wrap items-center gap-2">
        <h3 class="text-sm font-semibold text-foreground">Unidades logísticas</h3>
        {#if !loading}<Badge variant="neutral">{units.length} registradas</Badge>{/if}
        {#if !loading && pendingMeasurementCount > 0}
          <Badge variant="warning">{pendingMeasurementCount} por medir</Badge>
        {/if}
      </div>
      <p class="mt-1 max-w-3xl text-xs leading-5 text-foreground-muted">
        Existencias físicas identificables por caja, saco, paquete, contenedor o producto suelto.
        Los valores desconocidos nunca se interpretan como cero.
      </p>
      {#if canTransfer || canPrepareSplit}
        <p class="mt-1 max-w-3xl text-xs leading-5 text-foreground-muted">
          {#if canTransfer}Desde la bodega madre puedes trasladar unidades completas a una bodega de
            sucursal.
          {/if}
          {#if canPrepareSplit}Disponible indica que la revisión terminó. Dividir es opcional: úsalo
            solo si vas a separar físicamente el contenido.{/if}
        </p>
      {/if}
    </div>
    <Button variant="secondary" size="sm" onclick={requestLoad} disabled={loading}>
      {loading ? 'Actualizando…' : 'Actualizar'}
    </Button>
  </div>

  <div class="space-y-4 p-5">
    <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-[minmax(220px,1fr)_220px_180px_auto]">
      <label class="text-xs font-medium text-foreground-muted" for="handling-unit-search">
        Buscar por producto, SKU, código, lote o ubicación
        <input
          id="handling-unit-search"
          class={inputClass}
          type="search"
          bind:value={search}
          placeholder="Ej. Café, PRD-CAF-011 o HU-000123"
        />
      </label>
      <label class="text-xs font-medium text-foreground-muted" for="handling-unit-location">
        Ubicación
        <select
          id="handling-unit-location"
          class={inputClass}
          value={locationFilter}
          onchange={(event) => {
            locationFilter = (event.currentTarget as HTMLSelectElement).value;
          }}
        >
          <option value="">Todas las ubicaciones</option>
          {#each locationOptions as location (location.id)}
            <option value={location.id}>{location.code}</option>
          {/each}
        </select>
      </label>
      <label class="text-xs font-medium text-foreground-muted" for="handling-unit-status">
        Estado de existencia
        <select
          id="handling-unit-status"
          class={inputClass}
          value={statusFilter}
          onchange={(event) => {
            statusFilter = (event.currentTarget as HTMLSelectElement).value as StockStatus | '';
          }}
        >
          <option value="">Todos los estados</option>
          {#each STOCK_STATUS_OPTIONS as option (option.value)}
            <option value={option.value}>{option.label}</option>
          {/each}
        </select>
      </label>
      <label
        class="mt-5 flex h-9 items-center gap-2 rounded-lg border border-border px-3 text-xs text-foreground"
      >
        <input type="checkbox" bind:checked={includeClosed} /> Mostrar cerradas
      </label>
    </div>

    <label class="flex min-h-11 w-fit items-center gap-2 text-sm text-foreground">
      <input type="checkbox" bind:checked={onlyPendingLabels} />
      Solo etiquetas pendientes de imprimir o confirmar
    </label>

    {#if success}
      <div
        class="rounded-lg border border-success/30 bg-success/10 px-4 py-3 text-sm text-success"
        role="status"
      >
        <p>{success}</p>
        {#if successKind === 'split'}
          <div class="mt-3 border-t border-success/20 pt-3 text-xs text-foreground">
            <p class="font-semibold">¿Qué sigue?</p>
            <p class="mt-1 text-foreground-muted">
              No es otra recepción: se dividió una unidad disponible en dos. La confirmación de
              etiqueta anterior ya no aplica a la cantidad nueva; cada fila necesita su propia
              etiqueta vigente.
            </p>
            <ol class="mt-2 list-inside list-decimal space-y-1 text-foreground-muted">
              <li>
                En cada fila, pulsa <strong>Verificar medidas</strong> y registra las medidas reales de
                esa unidad.
              </li>
              <li>
                Pulsa <strong>Revisar etiqueta</strong>, imprime y coloca la etiqueta de esa unidad,
                y confirma que quedó colocada. Al remanente le corresponderá reimpresión si ya tenía
                una etiqueta; la fracción recibe su primera.
              </li>
              <li>
                Cuando ya no haya requisitos pendientes, pulsa <strong>Liberar a disponible</strong>
                en cada fila.
              </li>
            </ol>
          </div>
        {/if}
      </div>
    {/if}
    {#if locationWarning}
      <div
        class="rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-xs text-warning"
        role="status"
      >
        {locationWarning}
      </div>
    {/if}

    {#if error && units.length > 0}
      <div class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3" role="alert">
        <p class="text-sm font-semibold text-danger">No se pudo actualizar el inventario físico</p>
        <p class="mt-1 text-xs text-danger/90">{error}</p>
        <div class="mt-3">
          <Button variant="secondary" size="sm" onclick={requestLoad}>Reintentar</Button>
        </div>
      </div>
    {/if}

    {#if loading && units.length === 0}
      <div class="space-y-2" role="status" aria-label="Cargando unidades logísticas">
        {#each Array(4) as _}
          <div class="skeleton h-12 rounded-lg"></div>
        {/each}
      </div>
    {:else if error && units.length === 0}
      <div class="rounded-xl border border-danger/30 bg-danger/10 p-5" role="alert">
        <p class="text-sm font-semibold text-danger">No se pudo cargar el inventario físico</p>
        <p class="mt-1 text-xs text-danger/90">{error}</p>
        <div class="mt-4">
          <Button variant="secondary" size="sm" onclick={requestLoad}>Reintentar</Button>
        </div>
      </div>
    {:else if units.length === 0}
      <div
        class="rounded-xl border border-dashed border-border px-6 py-10 text-center"
        role="status"
      >
        <div
          class="mx-auto flex h-11 w-11 items-center justify-center rounded-xl bg-surface-muted text-foreground-muted"
        >
          <svg
            width="22"
            height="22"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <path
              d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"
            />
            <path d="m3.3 7 8.7 5 8.7-5M12 22V12" />
          </svg>
        </div>
        <p class="mt-3 text-sm font-semibold text-foreground">Sin unidades logísticas activas</p>
        <p class="mt-1 text-xs text-foreground-muted">
          Se mostrarán aquí cuando se confirme la recepción de mercancía identificable.
        </p>
      </div>
    {:else if filteredUnits.length === 0}
      <div
        class="rounded-xl border border-dashed border-border px-6 py-8 text-center"
        role="status"
      >
        <p class="text-sm font-semibold text-foreground">Sin coincidencias</p>
        <p class="mt-1 text-xs text-foreground-muted">Ajuste la búsqueda o los filtros.</p>
      </div>
    {:else}
      <div class="overflow-hidden rounded-xl border border-border">
        <table class="w-full text-xs">
          <caption class="sr-only">
            Unidades logísticas, ubicación, estado, trazabilidad y ocupación física
          </caption>
          <thead
            class="sr-only border-b border-border bg-surface-muted/40 text-left text-foreground-muted xl:not-sr-only xl:table-header-group"
          >
            <tr>
              <th scope="col" class="px-3 py-2.5">Unidad logística</th>
              <th scope="col" class="px-3 py-2.5">Ubicación</th>
              <th scope="col" class="px-3 py-2.5">Estado</th>
              <th scope="col" class="px-3 py-2.5">Lote y vencimiento</th>
              <th scope="col" class="px-3 py-2.5 text-right">Cantidad</th>
              <th scope="col" class="px-3 py-2.5 text-right">Peso ocupado</th>
              <th scope="col" class="px-3 py-2.5 text-right">Volumen ocupado</th>
              <th scope="col" class="px-3 py-2.5 text-right">QR y acciones</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            {#each filteredUnits as unit (unit.id)}
              <tr
                id={`handling-unit-${unit.id}`}
                class={`grid grid-cols-2 gap-x-4 gap-y-2 p-3 align-top hover:bg-surface-muted/25 sm:grid-cols-3 xl:table-row xl:p-0 ${unit.id === focusHandlingUnitId ? 'bg-primary/5 ring-1 ring-inset ring-primary/30' : ''}`}
              >
                <td
                  data-label="Unidad logística"
                  class="min-w-0 px-1 py-2 before:mb-1 before:block before:font-semibold before:uppercase before:tracking-wide before:text-foreground-muted before:content-[attr(data-label)] xl:table-cell xl:px-3 xl:py-3 xl:before:hidden"
                >
                  <p class="max-w-xs break-words text-sm font-semibold text-foreground">
                    {unit.product_name ?? 'Producto sin identificar'}
                  </p>
                  {#if unit.product_sku}
                    <p class="mt-1 text-xs text-foreground-muted">{unit.product_sku}</p>
                  {/if}
                  <p class="mt-1 break-all font-mono text-xs text-foreground-muted">{unit.code}</p>
                  {#if unit.packaging_name}
                    <p class="mt-1 text-xs text-foreground-muted">
                      Presentación de origen: {unit.packaging_name}
                      {#if unit.packaging_base_quantity != null}
                        · {number(Number(unit.packaging_base_quantity), 6)}
                        {baseUnitLabel(unit)} por presentación
                      {/if}
                    </p>
                  {/if}
                  <p class="mt-1 text-xs text-foreground-muted">
                    {unit.closed_at ? 'Cerrada' : measurementLabel(unit)}
                  </p>
                </td>
                <td
                  data-label="Ubicación"
                  class="min-w-0 px-1 py-2 before:mb-1 before:block before:font-semibold before:uppercase before:tracking-wide before:text-foreground-muted before:content-[attr(data-label)] xl:table-cell xl:px-3 xl:py-3 xl:before:hidden"
                >
                  <p class="font-mono text-foreground">{locationCode(unit)}</p>
                </td>
                <td
                  data-label="Estado"
                  class="min-w-0 px-1 py-2 before:mb-1 before:block before:font-semibold before:uppercase before:tracking-wide before:text-foreground-muted before:content-[attr(data-label)] xl:table-cell xl:px-3 xl:py-3 xl:before:hidden"
                >
                  <Badge variant={statusVariant(unit.stock_status)}>
                    {statusLabel(unit.stock_status)}
                  </Badge>
                </td>
                <td
                  data-label="Lote y vencimiento"
                  class="min-w-0 px-1 py-2 before:mb-1 before:block before:font-semibold before:uppercase before:tracking-wide before:text-foreground-muted before:content-[attr(data-label)] xl:table-cell xl:px-3 xl:py-3 xl:before:hidden"
                >
                  {#if unit.lot_code}
                    <p class="font-mono text-foreground">Fabricante: {unit.lot_code}</p>
                  {/if}
                  {#if unit.receipt_lot_code}
                    <p class="font-mono text-foreground">Recepción: {unit.receipt_lot_code}</p>
                  {/if}
                  {#if !unit.lot_code && !unit.receipt_lot_code}
                    <p class="font-mono text-foreground">Sin lote</p>
                  {/if}
                  <p class="mt-1 text-xs text-foreground-muted">{expiry(unit.expiry_date)}</p>
                </td>
                <td
                  data-label="Cantidad"
                  class="min-w-0 px-1 py-2 text-left font-mono tabular-nums text-foreground before:mb-1 before:block before:font-sans before:font-semibold before:uppercase before:tracking-wide before:text-foreground-muted before:content-[attr(data-label)] xl:table-cell xl:px-3 xl:py-3 xl:text-right xl:before:hidden"
                >
                  {number(unit.quantity_base, 6)}
                  <span class="block text-xs text-foreground-muted">{baseUnitLabel(unit)}</span>
                </td>
                <td
                  data-label="Peso ocupado"
                  class="min-w-0 px-1 py-2 text-left font-mono tabular-nums text-foreground before:mb-1 before:block before:font-sans before:font-semibold before:uppercase before:tracking-wide before:text-foreground-muted before:content-[attr(data-label)] xl:table-cell xl:px-3 xl:py-3 xl:text-right xl:before:hidden"
                >
                  {physical(unit.occupied_weight_kg, 'kg')}
                </td>
                <td
                  data-label="Volumen ocupado"
                  class="min-w-0 px-1 py-2 text-left font-mono tabular-nums text-foreground before:mb-1 before:block before:font-sans before:font-semibold before:uppercase before:tracking-wide before:text-foreground-muted before:content-[attr(data-label)] xl:table-cell xl:px-3 xl:py-3 xl:text-right xl:before:hidden"
                >
                  {physical(unit.occupied_volume_m3, 'm³')}
                </td>
                <td
                  data-label="QR y acciones"
                  class="col-span-full min-w-0 px-1 py-2 text-left before:mb-1 before:block before:font-semibold before:uppercase before:tracking-wide before:text-foreground-muted before:content-[attr(data-label)] xl:table-cell xl:px-3 xl:py-3 xl:text-right xl:before:hidden"
                >
                  <div class="flex flex-wrap justify-end gap-2">
                    <a
                      href={physicalKardexHref(warehouseId, unit.inventory_item_id)}
                      class="inline-flex min-h-11 items-center justify-center rounded-lg border border-foreground/50 bg-surface-elevated px-3 text-xs font-medium text-foreground hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                      aria-label={`Ver Kardex de ${unit.product_name ?? unit.product_sku ?? unit.code} en esta bodega`}
                      >Ver Kardex</a
                    >
                    <button
                      type="button"
                      class="inline-flex h-8 items-center justify-center rounded-lg border border-primary/40 bg-primary/10 px-3 text-xs font-medium text-primary transition-colors hover:bg-primary/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                      onclick={() => void showHandlingUnitQr(unit)}
                      aria-label={`Ver QR de ${unit.code}`}
                    >
                      Ver QR
                    </button>
                  </div>
                  {#if unit.stock_status === 'available' && unit.closed_at == null}
                    <p class="mt-2 text-xs text-success">
                      Revisión terminada · disponible para uso
                    </p>
                  {/if}
                  {#if canVerify || canRelease || canTransfer || canPrepareSplit}
                    {#if canMeasure(unit) || (canRelease && unit.stock_status === 'quarantine' && unit.closed_at == null) || ((canTransfer || canPrepareSplit) && unit.stock_status === 'available' && unit.closed_at == null)}
                      <div class="flex flex-wrap justify-end gap-2">
                        {#if canMeasure(unit)}
                          <button
                            type="button"
                            class="inline-flex h-8 items-center justify-center rounded-lg border border-border bg-surface-elevated px-3 text-xs font-medium text-foreground shadow-soft transition-all hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:pointer-events-none disabled:opacity-40"
                            disabled={savingUnitId != null}
                            onclick={() =>
                              measuringUnitId === unit.id
                                ? resetMeasurementForm()
                                : startMeasurement(unit)}
                            aria-expanded={measuringUnitId === unit.id}
                            aria-controls={`measurement-${unit.id}`}
                          >
                            {measuringUnitId === unit.id ? 'Cerrar' : 'Verificar medidas'}
                          </button>
                        {/if}
                        {#if canRelease && unit.stock_status === 'quarantine' && unit.closed_at == null}
                          {#if releaseBlockReasons(unit).length > 0}
                            <ul
                              class="w-full space-y-1 text-right text-[11px] text-warning"
                              aria-label={`Requisitos pendientes para ${unit.code}`}
                            >
                              {#each releaseBlockReasons(unit) as reason (reason)}
                                <li>{reason}</li>
                              {/each}
                            </ul>
                            {#if hasRetaceoBlocker(unit) && (unit.purchase_code || unit.receipt_lot_code)}
                              <p class="w-full text-right text-xs text-foreground-muted">
                                Referencia: {unit.purchase_code
                                  ? `Compra ${unit.purchase_code}`
                                  : 'compra vinculada'}{unit.receipt_lot_code
                                  ? ` · Lote ${unit.receipt_lot_code}`
                                  : ''}
                              </p>
                            {/if}
                            {#if hasRetaceoBlocker(unit) && canReadRetaceos}
                              <a
                                class="inline-flex h-8 items-center rounded-lg border border-warning/40 bg-warning/10 px-3 text-xs font-medium text-warning underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-warning"
                                href="/retaceos"
                              >
                                Abrir retaceos
                              </a>
                            {/if}
                            {#if canVerify && unit.release_requirements?.includes('label_confirmation_required')}
                              <button
                                type="button"
                                class="inline-flex h-8 items-center rounded-lg border border-primary/40 bg-primary/10 px-3 text-xs font-medium text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                                onclick={() => showHandlingUnitQr(unit)}
                              >
                                Revisar etiqueta
                              </button>
                            {/if}
                          {:else}
                            <label class="sr-only" for={`release-location-${unit.id}`}
                              >Destino para {unit.code}</label
                            >
                            <select
                              id={`release-location-${unit.id}`}
                              class={inputClass}
                              value={releaseDestination(unit)}
                              onchange={(event) =>
                                chooseReleaseDestination(
                                  unit.id,
                                  (event.currentTarget as HTMLSelectElement).value
                                )}
                            >
                              <option value="">Seleccione destino disponible</option>
                              {#each eligibleReleaseLocations as location (location.id)}
                                <option value={location.id}>
                                  {location.label}{location.id === unit.location_id
                                    ? ' · ubicación actual'
                                    : ''}
                                </option>
                              {/each}
                            </select>
                            <button
                              type="button"
                              class="inline-flex h-9 shrink-0 items-center justify-center rounded-lg border border-success/40 bg-success/10 px-3 text-xs font-medium text-success transition-colors hover:bg-success/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-success disabled:pointer-events-none disabled:opacity-40"
                              disabled={!canReleaseUnit(unit) || savingUnitId != null}
                              onclick={() => requestRelease(unit)}
                            >
                              Liberar a disponible
                            </button>
                          {/if}
                        {/if}
                        {#if canTransfer && unit.stock_status === 'available' && unit.closed_at == null}
                          <button
                            type="button"
                            class="inline-flex h-9 shrink-0 items-center justify-center rounded-lg border border-primary/40 bg-primary/10 px-3 text-xs font-medium text-primary transition-colors hover:bg-primary/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:pointer-events-none disabled:opacity-40"
                            disabled={Boolean(transferBlockReason(unit)) || savingUnitId != null}
                            onclick={() => startTransfer(unit)}
                            title={transferBlockReason(unit) ?? undefined}
                          >
                            Trasladar a sucursal
                          </button>
                          {#if transferBlockReason(unit)}
                            <span class="w-full text-right text-[11px] text-warning"
                              >{transferBlockReason(unit)}</span
                            >
                          {/if}
                        {/if}
                        {#if canPrepareSplit && unit.stock_status === 'available' && unit.closed_at == null}
                          <details
                            class="mt-2 w-full text-xs"
                            ontoggle={(event) => {
                              if (
                                !event.currentTarget.open &&
                                splittingUnitId === unit.id &&
                                savingUnitId == null
                              )
                                cancelSplit();
                            }}
                          >
                            <summary
                              class="cursor-pointer rounded-lg px-2 py-2 text-foreground-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                              >Otras acciones</summary
                            >
                            <button
                              type="button"
                              class="inline-flex h-9 shrink-0 items-center justify-center rounded-lg border border-warning/40 bg-warning/10 px-3 text-xs font-medium text-warning transition-colors hover:bg-warning/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-warning disabled:pointer-events-none disabled:opacity-40"
                              disabled={savingUnitId != null}
                              onclick={() => startSplit(unit)}
                              aria-expanded={splittingUnitId === unit.id}
                              aria-controls={`split-${unit.id}`}
                            >
                              {splittingUnitId === unit.id ? 'Cerrar formulario' : 'Dividir unidad'}
                            </button>
                          </details>
                        {/if}
                      </div>
                    {/if}
                  {/if}
                </td>
              </tr>
              {#if measuringUnitId === unit.id && canMeasure(unit)}
                <tr id={`measurement-${unit.id}`} class="block xl:table-row">
                  <td
                    colspan="8"
                    class="block bg-warning/5 px-2 py-3 xl:table-cell xl:px-4 xl:py-4"
                  >
                    <form
                      class="rounded-xl border border-warning/30 bg-surface p-4"
                      aria-label={`Verificar medidas de ${unit.code}`}
                      onsubmit={(event) => void verifyMeasurement(event, unit)}
                    >
                      <div
                        class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between"
                      >
                        <div>
                          <h4 class="text-sm font-semibold text-foreground">
                            Verificación física · {unit.code}
                          </h4>
                          <p class="mt-1 text-xs text-foreground-muted">
                            Registre el peso bruto y el volumen total de la unidad logística
                            completa, ya sea directamente o mediante sus tres dimensiones
                            exteriores.
                          </p>
                        </div>
                        <Badge variant="warning">Cuarentena</Badge>
                      </div>

                      {#if measurementError}
                        <div
                          class="mt-3 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger"
                          role="alert"
                        >
                          {measurementError}
                        </div>
                      {/if}

                      <div class="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                        <label
                          class="text-xs font-medium text-foreground-muted"
                          for={`measurement-weight-${unit.id}`}
                        >
                          Peso bruto total de la unidad logística (kg) *
                          <input
                            id={`measurement-weight-${unit.id}`}
                            class={inputClass}
                            type="number"
                            min="0.000001"
                            step="any"
                            bind:value={weightKg}
                            required
                            aria-invalid={measurementErrors.weight ? 'true' : undefined}
                            aria-describedby={measurementErrors.weight
                              ? `measurement-weight-${unit.id}-error`
                              : undefined}
                          />
                          {#if measurementErrors.weight}
                            <span
                              id={`measurement-weight-${unit.id}-error`}
                              class="mt-1 block text-[11px] text-danger"
                              >{measurementErrors.weight}</span
                            >
                          {/if}
                        </label>

                        <label
                          class="text-xs font-medium text-foreground-muted"
                          for={`measurement-method-${unit.id}`}
                        >
                          Método de volumen *
                          <select
                            id={`measurement-method-${unit.id}`}
                            class={inputClass}
                            value={measurementMethod}
                            onchange={(event) => {
                              measurementMethod = (event.currentTarget as HTMLSelectElement)
                                .value as MeasurementMethod;
                              measurementErrors = {};
                              measurementError = null;
                            }}
                          >
                            <option value="volume">Volumen directo</option>
                            <option value="dimensions">Calcular por dimensiones</option>
                          </select>
                        </label>

                        {#if measurementMethod === 'volume'}
                          <label
                            class="text-xs font-medium text-foreground-muted md:col-span-2 xl:col-span-1"
                            for={`measurement-volume-${unit.id}`}
                          >
                            Volumen (m³) *
                            <input
                              id={`measurement-volume-${unit.id}`}
                              class={inputClass}
                              type="number"
                              min="0.000001"
                              step="any"
                              bind:value={volumeM3}
                              required
                              aria-invalid={measurementErrors.volume ? 'true' : undefined}
                              aria-describedby={measurementErrors.volume
                                ? `measurement-volume-${unit.id}-error`
                                : undefined}
                            />
                            {#if measurementErrors.volume}
                              <span
                                id={`measurement-volume-${unit.id}-error`}
                                class="mt-1 block text-[11px] text-danger"
                                >{measurementErrors.volume}</span
                              >
                            {/if}
                          </label>
                        {:else}
                          <label
                            class="text-xs font-medium text-foreground-muted"
                            for={`measurement-length-${unit.id}`}
                          >
                            Largo (m) *
                            <input
                              id={`measurement-length-${unit.id}`}
                              class={inputClass}
                              type="number"
                              min="0.000001"
                              step="any"
                              bind:value={lengthM}
                              required
                              aria-invalid={measurementErrors.length ? 'true' : undefined}
                              aria-describedby={measurementErrors.length
                                ? `measurement-length-${unit.id}-error`
                                : undefined}
                            />
                            {#if measurementErrors.length}
                              <span
                                id={`measurement-length-${unit.id}-error`}
                                class="mt-1 block text-[11px] text-danger"
                                >{measurementErrors.length}</span
                              >
                            {/if}
                          </label>
                          <label
                            class="text-xs font-medium text-foreground-muted"
                            for={`measurement-width-${unit.id}`}
                          >
                            Ancho (m) *
                            <input
                              id={`measurement-width-${unit.id}`}
                              class={inputClass}
                              type="number"
                              min="0.000001"
                              step="any"
                              bind:value={widthM}
                              required
                              aria-invalid={measurementErrors.width ? 'true' : undefined}
                              aria-describedby={measurementErrors.width
                                ? `measurement-width-${unit.id}-error`
                                : undefined}
                            />
                            {#if measurementErrors.width}
                              <span
                                id={`measurement-width-${unit.id}-error`}
                                class="mt-1 block text-[11px] text-danger"
                                >{measurementErrors.width}</span
                              >
                            {/if}
                          </label>
                          <label
                            class="text-xs font-medium text-foreground-muted"
                            for={`measurement-height-${unit.id}`}
                          >
                            Alto (m) *
                            <input
                              id={`measurement-height-${unit.id}`}
                              class={inputClass}
                              type="number"
                              min="0.000001"
                              step="any"
                              bind:value={heightM}
                              required
                              aria-invalid={measurementErrors.height ? 'true' : undefined}
                              aria-describedby={measurementErrors.height
                                ? `measurement-height-${unit.id}-error`
                                : undefined}
                            />
                            {#if measurementErrors.height}
                              <span
                                id={`measurement-height-${unit.id}-error`}
                                class="mt-1 block text-[11px] text-danger"
                                >{measurementErrors.height}</span
                              >
                            {/if}
                          </label>
                        {/if}
                      </div>

                      <div class="mt-4 flex flex-wrap justify-end gap-2">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          disabled={savingUnitId === unit.id}
                          onclick={resetMeasurementForm}>Cancelar</Button
                        >
                        <Button type="submit" size="sm" disabled={savingUnitId === unit.id}>
                          {savingUnitId === unit.id ? 'Verificando…' : 'Confirmar medición'}
                        </Button>
                      </div>
                    </form>
                  </td>
                </tr>
              {/if}
              {#if splittingUnitId === unit.id && canPrepareSplit}
                <tr id={`split-${unit.id}`} class="block xl:table-row">
                  <td
                    colspan="8"
                    class="block bg-warning/5 px-2 py-3 xl:table-cell xl:px-4 xl:py-4"
                  >
                    <form
                      class="rounded-xl border border-warning/30 bg-surface p-4"
                      aria-label={`Dividir unidad ${unit.code}`}
                      onsubmit={(event) => {
                        event.preventDefault();
                        requestSplit(unit);
                      }}
                    >
                      <div
                        class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between"
                      >
                        <div>
                          <h4 class="text-sm font-semibold text-foreground">
                            Dividir unidad disponible
                          </h4>
                          <p class="mt-1 text-sm font-medium text-foreground">
                            {unit.product_name ?? 'Producto sin identificar'} · {unit.code}
                          </p>
                          <p class="mt-1 max-w-3xl text-xs leading-relaxed text-foreground-muted">
                            Operación opcional: crea otra unidad física y conserva el remanente en
                            esta. Ambas requerirán medidas y etiquetas vigentes antes de liberarlas.
                            Para terminar la revisión no necesitas dividir.
                          </p>
                        </div>
                        <Badge variant="warning">Revalidación requerida</Badge>
                      </div>

                      {#if splitError}
                        <div
                          class="mt-3 rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger"
                          role="alert"
                        >
                          {splitError}
                        </div>
                      {/if}

                      <div class="mt-4 grid gap-3 md:grid-cols-2">
                        <label
                          class="text-xs font-medium text-foreground-muted"
                          for={`split-quantity-${unit.id}`}
                        >
                          Cantidad para la nueva unidad · total {number(unit.quantity_base, 6)}
                          {baseUnitLabel(unit)}
                          <input
                            id={`split-quantity-${unit.id}`}
                            class={inputClass}
                            type="number"
                            min="0.000001"
                            max={unit.quantity_base - 0.000001}
                            step="0.000001"
                            bind:value={splitQuantityBase}
                            placeholder="Escribe la cantidad exacta"
                            required
                            disabled={savingUnitId != null}
                            oninput={() => (splitError = null)}
                          />
                        </label>
                        <label
                          class="text-xs font-medium text-foreground-muted"
                          for={`split-location-${unit.id}`}
                        >
                          Ubicación de la nueva unidad
                          <select
                            id={`split-location-${unit.id}`}
                            class={inputClass}
                            bind:value={splitDestinationLocationId}
                            required
                            disabled={savingUnitId != null || eligibleReleaseLocations.length === 0}
                            onchange={() => (splitError = null)}
                          >
                            <option value="">Seleccione ubicación activa</option>
                            {#each eligibleReleaseLocations as location (location.id)}
                              <option value={location.id}>{location.label}</option>
                            {/each}
                          </select>
                        </label>
                      </div>

                      {#if splitQuantityBase != null && Number.isFinite(splitQuantityBase) && splitQuantityBase > 0 && splitQuantityBase < unit.quantity_base}
                        <p
                          class="mt-3 rounded-lg border border-warning/20 bg-warning/5 px-3 py-2 text-xs text-foreground-muted"
                          role="status"
                        >
                          Resultado previsto: nueva unidad con {number(splitQuantityBase, 6)};
                          remanente {unit.code} con {number(
                            unit.quantity_base - splitQuantityBase,
                            6
                          )}. Las dos cantidades suman {number(unit.quantity_base, 6)}; esta unidad
                          no se elimina.
                        </p>
                      {/if}

                      <div class="mt-4 flex flex-wrap justify-end gap-2">
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          disabled={savingUnitId === unit.id}
                          onclick={cancelSplit}
                        >
                          Cancelar
                        </Button>
                        <Button
                          type="submit"
                          size="sm"
                          disabled={savingUnitId != null ||
                            eligibleReleaseLocations.length === 0 ||
                            splitQuantityBase == null ||
                            !Number.isFinite(splitQuantityBase) ||
                            splitQuantityBase <= 0 ||
                            splitQuantityBase >= unit.quantity_base}
                        >
                          Confirmar división
                        </Button>
                      </div>
                    </form>
                  </td>
                </tr>
              {/if}
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>
</Card>

<HandlingUnitLabelDialog
  unit={selectedQrUnit}
  {canVerify}
  contextKey={dialogContextKey}
  onclose={() => (selectedQrUnit = null)}
  onconfirmed={() => requestLoad()}
/>
