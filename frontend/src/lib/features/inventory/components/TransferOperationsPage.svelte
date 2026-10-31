<script lang="ts">
  import { browser } from '$app/environment';
  import { onDestroy, tick } from 'svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import { inventoryApi } from '$lib/features/inventory/services';
  import type { TransferHandlingUnit } from '$lib/features/inventory/types';
  import { listLocations } from '$lib/features/locations/services';
  import type { LocationOut } from '$lib/features/locations/types';
  import { getWarehouses } from '$lib/services/warehouses';
  import type { Warehouse } from '$lib/features/warehouses/types';
  import { company } from '$lib/stores/company.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import TransferDemandOverview from './TransferDemandOverview.svelte';
  import TransferPreparationDialog from './TransferPreparationDialog.svelte';
  import TransferDocumentList from './TransferDocumentList.svelte';
  import TransferLifecycleProgress from './TransferLifecycleProgress.svelte';
  import TransferVehicleCatalog from './TransferVehicleCatalog.svelte';
  import {
    inventoryTransfersApi,
    type InventoryTransfer,
    type TransferCreateInput,
    type TransferDemandRecord,
    type TransferLineInput,
    type TransferStatus,
    type TransferVehicle
  } from '../transfer-documents';
  import {
    allocateDemandQuantity,
    clearTransferAttempt,
    compareQuantities,
    formatQuantity,
    getOrCreateTransferAttempt,
    quantityFromScaled,
    quantityString,
    scaledQuantity,
    transferStatusLabel,
    type TransferAttempt
  } from '../transfer-operations';

  type Tab = 'supply' | 'documents' | 'vehicles';
  type CollectionState = 'loading' | 'loaded' | 'empty' | 'error';
  type DraftAllocation = { requestDetailId: string; quantity: string; requestCode: string };
  type DraftLine = {
    handlingUnitId: string;
    code: string;
    productName: string;
    sku: string | null;
    unitLabel: string;
    lotCode: string | null;
    availableQuantity: string;
    quantity: string;
    allocations: DraftAllocation[];
    excessReason: string;
    notes: string;
  };
  const statuses: Array<{ value: TransferStatus | ''; label: string }> = [
    { value: '', label: 'Todos los estados' },
    { value: 'preparation', label: 'En preparación' },
    { value: 'in_transit', label: 'En tránsito' },
    { value: 'received', label: 'Recibidos' },
    { value: 'closed_with_adjustment', label: 'Cerrado con ajuste' },
    { value: 'incident', label: 'Con incidencia' },
    { value: 'cancelled', label: 'Cancelados' }
  ];

  let activeTab = $state<Tab>('supply');
  let contextKey = $state('');
  let contextVersion = 0;
  let sourceLoadSequence = 0;
  let workspaceLoadContext = '';
  let warehouses = $state<Warehouse[]>([]);
  let sourceWarehouseId = $state('');
  let availableUnits = $state<TransferHandlingUnit[]>([]);
  let demands = $state<TransferDemandRecord[]>([]);
  let demandState = $state<CollectionState>('loading');
  let stockState = $state<CollectionState>('loading');
  let supplyError = $state<string | null>(null);
  let transfers = $state<InventoryTransfer[]>([]);
  let transfersState = $state<CollectionState>('loading');
  let transferError = $state<string | null>(null);
  let transferStatusFilter = $state<TransferStatus | ''>('');
  let transferPage = $state(1);
  let transfersHaveMore = $state(false);
  let loadingMoreTransfers = $state(false);
  let vehicles = $state<TransferVehicle[]>([]);
  let vehicleState = $state<CollectionState>('loading');
  let vehicleError = $state<string | null>(null);
  let vehicleCode = $state('');
  let vehicleName = $state('');
  let vehicleSaving = $state(false);
  let destinations = $state<Warehouse[]>([]);
  let demandBranchErrors = $state<string[]>([]);

  let selectedProductKey = $state('');
  let selectedDemandDetailId = $state('');
  let destinationWarehouseId = $state('');
  let draftNotes = $state('');
  let draftLines = $state<DraftLine[]>([]);
  let editingTransferId = $state('');
  let draftError = $state<string | null>(null);
  let draftSaving = $state(false);
  let requestedHandlingUnitId = $state('');
  let preparationOpen = $state(false);
  let preparationNotice = $state<string | null>(null);
  let preparationSavedMessage = $state<string | null>(null);

  let selectedTransferId = $state('');
  let selectedTransfer = $state<InventoryTransfer | null>(null);
  let detailLoading = $state(false);
  let detailError = $state<string | null>(null);
  let selectedVehicleId = $state('');
  let actionError = $state<string | null>(null);
  let actionNotice = $state<string | null>(null);
  let actionSaving = $state(false);
  let actionProgressMessage = $state('');
  let destinationLocations = $state<LocationOut[]>([]);
  let destinationLocationState = $state<CollectionState>('loaded');
  let receiptQuantities = $state<Record<string, string>>({});
  let receiptLocationIds = $state<Record<string, string>>({});
  let incidentReason = $state('');
  let incidentEvidence = $state('');
  let incidentResolution = $state<'resume_transit' | 'close_received'>('resume_transit');
  let incidentResolutionNotes = $state('');
  let showIncidentForm = $state(false);
  let showResolutionForm = $state(false);
  let pageSearch = $state('');
  let confirmationText = $state('');
  let pendingConfirmation: (() => Promise<void>) | null = null;
  let confirmationDialog = $state<HTMLDialogElement | null>(null);
  let confirmationReturnFocusTarget: HTMLElement | null = null;
  const inMemoryAttempts = new Map<string, TransferAttempt>();

  const canMoveInventory = $derived(permissions.hasPermission('inventory:move'));
  const canReceiveInventory = $derived(permissions.hasPermission('inventory:receive'));
  const canCreateAdjustment = $derived(permissions.hasPermission('inventory:adjust'));
  const canReadDestinationInventory = $derived(
    permissions.hasPermission('inventory:read') && permissions.hasPermission('warehouses.view')
  );
  const hasReceivedStock = $derived(
    selectedTransfer?.lines.some((line) => (scaledQuantity(line.quantity_received) ?? 0n) > 0n) ??
      false
  );
  const destinationInventoryHref = $derived(
    selectedTransfer?.destination_warehouse_id
      ? `/warehouses/${encodeURIComponent(selectedTransfer.destination_warehouse_id)}?tab=inventario`
      : null
  );
  const centralWarehouses = $derived(
    warehouses.filter((item) => item.isCentral && item.storageEligible)
  );
  const activeDemand = $derived(
    demands.find((item) => item.purchase_request_detail_id === selectedDemandDetailId) ?? null
  );
  const currentIncidents = $derived(selectedTransfer?.incidents ?? []);
  const openIncident = $derived(
    currentIncidents.find((incident) => incident.status === 'open') ?? null
  );
  const currentTransitQuantity = $derived(
    selectedTransfer?.lines.reduce(
      (total, line) => total + (scaledQuantity(line.quantity_in_transit) ?? 0n),
      0n
    ) ?? 0n
  );

  let supplyProducts = $derived.by(() => {
    const grouped = new Map<
      string,
      {
        key: string;
        inventoryItemId: string | null;
        productId: number;
        productName: string;
        sku: string | null;
        unitId: number;
        unitLabel: string;
        units: TransferHandlingUnit[];
        demands: TransferDemandRecord[];
      }
    >();
    const keyFor = (itemId: string | null, productId: number, unitId: number) =>
      itemId ? `item:${itemId}:unit:${unitId}` : `product:${productId}:unit:${unitId}`;

    for (const unit of availableUnits) {
      if (unit.product_id == null) continue;
      const key = keyFor(unit.inventory_item_id, unit.product_id, unit.base_unit_id);
      const row = grouped.get(key) ?? {
        key,
        inventoryItemId: unit.inventory_item_id,
        productId: unit.product_id,
        productName: unit.product_name ?? 'Producto sin nombre',
        sku: unit.product_sku,
        unitId: unit.base_unit_id,
        unitLabel: unit.base_unit_symbol ?? unit.base_unit_name ?? 'unidad base',
        units: [],
        demands: []
      };
      row.units.push(unit);
      grouped.set(key, row);
    }
    for (const demand of demands) {
      const key = keyFor(demand.inventory_item_id, demand.product_id, demand.unit_id);
      const row = grouped.get(key) ?? {
        key,
        inventoryItemId: demand.inventory_item_id,
        productId: demand.product_id,
        productName: demand.product_name || 'Producto sin nombre',
        sku: demand.sku,
        unitId: demand.unit_id,
        unitLabel: demand.unit_symbol || demand.unit_name || 'unidad base',
        units: [],
        demands: []
      };
      row.demands.push(demand);
      grouped.set(key, row);
    }
    return [...grouped.values()]
      .map((row) => ({
        ...row,
        availableQuantity: row.units.reduce(
          (total, unit) => total + (scaledQuantity(unit.quantity_base) ?? 0n),
          0n
        ),
        demands: [...row.demands].sort(
          (left, right) =>
            (left.required_date?.slice(0, 10) ?? '9999-12-31').localeCompare(
              right.required_date?.slice(0, 10) ?? '9999-12-31'
            ) || left.request_date.localeCompare(right.request_date)
        )
      }))
      .sort(
        (left, right) =>
          left.productName.localeCompare(right.productName, 'es-SV') ||
          left.sku?.localeCompare(right.sku ?? '') ||
          0
      );
  });
  const selectedProduct = $derived(
    supplyProducts.find((item) => item.key === selectedProductKey) ?? null
  );
  const preparationDestinations = $derived(
    activeDemand
      ? destinations.filter((item) => item.branchId === activeDemand.branch_id)
      : destinations
  );

  $effect(() => {
    const dialog = confirmationDialog;
    if (!confirmationText || !dialog || !browser) return;
    confirmationReturnFocusTarget =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    if (!dialog.open) dialog.showModal();
    queueMicrotask(() => dialog.querySelector<HTMLButtonElement>('button')?.focus());
    return () => {
      if (dialog.open) dialog.close();
      const target = confirmationReturnFocusTarget;
      confirmationReturnFocusTarget = null;
      if (target?.isConnected) queueMicrotask(() => target.focus());
    };
  });

  $effect(() => {
    const companyId = company.id;
    const branchId = branch.id;
    const allBranches = branch.accessAllBranches;
    const ready = branch.ready;
    const nextKey = companyId
      ? `${companyId}:${branchId ?? '__all__'}:${allBranches ? 'all' : 'scoped'}`
      : '';
    if (nextKey !== contextKey) {
      contextKey = nextKey;
      contextVersion += 1;
      workspaceLoadContext = '';
      resetOperationalState();
    }
    if (!ready || !companyId || !contextKey || workspaceLoadContext === contextKey) return;
    workspaceLoadContext = contextKey;
    void loadWorkspace(contextKey, contextVersion);
  });

  onDestroy(() => {
    contextVersion += 1;
  });

  function resetOperationalState() {
    sourceLoadSequence += 1;
    preparationSavedMessage = null;
    sourceWarehouseId = '';
    warehouses = [];
    destinations = [];
    availableUnits = [];
    demands = [];
    demandState = 'loading';
    stockState = 'loading';
    supplyError = null;
    demandBranchErrors = [];
    transfers = [];
    transfersState = 'loading';
    transferError = null;
    selectedTransferId = '';
    selectedTransfer = null;
    detailLoading = false;
    detailError = null;
    actionError = null;
    actionNotice = null;
    actionProgressMessage = '';
    actionSaving = false;
    destinationLocations = [];
    destinationLocationState = 'loading';
    receiptQuantities = {};
    receiptLocationIds = {};
    showIncidentForm = false;
    showResolutionForm = false;
    confirmationText = '';
    pendingConfirmation = null;
    vehicles = [];
    vehicleState = 'loading';
    vehicleError = null;
    selectedVehicleId = '';
    vehicleCode = '';
    vehicleName = '';
    draftSaving = false;
    activeTab = 'supply';
    clearDraft();
  }

  function isCurrent(key: string, version: number): boolean {
    return key === contextKey && version === contextVersion;
  }

  async function loadWorkspace(key: string, version: number) {
    try {
      const all: Warehouse[] = [];
      const scopedBranchId = branch.accessAllBranches
        ? undefined
        : (branch.id ?? branch.branches[0]?.id);
      if (!branch.accessAllBranches && !scopedBranchId) {
        throw new Error('Tu usuario no tiene sucursales autorizadas para consultar traslados.');
      }
      let pageNumber = 1;
      let pages = 1;
      do {
        const pageResult = await getWarehouses({
          branchId: scopedBranchId,
          page: pageNumber,
          size: 100,
          status: 'active'
        });
        all.push(...pageResult.items);
        pages = Math.max(1, pageResult.meta.pages);
        pageNumber += 1;
      } while (pageNumber <= pages && isCurrent(key, version));
      if (!isCurrent(key, version)) return;

      warehouses = all.filter((item) => item.status === 'active');
      destinations = warehouses
        .filter((item) => !item.isCentral && item.branchId && item.storageEligible)
        .sort((left, right) =>
          `${left.branchName} ${left.name}`.localeCompare(
            `${right.branchName} ${right.name}`,
            'es-SV'
          )
        );
      const query = browser ? new URLSearchParams(window.location.search) : new URLSearchParams();
      const preferredSource = query.get('warehouse_id');
      const nextSource = centralWarehouses.some((item) => item.id === preferredSource)
        ? preferredSource!
        : (centralWarehouses[0]?.id ?? '');
      sourceWarehouseId = nextSource;
      requestedHandlingUnitId = query.get('handling_unit_id') ?? '';

      await Promise.all([
        loadTransferPage(key, version, 1, true),
        loadSourceData(nextSource, key, version)
      ]);
      if (!isCurrent(key, version)) return;

      if (requestedHandlingUnitId) {
        const unit = availableUnits.find((item) => item.id === requestedHandlingUnitId);
        if (unit?.product_id != null) {
          selectedProductKey = productKey(
            unit.inventory_item_id,
            unit.product_id,
            unit.base_unit_id
          );
          destinationWarehouseId = '';
          draftLines = [draftLineFromUnit(unit)];
          draftError = null;
        } else {
          preparationNotice =
            'La unidad del enlace ya no está disponible en esta bodega. Selecciona otra unidad disponible para preparar el traslado.';
        }
      }
      if (canMoveInventory && centralWarehouses.length > 0) void loadVehicles(key, version);
    } catch (cause) {
      if (!isCurrent(key, version)) return;
      supplyError = message(cause, 'No se pudieron cargar las bodegas disponibles.');
      stockState = 'error';
      demandState = 'error';
      transfersState = 'error';
      transferError = supplyError;
    }
  }

  function productKey(itemId: string | null, productId: number, unitId: number): string {
    return itemId ? `item:${itemId}:unit:${unitId}` : `product:${productId}:unit:${unitId}`;
  }

  function message(cause: unknown, fallback: string): string {
    return cause instanceof Error ? cause.message : fallback;
  }

  function mayHaveCommitted(cause: unknown): boolean {
    if (cause && typeof cause === 'object' && 'status' in cause) {
      const status = Number((cause as { status?: unknown }).status);
      return status === 0 || status === 408 || status === 429 || status >= 500;
    }
    return true;
  }

  function receiptWasApplied(
    before: InventoryTransfer,
    after: InventoryTransfer,
    receivedLines: Array<{ transfer_detail_id: string; quantity_base: string }>
  ): boolean {
    return (
      receivedLines.length > 0 &&
      receivedLines.every((received) => {
        const previousLine = before.lines.find((line) => line.id === received.transfer_detail_id);
        const currentLine = after.lines.find((line) => line.id === received.transfer_detail_id);
        const requested = scaledQuantity(received.quantity_base);
        const previousReceived = scaledQuantity(previousLine?.quantity_received);
        const currentReceived = scaledQuantity(currentLine?.quantity_received);
        const previousTransit = scaledQuantity(previousLine?.quantity_in_transit);
        const currentTransit = scaledQuantity(currentLine?.quantity_in_transit);
        return (
          requested != null &&
          previousReceived != null &&
          currentReceived != null &&
          previousTransit != null &&
          currentTransit != null &&
          currentReceived - previousReceived === requested &&
          previousTransit - currentTransit === requested
        );
      })
    );
  }

  async function loadSourceData(warehouseId: string, key = contextKey, version = contextVersion) {
    const sequence = ++sourceLoadSequence;
    if (!warehouseId) {
      availableUnits = [];
      demands = [];
      stockState = 'empty';
      demandState = 'empty';
      return;
    }
    stockState = 'loading';
    demandState = 'loading';
    supplyError = null;
    demandBranchErrors = [];
    availableUnits = [];
    demands = [];
    const demandBranches = [
      ...new Set(
        destinations.map((item) => item.branchId).filter((id): id is string => Boolean(id))
      )
    ];
    const [stockResult, ...demandResults] = await Promise.allSettled([
      inventoryApi.listTransferUnits(warehouseId, 'available'),
      ...(canMoveInventory
        ? demandBranches.map((branchId) => inventoryTransfersApi.listDemand(branchId))
        : [])
    ]);
    if (
      !isCurrent(key, version) ||
      warehouseId !== sourceWarehouseId ||
      sequence !== sourceLoadSequence
    )
      return;
    if (stockResult.status === 'fulfilled') {
      availableUnits = stockResult.value;
      stockState = availableUnits.length ? 'loaded' : 'empty';
    } else {
      stockState = 'error';
      supplyError = message(stockResult.reason, 'No se pudo cargar el inventario liberado.');
    }

    if (!canMoveInventory) {
      demands = [];
      demandState = 'empty';
    } else {
      const resolved = demandResults.filter(
        (result): result is PromiseFulfilledResult<TransferDemandRecord[]> =>
          result.status === 'fulfilled'
      );
      const rejected = demandResults.filter((result) => result.status === 'rejected');
      demands = resolved.flatMap((result) => result.value);
      demandBranchErrors = rejected.map((result) =>
        message(result.reason, 'No se pudo consultar una sucursal.')
      );
      demandState =
        rejected.length === demandResults.length && demandResults.length
          ? 'error'
          : rejected.length
            ? 'loaded'
            : demands.length
              ? 'loaded'
              : 'empty';
    }
  }

  async function loadVehicles(key = contextKey, version = contextVersion) {
    vehicleState = 'loading';
    vehicleError = null;
    try {
      const result = await inventoryTransfersApi.listVehicles();
      if (!isCurrent(key, version)) return;
      vehicles = result;
      vehicleState = result.length ? 'loaded' : 'empty';
      if (!selectedVehicleId)
        selectedVehicleId = result.find((item) => item.status === 'active')?.id ?? '';
    } catch (cause) {
      if (!isCurrent(key, version)) return;
      vehicles = [];
      vehicleState = 'error';
      vehicleError = message(cause, 'No se pudo consultar el catálogo de vehículos.');
    }
  }

  async function loadTransferPage(
    key = contextKey,
    version = contextVersion,
    pageNumber = 1,
    replace = false
  ) {
    if (replace) {
      transfersState = 'loading';
      transferError = null;
      transfers = [];
      transferPage = 1;
    } else loadingMoreTransfers = true;
    try {
      const result = await inventoryTransfersApi.list({
        status: transferStatusFilter || undefined,
        page: pageNumber,
        size: 50
      });
      if (!isCurrent(key, version)) return;
      transfers = replace
        ? result
        : [
            ...transfers,
            ...result.filter((item) => !transfers.some((existing) => existing.id === item.id))
          ];
      transferPage = pageNumber;
      transfersHaveMore = result.length === 50;
      transfersState = transfers.length ? 'loaded' : 'empty';
    } catch (cause) {
      if (!isCurrent(key, version)) return;
      transfersState = 'error';
      transferError = message(cause, 'No se pudieron consultar los traslados.');
    } finally {
      loadingMoreTransfers = false;
    }
  }

  async function chooseSource(warehouseId: string) {
    sourceWarehouseId = warehouseId;
    clearDraft();
    await loadSourceData(warehouseId);
  }

  function draftLineFromUnit(unit: TransferHandlingUnit): DraftLine {
    return {
      handlingUnitId: unit.id,
      code: unit.code,
      productName: unit.product_name ?? 'Producto sin nombre',
      sku: unit.product_sku,
      unitLabel: unit.base_unit_symbol ?? unit.base_unit_name ?? 'unidad base',
      lotCode: unit.receipt_lot_code ?? unit.lot_code,
      availableQuantity: String(unit.quantity_base),
      quantity: '',
      allocations: [],
      excessReason: '',
      notes: ''
    };
  }

  function beginPreparation(productKeyValue: string, demand?: TransferDemandRecord) {
    if (!canMoveInventory || draftSaving || stockState === 'error' || stockState === 'loading')
      return;
    const product = supplyProducts.find((item) => item.key === productKeyValue);
    if (!product || product.units.length === 0 || (demand && demandState === 'error')) return;
    selectedProductKey = productKeyValue;
    selectedDemandDetailId = demand?.purchase_request_detail_id ?? '';
    destinationWarehouseId = demand
      ? (destinations.find((item) => item.branchId === demand.branch_id)?.id ?? '')
      : '';
    draftNotes = '';
    draftLines = [];
    editingTransferId = '';
    draftError = null;
    selectedTransferId = '';
    selectedTransfer = null;
    activeTab = 'supply';
    preparationNotice = null;
    preparationSavedMessage = null;
    const preferredUnit =
      product.units.find((item) => item.id === requestedHandlingUnitId) ??
      (product.units.length === 1 ? product.units[0] : null);
    if (preferredUnit) addDraftUnit(preferredUnit.id);
    preparationOpen = true;
  }

  function addDraftUnit(unitId: string) {
    if (draftLines.some((line) => line.handlingUnitId === unitId)) {
      draftLines = draftLines.filter((line) => line.handlingUnitId !== unitId);
      return;
    }
    const unit = availableUnits.find((item) => item.id === unitId);
    if (!unit) return;
    let line = draftLineFromUnit(unit);
    if (activeDemand) {
      line = {
        ...line,
        allocations: [
          {
            requestDetailId: activeDemand.purchase_request_detail_id,
            quantity: '0',
            requestCode: activeDemand.request_code
          }
        ]
      };
    }
    draftLines = [...draftLines, line];
  }

  function updateDraftLine(index: number, patch: Partial<DraftLine>) {
    draftLines = draftLines.map((line, current) =>
      current === index ? { ...line, ...patch } : line
    );
    draftError = null;
  }

  function allocationIssue(value: string): string | null {
    return !value.trim() || scaledQuantity(value) == null
      ? 'Indica cero o una cantidad positiva con hasta seis decimales.'
      : null;
  }

  function updateDraftAllocation(index: number, requestDetailId: string, quantity: string) {
    const line = draftLines[index];
    if (!line) return;
    updateDraftLine(index, {
      allocations: line.allocations.map((allocation) =>
        allocation.requestDetailId === requestDetailId ? { ...allocation, quantity } : allocation
      )
    });
  }

  async function refreshPreparationStock() {
    const expectedContext = contextKey;
    const expectedVersion = contextVersion;
    const origin = sourceWarehouseId;
    const editingId = editingTransferId;
    const productKeyValue = selectedProductKey;
    await loadSourceData(origin, expectedContext, expectedVersion);
    if (
      !isCurrent(expectedContext, expectedVersion) ||
      sourceWarehouseId !== origin ||
      !preparationOpen ||
      editingTransferId !== editingId ||
      selectedProductKey !== productKeyValue ||
      (stockState !== 'loaded' && stockState !== 'empty')
    )
      return;
    draftLines = draftLines.map((line) => ({
      ...line,
      availableQuantity: String(
        availableUnits.find((unit) => unit.id === line.handlingUnitId)?.quantity_base ?? '0'
      )
    }));
  }

  function updatePlannedQuantity(index: number, quantity: string) {
    const line = draftLines[index];
    if (!line) return;
    if (!activeDemand) {
      updateDraftLine(index, { quantity });
      return;
    }
    const allocatedElsewhere = draftLines.reduce((total, current, currentIndex) => {
      if (currentIndex === index) return total;
      return (
        total +
        current.allocations
          .filter(
            (allocation) => allocation.requestDetailId === activeDemand.purchase_request_detail_id
          )
          .reduce(
            (lineTotal, allocation) => lineTotal + (scaledQuantity(allocation.quantity) ?? 0n),
            0n
          )
      );
    }, 0n);
    const assigned = allocateDemandQuantity(
      quantity,
      activeDemand.quantity_pending,
      allocatedElsewhere
    );
    updateDraftLine(index, {
      quantity,
      allocations: [
        {
          requestDetailId: activeDemand.purchase_request_detail_id,
          requestCode: activeDemand.request_code,
          quantity: quantityFromScaled(assigned)
        }
      ]
    });
  }

  function clearDraft() {
    preparationOpen = false;
    preparationNotice = null;
    selectedProductKey = '';
    selectedDemandDetailId = '';
    destinationWarehouseId = '';
    draftNotes = '';
    draftLines = [];
    editingTransferId = '';
    draftError = null;
  }

  function closePreparation() {
    if (draftSaving) return;
    clearDraft();
    requestedHandlingUnitId = '';
  }

  function buildInput(): Omit<TransferCreateInput, 'idempotency_key'> | null {
    if (
      stockState === 'loading' ||
      stockState === 'error' ||
      (!editingTransferId && !selectedProduct)
    ) {
      draftError = 'Espera a que se consulten las existencias del producto antes de guardar.';
      return null;
    }
    if (
      !editingTransferId &&
      selectedDemandDetailId &&
      (!activeDemand || demandState === 'loading' || demandState === 'error')
    ) {
      draftError =
        'Espera a que se consulte de nuevo la solicitud antes de guardar la preparación.';
      return null;
    }
    if (
      !sourceWarehouseId ||
      !destinationWarehouseId ||
      sourceWarehouseId === destinationWarehouseId
    ) {
      draftError = 'Seleccione una bodega de origen y un destino diferente.';
      return null;
    }
    if (!preparationDestinations.some((item) => item.id === destinationWarehouseId)) {
      draftError = 'Selecciona una bodega habilitada de la sucursal destino de esta preparación.';
      return null;
    }
    if (draftLines.length === 0) {
      draftError = 'Agregue al menos una unidad logística al borrador.';
      return null;
    }
    const lines: TransferLineInput[] = [];
    let allocatedTotal = 0n;
    for (const [index, line] of draftLines.entries()) {
      const quantity = quantityString(line.quantity);
      const available = scaledQuantity(line.availableQuantity);
      const planned = quantity ? scaledQuantity(quantity) : null;
      if (!quantity || planned == null || available == null || planned > available) {
        draftError = `Revise la cantidad de ${line.code}; debe ser positiva y no superar ${formatQuantity(line.availableQuantity)} ${line.unitLabel}.`;
        return null;
      }
      if (line.allocations.some((allocation) => allocationIssue(allocation.quantity))) {
        draftError = `Revisa la asignación a solicitud de ${line.code}: usa cero o una cantidad positiva con hasta seis decimales.`;
        return null;
      }
      const allocations = line.allocations
        .map((allocation) => ({ allocation, quantity: quantityString(allocation.quantity) }))
        .filter((entry): entry is { allocation: DraftAllocation; quantity: string } =>
          Boolean(entry.quantity)
        );
      const allocationTotal = allocations.reduce(
        (sum, item) => sum + (scaledQuantity(item.quantity) ?? 0n),
        0n
      );
      if (allocationTotal > planned) {
        draftError = `La cantidad asignada a solicitud supera la cantidad preparada de ${line.code}.`;
        return null;
      }
      if (
        activeDemand &&
        allocations.some(
          (item) => item.allocation.requestDetailId !== activeDemand.purchase_request_detail_id
        )
      ) {
        draftError = 'Esta preparación solo puede vincular la línea de solicitud seleccionada.';
        return null;
      }
      allocatedTotal += allocationTotal;
      if (allocationTotal < planned && line.excessReason.trim().length < 3) {
        draftError = activeDemand
          ? `Documenta el motivo del excedente de ${line.code}.`
          : `Indica el motivo del envío manual de ${line.code}.`;
        return null;
      }
      lines.push({
        handling_unit_id: line.handlingUnitId,
        quantity_base: quantity,
        demand_allocations: allocations.map(({ allocation, quantity: allocatedQuantity }) => ({
          purchase_request_detail_id: allocation.requestDetailId,
          allocated_quantity: allocatedQuantity
        })),
        excess_reason: allocationTotal < planned ? line.excessReason.trim() : null,
        notes: line.notes.trim() || null
      });
      if (index > 500) {
        draftError = 'El documento supera el máximo de líneas admitido.';
        return null;
      }
    }
    if (activeDemand && allocatedTotal > (scaledQuantity(activeDemand.quantity_pending) ?? 0n)) {
      draftError =
        'La asignación supera el pendiente de asignar informado por el servidor. Actualice la demanda e intente de nuevo.';
      return null;
    }
    return {
      origin_warehouse_id: sourceWarehouseId,
      destination_warehouse_id: destinationWarehouseId,
      vehicle_id: null,
      notes: draftNotes.trim() || null,
      lines
    };
  }

  function attemptFor(action: string, fingerprint: string): TransferAttempt {
    let storage: Storage | null = null;
    if (browser) {
      try {
        storage = window.sessionStorage;
      } catch {
        // The in-memory attempt still protects retries while this page remains open.
      }
    }
    return getOrCreateTransferAttempt(
      storage,
      inMemoryAttempts,
      contextKey,
      action,
      fingerprint,
      () => crypto.randomUUID()
    );
  }

  function clearAttempt(action: string) {
    let storage: Storage | null = null;
    if (browser) {
      try {
        storage = window.sessionStorage;
      } catch {
        // The command has succeeded; in-memory cleanup still applies.
      }
    }
    clearTransferAttempt(storage, inMemoryAttempts, contextKey, action);
  }

  async function refreshAfterCommand(transferId: string, expectedContext: string) {
    if (expectedContext !== contextKey) return null;
    const authoritative = await inventoryTransfersApi.get(transferId);
    if (expectedContext !== contextKey) return null;
    selectedTransfer = authoritative;
    selectedTransferId = authoritative.id;
    transfers = [authoritative, ...transfers.filter((item) => item.id !== authoritative.id)];
    await Promise.all([
      loadTransferPage(contextKey, contextVersion, 1, true),
      loadSourceData(sourceWarehouseId)
    ]);
    if (authoritative.status === 'in_transit') await loadDestinationLocationsFor(authoritative);
    return authoritative;
  }

  async function savePreparation() {
    if (draftSaving || !canMoveInventory) return;
    const base = buildInput();
    if (!base) return;
    const fingerprint = JSON.stringify({
      ...base,
      transfer_id: editingTransferId || null
    });
    const actionName = editingTransferId ? `update:${editingTransferId}` : 'create';
    const attempt = attemptFor(actionName, fingerprint);
    const body: TransferCreateInput = { ...base, idempotency_key: attempt.idempotencyKey };
    const expectedContext = contextKey;
    draftSaving = true;
    draftError = null;
    actionProgressMessage = editingTransferId
      ? 'Actualizando la preparación…'
      : 'Guardando la preparación sin mover existencias…';
    try {
      const result = editingTransferId
        ? await inventoryTransfersApi.update(editingTransferId, body)
        : await inventoryTransfersApi.create(body);
      if (expectedContext !== contextKey) return;
      const authoritative = await refreshAfterCommand(result.id, expectedContext);
      if (!authoritative) return;
      clearAttempt(actionName);
      clearDraft();
      activeTab = 'documents';
      preparationSavedMessage = `${authoritative.code}: preparación guardada. El despacho se confirma por separado.`;
      await tick();
      if (expectedContext === contextKey && activeTab === 'documents') {
        const heading = document.getElementById('detail-heading');
        heading?.focus({ preventScroll: true });
        heading?.scrollIntoView({ block: 'start', behavior: 'instant' });
      }
    } catch (cause) {
      if (expectedContext === contextKey)
        draftError = message(
          cause,
          'No se pudo guardar la preparación. Puede reintentar sin cambiar sus datos.'
        );
    } finally {
      draftSaving = false;
      actionProgressMessage = '';
    }
  }

  async function openTransfer(transferId: string) {
    if (actionSaving || draftSaving) return;
    const expectedContext = contextKey;
    preparationSavedMessage = null;
    const expectedVersion = contextVersion;
    selectedTransferId = transferId;
    selectedTransfer = null;
    detailLoading = true;
    detailError = null;
    actionError = null;
    actionNotice = null;
    receiptQuantities = {};
    receiptLocationIds = {};
    try {
      const result = await inventoryTransfersApi.get(transferId);
      if (!isCurrent(expectedContext, expectedVersion) || selectedTransferId !== transferId) return;
      selectedTransfer = result;
      if (result.status === 'in_transit' || result.status === 'incident') {
        await loadDestinationLocationsFor(result, expectedContext, expectedVersion);
      }
    } catch (cause) {
      if (isCurrent(expectedContext, expectedVersion) && selectedTransferId === transferId) {
        detailError = message(cause, 'No se pudo abrir el traslado.');
      }
    } finally {
      if (isCurrent(expectedContext, expectedVersion) && selectedTransferId === transferId)
        detailLoading = false;
    }
  }

  async function loadDestinationLocationsFor(
    transfer: InventoryTransfer,
    expectedContext = contextKey,
    expectedVersion = contextVersion
  ) {
    destinationLocationState = 'loading';
    destinationLocations = [];
    try {
      const all: LocationOut[] = [];
      let currentPage = 1;
      let pages = 1;
      do {
        const pageResult = await listLocations(transfer.destination_warehouse_id, {
          page: currentPage,
          size: 100
        });
        if (!isCurrent(expectedContext, expectedVersion) || selectedTransferId !== transfer.id)
          return;
        all.push(
          ...pageResult.items.filter(
            (item) =>
              item.warehouse_id === transfer.destination_warehouse_id &&
              item.is_active &&
              item.lifecycle_status === 'active' &&
              item.storage_eligible &&
              item.location_type !== 'virtual'
          )
        );
        pages = Math.max(1, pageResult.meta.pages);
        currentPage += 1;
      } while (currentPage <= pages);
      if (!isCurrent(expectedContext, expectedVersion) || selectedTransferId !== transfer.id)
        return;
      destinationLocations = all.sort((left, right) =>
        left.code.localeCompare(right.code, 'es-SV')
      );
      destinationLocationState = destinationLocations.length ? 'loaded' : 'empty';
    } catch (cause) {
      if (!isCurrent(expectedContext, expectedVersion) || selectedTransferId !== transfer.id)
        return;
      destinationLocationState = 'error';
      detailError = message(cause, 'No se pudieron consultar las ubicaciones de recepción.');
    }
  }

  function confirmAction(label: string, description: string, action: () => Promise<void>) {
    confirmationText = `${label}: ${description}`;
    pendingConfirmation = action;
  }

  function dismissConfirmation() {
    confirmationText = '';
    pendingConfirmation = null;
  }

  async function runConfirmedAction() {
    const action = pendingConfirmation;
    if (!action || actionSaving) return;
    pendingConfirmation = null;
    confirmationText = '';
    await action();
  }

  async function cancelPreparation() {
    const transfer = selectedTransfer;
    if (!transfer || transfer.status !== 'preparation' || actionSaving || !canMoveInventory) return;
    await runTransferCommand('cancel', transfer, (key) =>
      inventoryTransfersApi.cancel(transfer.id, key)
    );
  }

  async function dispatchPreparation() {
    const transfer = selectedTransfer;
    if (
      !transfer ||
      transfer.status !== 'preparation' ||
      !selectedVehicleId ||
      actionSaving ||
      !canMoveInventory
    )
      return;
    await runTransferCommand(
      'dispatch',
      transfer,
      (key) => inventoryTransfersApi.dispatch(transfer.id, selectedVehicleId, key),
      {
        vehicle_id: selectedVehicleId
      }
    );
  }

  async function runTransferCommand(
    actionName: string,
    transfer: InventoryTransfer,
    command: (key: string) => Promise<InventoryTransfer>,
    fingerprintData: unknown = null
  ) {
    const expectedContext = contextKey;
    const fingerprint = JSON.stringify({ transfer_id: transfer.id, data: fingerprintData });
    const attempt = attemptFor(`${actionName}:${transfer.id}`, fingerprint);
    actionSaving = true;
    actionError = null;
    actionNotice = null;
    actionProgressMessage =
      (
        {
          cancel: 'Cancelando preparación…',
          dispatch: 'Confirmando despacho…',
          incident: 'Registrando incidencia…',
          'resolve-incident': 'Guardando resolución…'
        } as Record<string, string>
      )[actionName] ?? 'Procesando traslado…';
    try {
      const result = await command(attempt.idempotencyKey);
      if (expectedContext !== contextKey) return;
      const authoritative = await refreshAfterCommand(result.id, expectedContext);
      if (authoritative) clearAttempt(`${actionName}:${transfer.id}`);
    } catch (cause) {
      if (expectedContext === contextKey) {
        const failure = message(cause, 'No se pudo completar la operación.');
        if (mayHaveCommitted(cause)) {
          try {
            const authoritative = await refreshAfterCommand(transfer.id, expectedContext);
            if (authoritative && authoritative.status !== transfer.status) {
              clearAttempt(`${actionName}:${transfer.id}`);
              actionNotice = `${failure} Se consultó el estado y el traslado ya figura como ${transferStatusLabel(authoritative.status)}. No repitas esta acción.`;
              actionError = null;
            } else {
              actionError = `${failure} Se consultó el estado actual${authoritative ? ` (${transferStatusLabel(authoritative.status)})` : ''}; la clave de reintento se conserva. Revisa cantidades y estado antes de reintentar.`;
            }
          } catch {
            actionError = `${failure} No se pudo confirmar el estado. La clave de reintento se conserva; actualiza el documento antes de decidir si reintentas.`;
          }
        } else actionError = failure;
      }
    } finally {
      actionSaving = false;
      actionProgressMessage = '';
    }
  }

  function requestCancel() {
    if (!selectedTransfer) return;
    confirmAction(
      'Cancelar preparación',
      `se cancelará ${selectedTransfer.code}; no se moverá inventario y el registro permanecerá en el historial`,
      cancelPreparation
    );
  }

  function requestDispatch() {
    if (!selectedTransfer) return;
    const vehicle = vehicles.find((item) => item.id === selectedVehicleId);
    if (!vehicle || vehicle.status !== 'active') {
      actionError = 'Seleccione un vehículo activo antes de despachar.';
      return;
    }
    const summary = selectedTransfer.lines
      .map(
        (line) =>
          `${line.product_name} · ${formatQuantity(line.quantity_planned)} ${line.base_unit_symbol ?? line.base_unit_name ?? 'base'}`
      )
      .join('; ');
    confirmAction(
      'Confirmar despacho',
      `${selectedTransfer.origin_warehouse_name} → ${selectedTransfer.destination_warehouse_name} · ${vehicle.code} · ${summary}`,
      dispatchPreparation
    );
  }

  function editPreparation(transfer: InventoryTransfer) {
    if (transfer.status !== 'preparation' || !canMoveInventory || draftSaving) return;
    editingTransferId = transfer.id;
    sourceWarehouseId = transfer.origin_warehouse_id;
    destinationWarehouseId = transfer.destination_warehouse_id;
    draftNotes = transfer.notes ?? '';
    selectedDemandDetailId = '';
    selectedProductKey = '';
    draftLines = transfer.lines.map((line) => ({
      handlingUnitId: line.source_handling_unit_id,
      code: line.source_handling_unit_code ?? 'Unidad logística',
      productName: line.product_name,
      sku: line.sku,
      unitLabel: line.base_unit_symbol ?? line.base_unit_name ?? 'unidad base',
      lotCode: line.inventory_lot_detail_code,
      availableQuantity: '0',
      quantity: String(line.quantity_planned),
      allocations: line.demand_allocations.map((allocation) => ({
        requestDetailId: allocation.purchase_request_detail_id,
        quantity: String(allocation.allocated_quantity),
        requestCode: allocation.request_code
      })),
      excessReason: line.excess_reason ?? '',
      notes: line.notes ?? ''
    }));
    selectedTransfer = transfer;
    selectedTransferId = transfer.id;
    activeTab = 'supply';
    draftError = null;
    preparationOpen = true;
    void refreshPreparationStock();
  }

  async function confirmReceipt() {
    const transfer = selectedTransfer;
    if (!transfer || transfer.status !== 'in_transit' || actionSaving || !canReceiveInventory)
      return;
    const lines: Array<{
      transfer_detail_id: string;
      destination_location_id: string;
      quantity_base: string;
    }> = [];
    for (const line of transfer.lines) {
      const raw = receiptQuantities[line.id]?.trim() ?? '';
      if (!raw) continue;
      const quantity = quantityString(raw);
      const remaining = scaledQuantity(line.quantity_in_transit);
      const planned = quantity ? scaledQuantity(quantity) : null;
      if (!quantity || planned == null || remaining == null || planned > remaining) {
        actionError = `La cantidad recibida de ${line.product_name} debe ser positiva y no superar lo que sigue en tránsito.`;
        return;
      }
      const locationId = receiptLocationIds[line.id];
      if (!locationId || !destinationLocations.some((item) => item.id === locationId)) {
        actionError = `Seleccione una ubicación válida para ${line.product_name}.`;
        return;
      }
      lines.push({
        transfer_detail_id: line.id,
        destination_location_id: locationId,
        quantity_base: quantity
      });
    }
    if (!lines.length) {
      actionError = 'Escriba al menos una cantidad contada para registrar la recepción.';
      return;
    }
    const fingerprint = JSON.stringify({ transfer_id: transfer.id, lines });
    const actionName = `receive:${transfer.id}`;
    const attempt = attemptFor(actionName, fingerprint);
    const expectedContext = contextKey;
    actionSaving = true;
    actionError = null;
    actionNotice = null;
    actionProgressMessage = 'Registrando las cantidades recibidas…';
    try {
      const result = await inventoryTransfersApi.receive(
        transfer.id,
        attempt.idempotencyKey,
        lines
      );
      if (expectedContext !== contextKey) return;
      const authoritative = await refreshAfterCommand(result.id, expectedContext);
      if (authoritative) {
        clearAttempt(actionName);
        receiptQuantities = {};
        receiptLocationIds = {};
      }
    } catch (cause) {
      if (expectedContext === contextKey) {
        const failure = message(cause, 'No se pudo registrar la recepción.');
        if (mayHaveCommitted(cause)) {
          try {
            const authoritative = await refreshAfterCommand(transfer.id, expectedContext);
            if (authoritative && receiptWasApplied(transfer, authoritative, lines)) {
              clearAttempt(actionName);
              receiptQuantities = {};
              receiptLocationIds = {};
              actionNotice = `${failure} La consulta confirmó las cantidades recibidas; el estado quedó actualizado. No vuelvas a registrar esas unidades.`;
              actionError = null;
            } else {
              actionError = `${failure} Se consultó el estado actual${authoritative ? ` (${transferStatusLabel(authoritative.status)})` : ''}; la clave de reintento se conserva. Revisa el detalle antes de reintentar.`;
            }
          } catch {
            actionError = `${failure} No se pudo confirmar el estado. La clave de reintento se conserva; actualiza el documento antes de decidir si reintentas.`;
          }
        } else actionError = failure;
      }
    } finally {
      actionSaving = false;
      actionProgressMessage = '';
    }
  }

  async function reportIncident() {
    if (!canMoveInventory && !canReceiveInventory) return;
    if (!selectedTransfer || incidentReason.trim().length < 5 || actionSaving) return;
    const transfer = selectedTransfer;
    const body = {
      reason: incidentReason.trim(),
      evidence_reference: incidentEvidence.trim() || null
    };
    await runTransferCommand(
      'incident',
      transfer,
      (key) => inventoryTransfersApi.openIncident(transfer.id, { ...body, idempotency_key: key }),
      body
    );
    if (!actionError) {
      incidentReason = '';
      incidentEvidence = '';
      showIncidentForm = false;
    }
  }

  async function resolveTransferIncident() {
    if (!canMoveInventory && !canReceiveInventory) return;
    if (
      !selectedTransfer ||
      !openIncident ||
      incidentResolutionNotes.trim().length < 5 ||
      actionSaving
    )
      return;
    const transfer = selectedTransfer;
    const resolution = incidentResolution;
    if (resolution === 'close_received' && currentTransitQuantity > 0n) {
      actionError = 'No puede cerrarse como recibido mientras queden cantidades en tránsito.';
      return;
    }
    const body = { resolution, resolution_notes: incidentResolutionNotes.trim() };
    await runTransferCommand(
      'resolve-incident',
      transfer,
      (key) =>
        inventoryTransfersApi.resolveIncident(transfer.id, { ...body, idempotency_key: key }),
      body
    );
    if (!actionError) {
      incidentResolutionNotes = '';
      showResolutionForm = false;
    }
  }

  function formatDate(value: string | null | undefined): string {
    if (!value) return 'Sin fecha indicada';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'Fecha no disponible';
    return new Intl.DateTimeFormat('es-SV', {
      dateStyle: 'medium',
      timeZone: 'America/El_Salvador'
    }).format(date);
  }

  function documentSummary(transfer: InventoryTransfer): string {
    return transfer.lines
      .map(
        (line) =>
          `${line.product_name} (${formatQuantity(line.quantity_planned)} ${line.base_unit_symbol ?? line.base_unit_name ?? 'base'})`
      )
      .join(' · ');
  }

  function branchWarehouseName(warehouse: Warehouse): string {
    return [warehouse.branchName, warehouse.name].filter(Boolean).join(' · ');
  }

  async function saveVehicle(event: SubmitEvent) {
    event.preventDefault();
    if (vehicleSaving || !canMoveInventory) return;
    const code = vehicleCode.trim();
    const name = vehicleName.trim();
    if (!code || name.length < 2) {
      vehicleError = 'Indique el código y un nombre de al menos dos caracteres.';
      return;
    }
    vehicleSaving = true;
    vehicleError = null;
    try {
      await inventoryTransfersApi.createVehicle({ code, name });
      vehicleCode = '';
      vehicleName = '';
      await loadVehicles();
    } catch (cause) {
      vehicleError = message(cause, 'No se pudo registrar el vehículo.');
    } finally {
      vehicleSaving = false;
    }
  }

  async function changeVehicleStatus(vehicle: TransferVehicle) {
    if (!canMoveInventory || vehicleSaving) return;
    vehicleSaving = true;
    vehicleError = null;
    try {
      await inventoryTransfersApi.setVehicleStatus(
        vehicle.id,
        vehicle.status === 'active' ? 'inactive' : 'active'
      );
      await loadVehicles();
    } catch (cause) {
      vehicleError = message(cause, 'No se pudo cambiar el estado del vehículo.');
    } finally {
      vehicleSaving = false;
    }
  }

  function chooseDocumentFilter(value: string) {
    transferStatusFilter = value as TransferStatus | '';
    void loadTransferPage(contextKey, contextVersion, 1, true);
  }
</script>

<svelte:head>
  <title>Traslados de inventario | GestionaSV</title>
  <meta
    name="description"
    content="Preparación, despacho y recepción trazable de traslados entre bodegas."
  />
</svelte:head>

<main class="mx-auto w-full max-w-[1600px] space-y-6 p-4 sm:p-6 xl:p-8">
  <header class="flex flex-wrap items-start justify-between gap-4">
    <div class="space-y-2">
      <p class="text-xs font-semibold uppercase tracking-[0.16em] text-primary">
        Inventario · logística
      </p>
      <h1 class="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
        Traslados entre bodegas
      </h1>
      <p class="max-w-3xl text-sm text-foreground-muted sm:text-base">
        Prepara un documento desde la matriz, despacha con vehículo y registra en destino solo lo
        que llegó. Recibir deja la mercancía en cuarentena para su revisión.
      </p>
    </div>
    <Button
      variant="secondary"
      onclick={() =>
        void Promise.all([
          loadTransferPage(contextKey, contextVersion, 1, true),
          loadSourceData(sourceWarehouseId)
        ])}
    >
      Actualizar información
    </Button>
  </header>

  <nav
    class="transfer-tabs flex flex-nowrap gap-2 overflow-x-auto border-b border-border pb-3"
    aria-label="Secciones de traslados"
  >
    <button
      class:active-tab={activeTab === 'supply'}
      class="tab-button"
      type="button"
      aria-pressed={activeTab === 'supply'}
      onclick={() => (activeTab = 'supply')}>Abastecimiento</button
    >
    <button
      class:active-tab={activeTab === 'documents'}
      class="tab-button"
      type="button"
      aria-pressed={activeTab === 'documents'}
      onclick={() => (activeTab = 'documents')}>Documentos</button
    >
    {#if canMoveInventory && centralWarehouses.length > 0}
      <button
        class:active-tab={activeTab === 'vehicles'}
        class="tab-button"
        type="button"
        aria-pressed={activeTab === 'vehicles'}
        onclick={() => (activeTab = 'vehicles')}>Vehículos</button
      >
    {/if}
  </nav>

  {#if (actionSaving || draftSaving) && actionProgressMessage}
    <div
      class="flex items-center gap-3 rounded-xl border border-primary/25 bg-primary/5 px-4 py-3 text-sm text-foreground"
      role="status"
      aria-live="polite"
    >
      <span
        class="size-4 shrink-0 animate-spin rounded-full border-2 border-primary border-r-transparent motion-reduce:animate-none"
        aria-hidden="true"
      ></span>
      <span>{actionProgressMessage}</span>
    </div>
  {/if}

  {#if activeTab === 'supply'}
    <section class="space-y-5" aria-labelledby="supply-heading">
      <div class="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="supply-heading" class="text-lg font-semibold text-foreground">
            Planificar abastecimiento
          </h2>
          <p class="mt-1 text-sm text-foreground-muted">
            Consulta las existencias de la matriz y prepara el envío para cada sucursal.
          </p>
        </div>
        {#if centralWarehouses.length > 0 && canMoveInventory}
          <label class="w-full space-y-1 text-sm font-medium text-foreground sm:w-auto sm:min-w-64">
            Bodega de origen
            <select
              class="field-control"
              value={sourceWarehouseId}
              onchange={(event) => void chooseSource(event.currentTarget.value)}
            >
              {#each centralWarehouses as warehouse (warehouse.id)}
                <option value={warehouse.id}>{warehouse.code} · {warehouse.name}</option>
              {/each}
            </select>
          </label>
        {/if}
      </div>

      {#if !canMoveInventory}
        <div class="notice notice-info" role="status">
          Tu perfil puede consultar y recibir traslados autorizados. Para preparar o despachar desde
          la matriz se requiere el permiso de movimiento y el alcance correspondiente.
        </div>
      {:else if centralWarehouses.length === 0 && warehouses.length > 0}
        <div class="notice notice-info" role="status">
          No hay una bodega central disponible en tu alcance. Puedes consultar los documentos que
          correspondan a tu sucursal desde la sección Documentos.
        </div>
      {/if}

      {#if supplyError && stockState === 'error'}
        <div class="notice notice-danger" role="alert">
          No se pudo confirmar la existencia. {supplyError}
        </div>
      {/if}
      {#if demandBranchErrors.length > 0}
        <div class="notice notice-warning" role="alert">
          La demanda de {demandBranchErrors.length} sucursal(es) no pudo consultarse. No se interpreta
          como cero. Actualiza la información para reintentar.
        </div>
      {/if}
      {#if demandState === 'error'}
        <div class="notice notice-danger" role="alert">
          No se pudo consultar la demanda de las sucursales autorizadas. La preparación por
          solicitud queda bloqueada hasta que la consulta funcione.
        </div>
      {/if}
      {#if preparationNotice}<div class="notice notice-warning" role="status">
          {preparationNotice}
        </div>{/if}

      {#if canMoveInventory && centralWarehouses.length > 0}
        <TransferDemandOverview
          products={supplyProducts}
          {selectedProductKey}
          demandIncomplete={demandBranchErrors.length > 0}
          {stockState}
          {demandState}
          {supplyError}
          search={pageSearch}
          {canMoveInventory}
          onSearch={(value) => (pageSearch = value)}
          onPrepareManual={(productKey) => beginPreparation(productKey)}
          onPrepareDemand={(productKey, demand) => beginPreparation(productKey, demand)}
        />
      {/if}

      <TransferPreparationDialog
        open={preparationOpen}
        busy={draftSaving}
        onclose={closePreparation}
      >
        <section class="space-y-5 p-4 sm:p-6">
          <header class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2
                id="preparation-heading"
                tabindex="-1"
                class="text-lg font-semibold text-foreground"
              >
                {editingTransferId ? 'Editar preparación' : 'Preparar traslado'}
              </h2>
              {#if selectedProduct}<p class="mt-1 text-sm text-foreground-muted">
                  {selectedProduct.productName} · {selectedProduct.sku ??
                    `Producto ${selectedProduct.productId}`} · {selectedProduct.unitLabel}
                </p>{/if}
              {#if activeDemand}<p class="mt-1 text-sm text-foreground-muted">
                  {activeDemand.branch_name} · {activeDemand.request_code} · Pendiente de asignar {formatQuantity(
                    activeDemand.quantity_pending
                  )}
                  {activeDemand.unit_symbol ?? activeDemand.unit_name}
                </p>{/if}
              <p id="preparation-description" class="mt-2 text-xs leading-5 text-foreground-muted">
                Guarda un borrador con su destino y cantidades. El inventario se mueve cuando
                confirmas el despacho.
              </p>
            </div>
            <button
              class="text-sm text-foreground-muted underline underline-offset-4"
              type="button"
              disabled={draftSaving}
              onclick={closePreparation}>Cerrar formulario</button
            >
          </header>
          {#if stockState === 'loading'}
            <p class="notice notice-info" role="status">
              Actualizando las existencias de la bodega de origen…
            </p>
          {:else if stockState === 'error'}
            <div class="notice notice-danger space-y-2" role="alert">
              <p>No se pudo confirmar la existencia disponible. Tus cantidades se conservan.</p>
              <Button
                variant="secondary"
                disabled={draftSaving}
                onclick={() => void refreshPreparationStock()}>Reintentar existencias</Button
              >
            </div>
          {/if}
          {#if selectedDemandDetailId && demandState !== 'loading' && !activeDemand}
            <p class="notice notice-warning" role="alert">
              La solicitud seleccionada no está disponible en la consulta actual. Actualiza los
              saldos o descarta este formulario para elegir otra solicitud.
            </p>
          {/if}
          <fieldset
            disabled={draftSaving || stockState === 'loading' || stockState === 'error'}
            class="min-w-0 space-y-4"
          >
            <legend class="sr-only">Destino y unidades del traslado</legend>
            <div class="grid gap-4 lg:grid-cols-2">
              <label class="space-y-1 text-sm font-medium text-foreground"
                >Bodega de origen
                <select class="field-control" value={sourceWarehouseId} disabled>
                  {#each centralWarehouses as warehouse (warehouse.id)}<option value={warehouse.id}
                      >{warehouse.code} · {warehouse.name}</option
                    >{/each}
                </select>
              </label>
              <label class="space-y-1 text-sm font-medium text-foreground"
                >Bodega de sucursal destino
                <select
                  class="field-control"
                  bind:value={destinationWarehouseId}
                  disabled={preparationDestinations.length === 0}
                >
                  <option value="">Seleccione destino</option>
                  {#each preparationDestinations as warehouse (warehouse.id)}<option
                      value={warehouse.id}>{branchWarehouseName(warehouse)}</option
                    >{/each}
                </select>
              </label>
            </div>
            {#if preparationDestinations.length === 0}<p class="notice notice-warning" role="alert">
                No hay una bodega de destino habilitada{activeDemand
                  ? ` en ${activeDemand.branch_name}`
                  : ''}. Revisa su configuración en Almacenes antes de guardar.
              </p>{/if}
            {#if selectedProduct && !editingTransferId}
              <div class="space-y-3">
                <h3 class="font-medium text-foreground">Elige las unidades y cuánto enviar</h3>
                {#if selectedProduct.units.length === 0}<p class="text-sm text-warning">
                    No hay unidades disponibles para preparar.
                  </p>{/if}
                {#each selectedProduct.units as unit (unit.id)}
                  {@const selected = draftLines.some((line) => line.handlingUnitId === unit.id)}
                  <article
                    class="grid min-w-0 gap-3 rounded-xl border border-border bg-surface p-3 lg:grid-cols-[minmax(0,1fr)_150px_150px] lg:items-center"
                  >
                    <label class="flex min-w-0 items-start gap-3"
                      ><input
                        class="mt-1"
                        type="checkbox"
                        checked={selected}
                        onchange={() => addDraftUnit(unit.id)}
                      /><span
                        ><span class="block break-all font-mono text-sm font-medium text-foreground"
                          >{unit.code}</span
                        ><span class="block break-all text-xs text-foreground-muted"
                          >Lote {unit.receipt_lot_code ?? unit.lot_code ?? 'sin lote'} · Disponible {formatQuantity(
                            unit.quantity_base
                          )}
                          {unit.base_unit_symbol ?? unit.base_unit_name ?? 'base'}</span
                        ></span
                      ></label
                    >
                    {#if selected}
                      {@const index = draftLines.findIndex(
                        (line) => line.handlingUnitId === unit.id
                      )}
                      <label class="text-xs font-medium text-foreground-muted"
                        >Cantidad a preparar ({selectedProduct.unitLabel})
                        <input
                          class="field-control mt-1"
                          type="number"
                          min="0.000001"
                          max={unit.quantity_base}
                          step="0.000001"
                          value={draftLines[index]?.quantity ?? ''}
                          oninput={(event) =>
                            updatePlannedQuantity(index, event.currentTarget.value)}
                        />
                      </label>
                      {#if activeDemand}
                        <label class="text-xs font-medium text-foreground-muted"
                          >Asignar a solicitud
                          <input
                            class="field-control mt-1"
                            type="number"
                            min="0"
                            step="0.000001"
                            disabled={!activeDemand}
                            aria-invalid={Boolean(
                              allocationIssue(draftLines[index]?.allocations[0]?.quantity ?? '')
                            )}
                            aria-describedby={allocationIssue(
                              draftLines[index]?.allocations[0]?.quantity ?? ''
                            )
                              ? `allocation-error-${unit.id}`
                              : undefined}
                            value={draftLines[index]?.allocations[0]?.quantity ?? ''}
                            oninput={(event) => {
                              const current = draftLines[index];
                              if (current && activeDemand)
                                updateDraftLine(index, {
                                  allocations: [
                                    {
                                      ...current.allocations[0],
                                      requestDetailId: activeDemand.purchase_request_detail_id,
                                      requestCode: activeDemand.request_code,
                                      quantity: event.currentTarget.value
                                    }
                                  ]
                                });
                            }}
                          />
                        </label>
                        {#if allocationIssue(draftLines[index]?.allocations[0]?.quantity ?? '')}
                          <p
                            id={`allocation-error-${unit.id}`}
                            class="text-xs text-foreground lg:col-span-full"
                            role="alert"
                          >
                            {allocationIssue(draftLines[index]?.allocations[0]?.quantity ?? '')}
                          </p>
                        {/if}
                      {/if}
                      {#if (scaledQuantity(draftLines[index]?.quantity) ?? 0n) > (scaledQuantity(draftLines[index]?.allocations[0]?.quantity || '0') ?? 0n)}
                        <label class="text-xs font-medium text-foreground-muted lg:col-span-full"
                          >{activeDemand ? 'Motivo del excedente' : 'Motivo del envío manual'}
                          <input
                            class="field-control mt-1"
                            type="text"
                            maxlength="2000"
                            value={draftLines[index]?.excessReason ?? ''}
                            placeholder={activeDemand
                              ? 'Explica la cantidad adicional a lo solicitado'
                              : 'Ej. Abastecimiento preventivo de sucursal'}
                            oninput={(event) =>
                              updateDraftLine(index, { excessReason: event.currentTarget.value })}
                          />
                        </label>
                      {/if}
                    {/if}
                  </article>
                {/each}
              </div>
            {/if}
            {#if editingTransferId}
              <div class="space-y-3">
                <h3 class="font-medium text-foreground">Líneas conservadas en el documento</h3>
                {#each draftLines as line, index (line.handlingUnitId)}
                  <article
                    class="grid min-w-0 gap-3 rounded-xl border border-border bg-surface p-3 lg:grid-cols-[minmax(0,1fr)_180px_minmax(0,1fr)] lg:items-center"
                  >
                    <div>
                      <p class="font-medium text-foreground">{line.productName}</p>
                      <p class="break-all font-mono text-xs text-foreground-muted">
                        {line.sku ?? 'SKU sin registrar'} · {line.code} · Lote {line.lotCode ??
                          'sin lote'}
                      </p>
                      <p class="mt-1 text-xs text-foreground-muted">
                        {#if stockState === 'loaded' || stockState === 'empty'}
                          Disponible ahora: {formatQuantity(line.availableQuantity)}
                          {line.unitLabel}. {compareQuantities(line.availableQuantity, '0') === 0
                            ? 'La unidad ya no está disponible para despacho; revisa o cancela esta preparación desde Documentos.'
                            : ''}
                        {:else}Existencia pendiente de consultar.{/if}
                      </p>
                    </div>
                    <label class="text-xs font-medium text-foreground-muted"
                      >Cantidad planeada
                      <input
                        class="field-control mt-1"
                        type="number"
                        min="0.000001"
                        max={line.availableQuantity}
                        step="0.000001"
                        value={line.quantity}
                        oninput={(event) =>
                          updateDraftLine(index, { quantity: event.currentTarget.value })}
                      />
                    </label>
                    <div class="min-w-0 space-y-2">
                      {#each line.allocations as allocation (allocation.requestDetailId)}
                        <label class="block text-xs font-medium text-foreground-muted">
                          Asignado a {allocation.requestCode} ({line.unitLabel})
                          <input
                            class="field-control mt-1"
                            type="number"
                            min="0"
                            max={line.quantity}
                            step="0.000001"
                            value={allocation.quantity}
                            aria-invalid={Boolean(allocationIssue(allocation.quantity))}
                            aria-describedby={allocationIssue(allocation.quantity)
                              ? `allocation-error-${line.handlingUnitId}-${allocation.requestDetailId}`
                              : undefined}
                            oninput={(event) =>
                              updateDraftAllocation(
                                index,
                                allocation.requestDetailId,
                                event.currentTarget.value
                              )}
                          />
                        </label>
                        {#if allocationIssue(allocation.quantity)}<p
                            id={`allocation-error-${line.handlingUnitId}-${allocation.requestDetailId}`}
                            class="text-xs text-foreground"
                            role="alert"
                          >
                            {allocationIssue(allocation.quantity)}
                          </p>{/if}
                      {:else}
                        <p class="text-xs text-foreground-muted">
                          Sin solicitud vinculada. Indica el motivo del envío manual.
                        </p>
                      {/each}
                    </div>
                    {#if (scaledQuantity(line.quantity) ?? 0n) > line.allocations.reduce((sum, allocation) => sum + (scaledQuantity(allocation.quantity) ?? 0n), 0n)}
                      <label class="text-xs font-medium text-foreground-muted lg:col-span-full"
                        >Motivo del excedente
                        <input
                          class="field-control mt-1"
                          type="text"
                          maxlength="2000"
                          value={line.excessReason}
                          oninput={(event) =>
                            updateDraftLine(index, { excessReason: event.currentTarget.value })}
                        />
                      </label>
                    {/if}
                  </article>
                {/each}
              </div>
            {/if}
            <label class="block space-y-1 text-sm font-medium text-foreground"
              >Notas de la preparación
              <textarea
                class="field-control min-h-20"
                maxlength="4000"
                bind:value={draftNotes}
                placeholder="Instrucciones para el despacho o recepción"
              ></textarea>
            </label>
            {#if draftError}<p class="notice notice-danger" role="alert">{draftError}</p>{/if}
          </fieldset>
          <div
            class="sticky -bottom-4 -mx-4 flex flex-wrap justify-end gap-2 border-t border-border bg-surface p-4 sm:-bottom-6 sm:-mx-6 sm:p-5"
          >
            <Button
              variant="ghost"
              class="mr-auto"
              disabled={draftSaving || stockState === 'loading'}
              onclick={() => void refreshPreparationStock()}>Actualizar saldos</Button
            >
            <Button variant="secondary" disabled={draftSaving} onclick={closePreparation}
              >Descartar formulario</Button
            >
            <Button
              disabled={draftSaving ||
                stockState === 'loading' ||
                stockState === 'error' ||
                !canMoveInventory ||
                !sourceWarehouseId ||
                !destinationWarehouseId ||
                draftLines.length === 0}
              onclick={() => void savePreparation()}
              >{draftSaving
                ? 'Guardando…'
                : editingTransferId
                  ? 'Guardar cambios'
                  : 'Guardar en preparación'}</Button
            >
          </div>
        </section>
      </TransferPreparationDialog>
    </section>
  {:else if activeTab === 'documents'}
    <div class="space-y-5">
      {#if preparationSavedMessage}<p class="notice notice-success" role="status">
          {preparationSavedMessage}
        </p>{/if}
      <TransferDocumentList
        {transfers}
        state={transfersState}
        error={transferError}
        filter={transferStatusFilter}
        {statuses}
        hasMore={transfersHaveMore}
        loadingMore={loadingMoreTransfers}
        busy={actionSaving || draftSaving}
        {formatDate}
        {documentSummary}
        onFilter={chooseDocumentFilter}
        onRetry={() => void loadTransferPage(contextKey, contextVersion, 1, true)}
        onOpen={(transferId) => void openTransfer(transferId)}
        onLoadMore={() => void loadTransferPage(contextKey, contextVersion, transferPage + 1)}
      />

      {#if selectedTransferId}
        <section
          class="space-y-5 rounded-2xl border border-border bg-surface p-4 sm:p-6"
          aria-labelledby="detail-heading"
        >
          {#if detailLoading}
            <p class="text-sm text-foreground-muted" role="status">Abriendo documento…</p>
          {:else if detailError && !selectedTransfer}
            <p class="notice notice-danger" role="alert">{detailError}</p>
          {:else if selectedTransfer}
            <header class="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p class="font-mono text-sm text-primary">{selectedTransfer.code}</p>
                <h2
                  id="detail-heading"
                  tabindex="-1"
                  class="mt-1 scroll-mt-24 text-xl font-semibold text-foreground"
                >
                  {selectedTransfer.origin_warehouse_name} → {selectedTransfer.destination_warehouse_name}
                </h2>
                <p class="mt-1 text-sm text-foreground-muted">
                  Creado {formatDate(selectedTransfer.created_at)} · {transferStatusLabel(
                    selectedTransfer.status
                  )}
                </p>
              </div>
              <button
                class="text-sm text-foreground-muted underline underline-offset-4"
                type="button"
                onclick={() => {
                  selectedTransferId = '';
                  selectedTransfer = null;
                }}>Cerrar detalle</button
              >
            </header>
            {#if selectedTransfer.status === 'preparation' || selectedTransfer.status === 'in_transit' || selectedTransfer.status === 'received'}
              <TransferLifecycleProgress status={selectedTransfer.status} />
            {/if}
            {#if selectedTransfer.notes}<p
                class="rounded-xl bg-surface-muted p-3 text-sm text-foreground-muted"
              >
                {selectedTransfer.notes}
              </p>{/if}
            <div class="space-y-3">
              <h3 class="font-semibold text-foreground">Productos y avance</h3>
              {#each selectedTransfer.lines as line (line.id)}
                <article class="rounded-xl border border-border p-3 sm:p-4">
                  <div class="flex flex-wrap justify-between gap-3">
                    <div>
                      <p class="font-medium text-foreground">{line.product_name}</p>
                      <p class="font-mono text-xs text-foreground-muted">
                        {line.sku ?? 'SKU sin registrar'} · {line.presentation_name ??
                          line.base_unit_symbol ??
                          line.base_unit_name ??
                          'unidad base'} · {line.source_handling_unit_code ?? 'HU sin código'} · Lote
                        {line.inventory_lot_detail_code ?? 'sin lote'}
                      </p>
                    </div>
                    <p class="text-right text-sm text-foreground">
                      Planeado {formatQuantity(line.quantity_planned)}<span
                        class="block text-xs text-foreground-muted"
                        >Despachado {formatQuantity(line.quantity_dispatched)} · Recibido {formatQuantity(
                          line.quantity_received
                        )} · En tránsito {formatQuantity(line.quantity_in_transit)}</span
                      ><span class="block text-xs text-foreground-muted"
                        >Faltante documentado {formatQuantity(line.quantity_adjusted_out)}
                        {line.base_unit_symbol ?? line.base_unit_name ?? 'base'} · Devuelto {formatQuantity(
                          line.quantity_returned
                        )}
                        {line.base_unit_symbol ?? line.base_unit_name ?? 'base'}</span
                      >
                    </p>
                  </div>
                  {#if line.demand_allocations.length}<ul
                      class="mt-3 space-y-1 border-t border-border pt-3 text-xs text-foreground-muted"
                    >
                      {#each line.demand_allocations as allocation (allocation.purchase_request_detail_id)}<li
                        >
                          {allocation.branch_name} · {allocation.request_code}: asignado {formatQuantity(
                            allocation.allocated_quantity
                          )}, despachado {formatQuantity(allocation.quantity_dispatched)}, recibido {formatQuantity(
                            allocation.quantity_received
                          )}
                        </li>{/each}
                    </ul>{/if}
                  {#if line.receipts.length}<div class="mt-3 border-t border-border pt-3">
                      <p
                        class="text-xs font-semibold uppercase tracking-wide text-foreground-muted"
                      >
                        Historial de recepción
                      </p>
                      <ul class="mt-2 space-y-1 text-xs text-foreground-muted">
                        {#each line.receipts as receipt (receipt.id)}<li>
                            {formatQuantity(receipt.quantity_received)}
                            {line.base_unit_symbol ?? line.base_unit_name ?? 'base'} · {formatDate(
                              receipt.received_at
                            )} · {receipt.handling_unit_code ?? 'HU creada por recepción'}
                          </li>{/each}
                      </ul>
                    </div>{/if}
                </article>
              {/each}
            </div>

            {#if selectedTransfer.status === 'preparation'}
              <div
                class="grid gap-4 rounded-xl border border-primary/20 bg-primary/5 p-4 lg:grid-cols-[1fr_auto] lg:items-end"
              >
                <label class="space-y-1 text-sm font-medium text-foreground"
                  >Vehículo activo para el despacho
                  <select
                    class="field-control"
                    bind:value={selectedVehicleId}
                    disabled={!canMoveInventory || vehicleState === 'error'}
                    ><option value="">Seleccione vehículo</option
                    >{#each vehicles.filter((item) => item.status === 'active') as vehicle (vehicle.id)}<option
                        value={vehicle.id}>{vehicle.code} · {vehicle.name}</option
                      >{/each}</select
                  >
                </label>
                <div class="flex flex-wrap gap-2">
                  <Button
                    variant="secondary"
                    disabled={!canMoveInventory || actionSaving}
                    onclick={() => editPreparation(selectedTransfer!)}>Editar preparación</Button
                  ><Button
                    variant="secondary"
                    disabled={!canMoveInventory || actionSaving}
                    onclick={requestCancel}>Cancelar preparación</Button
                  ><Button
                    disabled={!canMoveInventory || actionSaving || !selectedVehicleId}
                    onclick={requestDispatch}>Confirmar despacho</Button
                  >
                </div>
              </div>
              <p class="text-xs text-foreground-muted">
                El despacho valida la disponibilidad de nuevo. La cantidad se moverá a tránsito solo
                después de confirmar esta acción.
              </p>
            {:else if selectedTransfer.status === 'in_transit'}
              <div class="rounded-xl border border-warning/30 bg-warning/5 p-4">
                <p class="font-medium text-foreground">Recepción en destino</p>
                <p class="mt-1 text-sm text-foreground-muted">
                  Deja vacías las cantidades que todavía no llegaron. Cada cantidad registrada pasa
                  a cuarentena; después se verifica la HU y su etiqueta desde Almacenes.
                </p>
              </div>
              {#if !canReceiveInventory}<div class="notice notice-warning" role="status">
                  Tu perfil puede consultar el documento, pero requiere el permiso de recepción para
                  registrar cantidades.
                </div>{/if}
              {#if destinationLocationState === 'loading'}<p class="text-sm text-foreground-muted">
                  Consultando ubicaciones de la bodega destino…
                </p>{:else if destinationLocationState === 'error'}<p
                  class="notice notice-danger"
                  role="alert"
                >
                  No se pudieron consultar ubicaciones válidas. No se puede registrar una recepción
                  hasta resolverlo. {detailError}
                </p>{:else if destinationLocations.length === 0}<p
                  class="notice notice-warning"
                  role="status"
                >
                  La bodega destino no tiene ubicaciones activas disponibles para recepción.
                </p>{/if}
              <div class="space-y-3">
                {#each selectedTransfer.lines.filter((line) => compareQuantities(line.quantity_in_transit, '0') > 0) as line (line.id)}
                  <article
                    class="grid gap-3 rounded-xl border border-border p-3 lg:grid-cols-[minmax(220px,1.2fr)_150px_minmax(220px,1fr)] lg:items-end"
                  >
                    <div>
                      <p class="font-medium text-foreground">{line.product_name}</p>
                      <p class="font-mono text-xs text-foreground-muted">
                        {line.sku ?? 'SKU sin registrar'} · {line.transit_handling_unit_code ??
                          'HU en tránsito'}
                      </p>
                      <p class="mt-1 text-xs text-foreground-muted">
                        En tránsito: {formatQuantity(line.quantity_in_transit)}
                        {line.base_unit_symbol ?? line.base_unit_name ?? 'base'}
                      </p>
                    </div>
                    <label class="text-xs font-medium text-foreground-muted"
                      >Cantidad contada ahora
                      <input
                        class="field-control mt-1"
                        type="number"
                        min="0.000001"
                        max={line.quantity_in_transit}
                        step="0.000001"
                        value={receiptQuantities[line.id] ?? ''}
                        oninput={(event) =>
                          (receiptQuantities = {
                            ...receiptQuantities,
                            [line.id]: event.currentTarget.value
                          })}
                      />
                    </label>
                    <label class="text-xs font-medium text-foreground-muted"
                      >Ubicación de recepción / cuarentena
                      <select
                        class="field-control mt-1"
                        value={receiptLocationIds[line.id] ?? ''}
                        onchange={(event) =>
                          (receiptLocationIds = {
                            ...receiptLocationIds,
                            [line.id]: event.currentTarget.value
                          })}
                        ><option value="">Seleccione ubicación</option
                        >{#each destinationLocations as location (location.id)}<option
                            value={location.id}>{location.code} · {location.location_type}</option
                          >{/each}</select
                      >
                    </label>
                  </article>
                {/each}
              </div>
              <div class="flex flex-wrap justify-end gap-2">
                <Button
                  variant="secondary"
                  disabled={actionSaving || (!canMoveInventory && !canReceiveInventory)}
                  onclick={() => {
                    showIncidentForm = !showIncidentForm;
                    showResolutionForm = false;
                  }}>Reportar incidencia</Button
                ><Button
                  disabled={!canReceiveInventory ||
                    actionSaving ||
                    destinationLocationState !== 'loaded' ||
                    !selectedTransfer.lines.some((line) =>
                      Boolean(receiptQuantities[line.id]?.trim())
                    )}
                  onclick={() => void confirmReceipt()}
                  >{actionSaving ? 'Registrando…' : 'Confirmar cantidades recibidas'}</Button
                >
              </div>
              {#if showIncidentForm}<form
                  class="grid gap-3 rounded-xl border border-warning/30 p-4 lg:grid-cols-2"
                  onsubmit={(event) => {
                    event.preventDefault();
                    void reportIncident();
                  }}
                >
                  <label class="space-y-1 text-sm font-medium text-foreground lg:col-span-2"
                    >Motivo de la incidencia<textarea
                      class="field-control min-h-20"
                      minlength="5"
                      maxlength="4000"
                      required
                      bind:value={incidentReason}
                    ></textarea></label
                  ><label class="space-y-1 text-sm font-medium text-foreground lg:col-span-2"
                    >Referencia de evidencia (opcional)<input
                      class="field-control"
                      maxlength="500"
                      bind:value={incidentEvidence}
                    /></label
                  >
                  <div class="flex justify-end gap-2 lg:col-span-2">
                    <Button variant="secondary" onclick={() => (showIncidentForm = false)}
                      >Cerrar</Button
                    ><Button
                      type="submit"
                      disabled={actionSaving || incidentReason.trim().length < 5}
                      >Guardar incidencia</Button
                    >
                  </div>
                </form>{/if}
            {:else if selectedTransfer.status === 'incident'}
              {#if openIncident}
                <div class="rounded-xl border border-warning/30 bg-warning/5 p-4">
                  <p class="font-medium text-foreground">Incidencia abierta</p>
                  <p class="mt-1 text-sm text-foreground-muted">
                    {openIncident.reason}{openIncident.evidence_reference
                      ? ` · Evidencia ${openIncident.evidence_reference}`
                      : ''}
                  </p>
                  <p class="mt-2 text-xs text-foreground-muted">
                    Las cantidades siguen en tránsito hasta que se reciba o se resuelva con una
                    acción autorizada. No se registra pérdida desde esta pantalla.
                  </p>
                  {#if canCreateAdjustment && selectedTransfer.lines.some((line) => compareQuantities(line.quantity_in_transit, '0') > 0)}
                    <div class="mt-4 space-y-2 border-t border-border pt-3">
                      <h3 class="text-sm font-semibold text-foreground">Faltantes por línea</h3>
                      <p class="text-xs text-foreground-muted">
                        Abre un borrador enlazado a la incidencia para justificar solo la cantidad
                        que sigue en tránsito. La recepción conserva su cantidad real.
                      </p>
                      {#each selectedTransfer.lines.filter((line) => compareQuantities(line.quantity_in_transit, '0') > 0) as line (line.id)}
                        <div
                          class="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface p-3"
                        >
                          <div>
                            <p class="text-sm font-medium text-foreground">{line.product_name}</p>
                            <p class="text-xs text-foreground-muted">
                              {line.transit_handling_unit_code ?? 'HU en tránsito'} · {formatQuantity(
                                line.quantity_in_transit
                              )}
                              {line.base_unit_symbol ?? line.base_unit_name ?? 'unidad base'}
                            </p>
                          </div>
                          <a
                            class="inline-flex h-9 items-center rounded-lg border border-border bg-surface-elevated px-3 text-sm font-medium text-foreground hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                            href={`/inventory/adjustments/new?transfer_id=${encodeURIComponent(selectedTransfer.id)}&incident_id=${encodeURIComponent(openIncident.id)}&detail_id=${encodeURIComponent(line.id)}`}
                            >Crear ajuste por faltante</a
                          >
                        </div>
                      {/each}
                    </div>
                  {/if}
                  <Button
                    class="mt-3"
                    variant="secondary"
                    disabled={actionSaving || (!canMoveInventory && !canReceiveInventory)}
                    onclick={() => {
                      showResolutionForm = !showResolutionForm;
                      showIncidentForm = false;
                    }}>Resolver incidencia autorizada</Button
                  >
                </div>
                {#if showResolutionForm}
                  <form
                    class="grid gap-3 rounded-xl border border-border p-4 lg:grid-cols-2"
                    onsubmit={(event) => {
                      event.preventDefault();
                      void resolveTransferIncident();
                    }}
                  >
                    <label class="space-y-1 text-sm font-medium text-foreground"
                      >Acción permitida<select class="field-control" bind:value={incidentResolution}
                        ><option value="resume_transit">Reanudar tránsito</option
                        >{#if currentTransitQuantity === 0n}<option value="close_received"
                            >Cerrar como recibido</option
                          >{/if}</select
                      ></label
                    >
                    <label class="space-y-1 text-sm font-medium text-foreground"
                      >Notas de resolución<textarea
                        class="field-control min-h-14"
                        minlength="5"
                        maxlength="4000"
                        required
                        bind:value={incidentResolutionNotes}
                      ></textarea></label
                    >
                    <div class="flex justify-end gap-2 lg:col-span-2">
                      <Button variant="secondary" onclick={() => (showResolutionForm = false)}
                        >Cerrar</Button
                      ><Button
                        type="submit"
                        disabled={actionSaving || incidentResolutionNotes.trim().length < 5}
                        >Guardar resolución</Button
                      >
                    </div>
                  </form>
                {/if}
              {:else}
                <div class="notice notice-warning" role="status">
                  El documento tiene una incidencia, pero no hay incidencia abierta en el detalle.
                  Actualiza el documento para consultar el estado vigente.
                </div>
              {/if}
            {:else if selectedTransfer.status === 'received'}
              <div class="notice notice-success" role="status">
                Traslado recibido. La mercancía ingresó en cuarentena en la bodega de destino.
                Consulta allí su estado actual y las revisiones pendientes.
              </div>
            {:else if selectedTransfer.status === 'closed_with_adjustment'}
              <div class="notice notice-warning" role="status">
                Traslado cerrado con ajuste. Las cantidades recibidas, devueltas y justificadas como
                faltante permanecen separadas en el historial; ninguna pérdida se contó como
                recibida.
              </div>
            {:else if selectedTransfer.status === 'cancelled'}
              <div class="notice notice-info" role="status">
                Preparación cancelada. No produjo movimientos y queda consultable en el historial.
              </div>
            {/if}

            {#if hasReceivedStock}
              <section
                class="rounded-xl border border-border bg-surface p-4"
                aria-labelledby="transfer-next-step"
              >
                <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div class="min-w-0">
                    <h3 id="transfer-next-step" class="font-semibold text-foreground">
                      Siguiente paso: inventario de destino
                    </h3>
                    <p class="mt-1 text-sm text-foreground-muted">
                      Consulta los productos ya recibidos en {selectedTransfer.destination_warehouse_name}
                      y completa las revisiones pendientes de ubicación, medidas y etiquetas.
                    </p>
                  </div>
                  {#if canReadDestinationInventory && destinationInventoryHref}
                    <a
                      href={destinationInventoryHref}
                      class="inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-lg bg-foreground px-4 py-2 text-sm font-medium text-surface hover:bg-foreground-muted focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                    >
                      Continuar en inventario de destino <span aria-hidden="true">→</span>
                    </a>
                  {/if}
                </div>
                {#if !canReadDestinationInventory}
                  <p class="mt-3 text-sm text-foreground-muted">
                    Un usuario con acceso a almacenes e inventario debe continuar con esta revisión.
                  </p>
                {:else if !destinationInventoryHref}
                  <p class="mt-3 text-sm text-foreground-muted">
                    No se pudo identificar la bodega de destino. Actualiza la información del
                    traslado.
                  </p>
                {/if}
              </section>
            {/if}

            {#if currentIncidents.length > 0}<section class="space-y-2 border-t border-border pt-4">
                <h3 class="font-semibold text-foreground">Historial de incidencias</h3>
                {#each currentIncidents as incident (incident.id)}<article
                    class="rounded-lg bg-surface-muted p-3 text-sm"
                  >
                    <p class="font-medium text-foreground">
                      {incident.status === 'open' ? 'Abierta' : 'Resuelta'} · {formatDate(
                        incident.opened_at
                      )}
                    </p>
                    <p class="mt-1 text-foreground-muted">{incident.reason}</p>
                    {#if incident.resolution_notes}<p class="mt-1 text-xs text-foreground-muted">
                        Resolución: {incident.resolution_notes}
                      </p>{/if}
                  </article>{/each}
              </section>{/if}
            {#if detailError}<p class="notice notice-danger" role="alert">{detailError}</p>{/if}
            {#if actionNotice}<p class="notice notice-success" role="status">{actionNotice}</p>{/if}
            {#if actionError}<p class="notice notice-danger" role="alert">{actionError}</p>{/if}
          {/if}
        </section>
      {/if}
    </div>
  {:else}
    <TransferVehicleCatalog
      {vehicles}
      state={vehicleState}
      error={vehicleError}
      canManage={canMoveInventory}
      saving={vehicleSaving}
      code={vehicleCode}
      name={vehicleName}
      onCodeChange={(value) => (vehicleCode = value)}
      onNameChange={(value) => (vehicleName = value)}
      onSave={(event) => void saveVehicle(event)}
      onToggleStatus={(vehicle) => void changeVehicleStatus(vehicle)}
    />
  {/if}
</main>

{#if confirmationText}
  <dialog
    bind:this={confirmationDialog}
    class="fixed inset-0 m-0 h-full max-h-full w-full max-w-none overflow-y-auto border-0 bg-transparent p-4 text-foreground backdrop:bg-black/60"
    aria-labelledby="transfer-confirm-heading"
    oncancel={(event) => {
      event.preventDefault();
      dismissConfirmation();
    }}
  >
    <div class="grid min-h-full place-items-center">
      <div
        class="w-full max-w-xl space-y-4 rounded-2xl border border-border bg-surface p-5 text-foreground shadow-2xl"
      >
        <h2 id="transfer-confirm-heading" class="text-lg font-semibold text-foreground">
          {confirmationText.split(':')[0]}
        </h2>
        <p class="text-sm text-foreground-muted">
          {confirmationText.substring(confirmationText.indexOf(':') + 1).trim()}
        </p>
        <div class="flex justify-end gap-2">
          <Button variant="secondary" onclick={dismissConfirmation}>Volver</Button><Button
            disabled={actionSaving}
            onclick={() => void runConfirmedAction()}
            >{actionSaving ? 'Procesando…' : 'Confirmar acción'}</Button
          >
        </div>
      </div>
    </div>
  </dialog>
{/if}

<style>
  .field-control {
    @apply w-full rounded-xl border border-border bg-surface px-3 py-2.5 text-sm text-foreground placeholder:text-foreground-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary;
  }
  .tab-button {
    @apply min-h-11 shrink-0 rounded-xl px-4 py-2 text-sm font-medium text-foreground-muted hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary;
  }
  .active-tab {
    @apply bg-primary/10 text-foreground;
  }
  .transfer-tabs {
    scrollbar-width: thin;
  }
  .notice {
    @apply rounded-xl border px-4 py-3 text-sm;
  }
  .notice-info {
    @apply border-primary/25 bg-primary/5 text-foreground;
  }
  .notice-warning {
    @apply border-warning/30 bg-warning/10 text-foreground;
  }
  .notice-danger {
    @apply border-danger/30 bg-danger/10 text-foreground;
  }
  .notice-success {
    @apply border-success/30 bg-success/10 text-success;
  }
  dialog::backdrop {
    background: rgb(0 0 0 / 60%);
  }
</style>
