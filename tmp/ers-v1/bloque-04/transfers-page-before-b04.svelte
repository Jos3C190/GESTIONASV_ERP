<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { catalogApi } from '$lib/api/catalog';
  import Button from '$lib/components/ui/Button.svelte';
  import { inventoryApi } from '$lib/features/inventory/services';
  import { getAsyncCollectionState } from '$lib/features/inventory/async-collection-state';
  import TransferSupplyDashboard from '$lib/features/inventory/components/TransferSupplyDashboard.svelte';
  import type { InventoryMovementHistory, TransferHandlingUnit } from '$lib/features/inventory/types';
  import type {
    TransferDemandEntry,
    TransferReceiptProduct,
    TransferReceiptSummary,
    TransferSupplyProduct
  } from '$lib/features/inventory/transfer-supply';
  import { listLocations } from '$lib/features/locations/services';
  import type { LocationOut } from '$lib/features/locations/types';
  import { purchaseRequestsApi } from '$lib/api/purchase-requests';
  import type { PurchaseRequest } from '$lib/types/purchase-request';
  import type { Unit } from '$lib/types/catalog';
  import { getWarehouses } from '$lib/services/warehouses';
  import type { Warehouse } from '$lib/features/warehouses/types';
  import { confirmation } from '$lib/stores/confirmation.svelte';
  import { branch } from '$lib/stores/branch.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';

  type DispatchMode = 'request' | 'replenishment';
  type TransferAttempt = { fingerprint: string; idempotencyKey: string };

  const ALL_WAREHOUSES = '__all__';

  const eligibleRequestStatuses = new Set([
    'approved',
    'partially_quoted',
    'quoted',
    'partially_ordered',
    'completed'
  ]);

  let warehouses = $state<Warehouse[]>([]);
  let centralWarehouses = $state<Warehouse[]>([]);
  let branchWarehouses = $state<Warehouse[]>([]);
  let sourceWarehouseId = $state('');
  let destinationWarehouseId = $state('');
  let receiverWarehouseId = $state('');
  let destinationLocationId = $state('');
  let destinationLocations = $state<LocationOut[]>([]);
  let availableUnits = $state<TransferHandlingUnit[]>([]);
  let inTransitUnits = $state<TransferHandlingUnit[]>([]);
  let requests = $state<PurchaseRequest[]>([]);
  let catalogUnits = $state<Unit[]>([]);
  let warehouseMovements = $state<InventoryMovementHistory[]>([]);
  let transferMovements = $state<InventoryMovementHistory[]>([]);
  let selectedRequestId = $state('');
  let dispatchProductId = $state<number | null>(null);
  let dispatchProductUnitId = $state<number | null>(null);
  let showDispatchForm = $state(false);
  let requestInventoryItemIds = $state<string[]>([]);
  let requestBaseUnitIds = $state<Record<number, number>>({});
  let plannedQuantities = $state<Record<string, number>>({});
  let selectedReceiptUnitIds = $state<string[]>([]);
  let receiptQuantities = $state<Record<string, number>>({});
  let mode = $state<DispatchMode>('replenishment');
  let reason = $state('');
  let loading = $state(true);
  let loadingStock = $state(false);
  let loadingDestination = $state(false);
  let loadingTransit = $state(false);
  let requestLoading = $state(false);
  let receiptLoading = $state(false);
  let receiptError = $state<string | null>(null);
  let transitError = $state<string | null>(null);
  let stockError = $state<string | null>(null);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let requestWarning = $state<string | null>(null);
  let success = $state<string | null>(null);
  let dispatchAttempt = $state<TransferAttempt | null>(null);
  let receiptAttempts = $state<Record<string, TransferAttempt>>({});
  let stockSequence = 0;
  let destinationSequence = 0;
  let transitSequence = 0;
  let requestSequence = 0;
  let receiptSequence = 0;

  let canDispatchFromMatrix = $derived(
    branch.accessAllBranches && permissions.hasPermission('inventory:move')
  );
  let canReceiveTransfers = $derived(permissions.hasPermission('inventory:receive'));
  let receivingWarehouses = $derived(
    warehouses
      .filter((warehouse) => warehouse.storageEligible)
      .sort((left, right) =>
        `${left.branchName ?? ''} ${left.name}`.localeCompare(
          `${right.branchName ?? ''} ${right.name}`,
          'es-SV'
        )
      )
  );

  let selectedRequest = $derived(requests.find((item) => item.id === selectedRequestId) ?? null);
  let selectedSource = $derived(
    centralWarehouses.find((warehouse) => warehouse.id === sourceWarehouseId) ?? null
  );
  let selectedDestination = $derived(
    warehouses.find((warehouse) => warehouse.id === destinationWarehouseId) ?? null
  );
  let requestFilteredUnits = $derived.by(() => {
    if (mode !== 'request') {
      return availableUnits.filter((unit) =>
        (dispatchProductId == null || unit.product_id === dispatchProductId) &&
        (dispatchProductUnitId == null || unit.base_unit_id === dispatchProductUnitId)
      );
    }
    if (!selectedRequest) return [];
    const allowedItems = new Set(requestInventoryItemIds);
    const requestPairs = new Set(
      selectedRequest.details
        .filter((detail) => requestBaseUnitIds[detail.product_id] === detail.unit_id)
        .map((detail) => `${detail.product_id}:${detail.unit_id}`)
    );
    return availableUnits.filter(
      (unit) =>
        allowedItems.has(unit.inventory_item_id) &&
        unit.product_id != null &&
        (dispatchProductId == null || unit.product_id === dispatchProductId) &&
        (dispatchProductUnitId == null || unit.base_unit_id === dispatchProductUnitId) &&
        requestPairs.has(`${unit.product_id}:${unit.base_unit_id}`)
    );
  });
  let selectedUnits = $derived(
    requestFilteredUnits.filter((unit) => (plannedQuantities[unit.id] ?? 0) > 0)
  );
  let selectedQuantity = $derived(
    selectedUnits.reduce((total, unit) => total + (plannedQuantities[unit.id] ?? 0), 0)
  );
  let partialAllocationCount = $derived(
    selectedUnits.filter((unit) => (plannedQuantities[unit.id] ?? 0) < unit.quantity_base - 0.000001).length
  );
  let requestUnitMismatches = $derived.by(() => {
    if (!selectedRequest) return [];
    return selectedRequest.details.filter(
      (detail) =>
        (dispatchProductId == null || detail.product_id === dispatchProductId) &&
        (dispatchProductUnitId == null || detail.unit_id === dispatchProductUnitId) &&
        requestBaseUnitIds[detail.product_id] != null &&
        requestBaseUnitIds[detail.product_id] !== detail.unit_id
    );
  });
  let receiverUnits = $derived(
    receiverWarehouseId === ALL_WAREHOUSES
      ? inTransitUnits.filter((unit) => receivingWarehouses.some((warehouse) => warehouse.id === unit.warehouse_id))
      : inTransitUnits.filter((unit) => unit.warehouse_id === receiverWarehouseId)
  );
  let pendingGroups = $derived.by(() => {
    const groups = new Map<string, {
      key: string;
      reference: string;
      warehouseId: string;
      warehouseLabel: string;
      units: TransferHandlingUnit[];
    }>();
    for (const unit of receiverUnits) {
      const reference = unit.source_reference || 'Traslado sin referencia';
      const key = `${unit.warehouse_id}:${reference}`;
      const group = groups.get(key) ?? {
        key,
        reference,
        warehouseId: unit.warehouse_id,
        warehouseLabel: [unit.warehouse_code, unit.warehouse_name, unit.branch_name]
          .filter((value) => Boolean(value))
          .join(' · ') || 'Bodega destino',
        units: []
      };
      group.units.push(unit);
      groups.set(key, group);
    }
    return [...groups.values()];
  });
  let stockLoadState = $derived(
    getAsyncCollectionState({ loading: loadingStock, error: stockError, items: availableUnits })
  );
  let pendingReceiptLoadState = $derived(
    getAsyncCollectionState({ loading: loadingTransit, error: transitError, items: receiverUnits })
  );
  let supplyProducts = $derived.by((): TransferSupplyProduct[] => {
    type ProductAccumulator = Omit<
      TransferSupplyProduct,
      'requestedQuantity' | 'pendingQuantity' | 'reserveQuantity' | 'shortageQuantity' | 'canEstimateReserve'
    >;
    const grouped = new Map<string, ProductAccumulator>();
    const unitLabels = new Map<number, string>(
      catalogUnits.map((unit): [number, string] => [
        unit.id_unit,
        unit.alias || unit.symbol || unit.name
      ])
    );
    const productUnitIds = new Map<number, Set<number>>();

    const addProductUnit = (productId: number, unitId: number) => {
      const unitIds = productUnitIds.get(productId) ?? new Set<number>();
      unitIds.add(unitId);
      productUnitIds.set(productId, unitIds);
    };

    for (const unit of availableUnits) {
      const productId = unit.product_id;
      const unitId = unit.base_unit_id;
      const key = productId == null
        ? `item:${unit.inventory_item_id}`
        : `product:${productId}:unit:${unitId}`;
      if (productId != null) addProductUnit(productId, unitId);
      const existing = grouped.get(key) ?? {
        key,
        productId,
        productName: unit.product_name ?? 'Producto sin nombre',
        sku: unit.product_sku,
        unitId,
        unitLabel: unit.base_unit_symbol ?? unit.base_unit_name ?? `Unidad ${unitId}`,
        availableQuantity: 0,
        handlingUnitCount: 0,
        demands: []
      };
      existing.availableQuantity += Number(unit.quantity_base) || 0;
      existing.handlingUnitCount += 1;
      grouped.set(key, existing);
    }

    for (const request of requests) {
      for (const detail of request.details) {
        const productId = Number(detail.product_id);
        const unitId = Number(detail.unit_id);
        if (!Number.isFinite(productId) || !Number.isFinite(unitId)) continue;
        addProductUnit(productId, unitId);
        const key = `product:${productId}:unit:${unitId}`;
        const existing = grouped.get(key) ?? {
          key,
          productId,
          productName: detail.description?.trim() || `Producto ${productId}`,
          sku: null,
          unitId,
          unitLabel: unitLabels.get(unitId) ?? `Unidad ${unitId}`,
          availableQuantity: 0,
          handlingUnitCount: 0,
          demands: []
        };
        const demand: TransferDemandEntry = {
          id: `${request.id}:${detail.id}`,
          requestId: request.id,
          requestCode: request.code,
          warehouseId: request.warehouse_id,
          branchName: request.branch_name ?? 'Sucursal sin nombre',
          requestDate: request.request_date,
          requiredDate: request.required_date,
          quantity: Number(detail.quantity) || 0,
          dispatchedQuantity: dispatchedForRequestProduct(
            request.code,
            productId,
            unitId
          ),
          remainingQuantity: 0,
          statusLabel: requestStatusLabel(request.status)
        };
        demand.remainingQuantity = Math.max(
          demand.quantity - demand.dispatchedQuantity,
          0
        );
        existing.demands.push(demand);
        grouped.set(key, existing);
      }
    }

    return [...grouped.values()]
      .map((product) => {
        const requestedQuantity = product.demands.reduce((total, demand) => total + demand.quantity, 0);
        const pendingQuantity = product.demands.reduce(
          (total, demand) => total + demand.remainingQuantity,
          0
        );
        const sameUnit = product.productId == null || (productUnitIds.get(product.productId)?.size ?? 0) <= 1;
        const canEstimateReserve = sameUnit;
        return {
          key: product.key,
          productId: product.productId,
          productName: product.productName,
          sku: product.sku,
          unitId: product.unitId,
          unitLabel: product.unitLabel,
          availableQuantity: product.availableQuantity,
          handlingUnitCount: product.handlingUnitCount,
          requestedQuantity,
          pendingQuantity,
          reserveQuantity: canEstimateReserve ? Math.max(product.availableQuantity - pendingQuantity, 0) : null,
          shortageQuantity: canEstimateReserve ? Math.max(pendingQuantity - product.availableQuantity, 0) : null,
          canEstimateReserve,
          demands: [...product.demands].sort((left, right) => right.requestDate.localeCompare(left.requestDate))
        };
      })
      .sort((left, right) =>
        right.availableQuantity - left.availableQuantity || left.productName.localeCompare(right.productName, 'es-SV')
      );
  });
  let recentReceipts = $derived.by((): TransferReceiptSummary[] => {
    const grouped = new Map<string, TransferReceiptSummary & { productMap: Map<string, TransferReceiptProduct> }>();
    for (const movement of warehouseMovements) {
      if (movement.movement_type !== 'receipt' || movement.to_warehouse_id !== sourceWarehouseId) continue;
      const receipt = grouped.get(movement.movement_id) ?? {
        id: movement.movement_id,
        reference: movement.source_reference ?? 'Recepción de compra',
        purchaseCode: movement.purchase_code ?? movement.purchase_order_code,
        receivedAt: movement.posted_at,
        products: [],
        productMap: new Map<string, TransferReceiptProduct>()
      };
      const productKey = `${movement.inventory_item_id}:${movement.base_unit_id}`;
      const product = receipt.productMap.get(productKey) ?? {
        key: productKey,
        productName: movement.product_name ?? 'Producto sin nombre',
        sku: movement.product_sku,
        quantity: 0,
        unitLabel: movement.base_unit_symbol ?? movement.base_unit_name ?? `Unidad ${movement.base_unit_id}`
      };
      product.quantity += Number(movement.quantity_base) || 0;
      receipt.productMap.set(productKey, product);
      receipt.products = [...receipt.productMap.values()];
      grouped.set(movement.movement_id, receipt);
    }
    return [...grouped.values()]
      .map((receipt): TransferReceiptSummary => ({
        id: receipt.id,
        reference: receipt.reference,
        purchaseCode: receipt.purchaseCode,
        receivedAt: receipt.receivedAt,
        products: [...receipt.productMap.values()]
      }))
      .sort((left, right) => right.receivedAt.localeCompare(left.receivedAt))
      .slice(0, 5);
  });

  function formatQuantity(value: number): string {
    return value.toLocaleString('es-SV', { maximumFractionDigits: 3 });
  }

  function formatCalendarDate(value: string | null): string {
    if (!value) return 'fecha no indicada';
    const dateOnly = value.slice(0, 10);
    const parsed = new Date(`${dateOnly}T12:00:00Z`);
    if (Number.isNaN(parsed.getTime())) return 'fecha no indicada';
    return new Intl.DateTimeFormat('es-SV', {
      dateStyle: 'medium',
      timeZone: 'UTC'
    }).format(parsed);
  }

  function requestUnitLabel(unitId: number): string {
    const unit = catalogUnits.find((item) => item.id_unit === unitId);
    return unit?.alias || unit?.symbol || unit?.name || `unidad ${unitId}`;
  }

  function warehouseLabel(warehouse: Warehouse): string {
    return [warehouse.code, warehouse.name, warehouse.branchName]
      .filter((value) => Boolean(value))
      .join(' · ');
  }

  function requestStatusLabel(status: PurchaseRequest['status']): string {
    const labels: Record<PurchaseRequest['status'], string> = {
      draft: 'Borrador',
      submitted: 'Enviada',
      approved: 'Aprobada',
      rejected: 'Rechazada',
      partially_quoted: 'Cotizada parcialmente',
      quoted: 'Cotizada',
      partially_ordered: 'Ordenada parcialmente',
      completed: 'Completada',
      cancelled: 'Cancelada'
    };
    return labels[status];
  }

  function quantitySummary(units: TransferHandlingUnit[]): string {
    const totals = new Map<number, { label: string; quantity: number }>();
    for (const unit of units) {
      const current = totals.get(unit.base_unit_id) ?? {
        label: unit.base_unit_symbol ?? unit.base_unit_name ?? 'unidad base',
        quantity: 0
      };
      current.quantity += unit.quantity_base;
      totals.set(unit.base_unit_id, current);
    }
    return [...totals.values()]
      .map(({ label, quantity }) => `${formatQuantity(quantity)} ${label}`)
      .join(' · ');
  }

  function allocationSummary(units: TransferHandlingUnit[]): string {
    const totals = new Map<number, { label: string; quantity: number }>();
    for (const unit of units) {
      const current = totals.get(unit.base_unit_id) ?? {
        label: unit.base_unit_symbol ?? unit.base_unit_name ?? 'unidad base',
        quantity: 0
      };
      current.quantity += plannedQuantities[unit.id] ?? 0;
      totals.set(unit.base_unit_id, current);
    }
    return [...totals.values()]
      .filter(({ quantity }) => quantity > 0)
      .map(({ label, quantity }) => `${formatQuantity(quantity)} ${label}`)
      .join(' · ');
  }

  function dispatchedForRequestProduct(
    requestCode: string,
    productId: number,
    unitId: number
  ): number {
    const marker = `Solicitud ${requestCode}`;
    return transferMovements
      .filter(
        (movement) =>
          movement.from_warehouse_id === sourceWarehouseId &&
          movement.to_stock_status === 'in_transit' &&
          movement.source_reference?.includes(marker) &&
          movement.product_id === productId &&
          movement.base_unit_id === unitId
      )
      .reduce((sum, movement) => sum + (Number(movement.quantity_base) || 0), 0);
  }

  function requestedForProduct(request: PurchaseRequest, productId: number, unitId: number): number {
    return request.details
      .filter((detail) => detail.product_id === productId && detail.unit_id === unitId)
      .reduce((sum, detail) => sum + (Number(detail.quantity) || 0), 0);
  }

  function remainingForProduct(request: PurchaseRequest, productId: number, unitId: number): number {
    return Math.max(
      requestedForProduct(request, productId, unitId) -
        dispatchedForRequestProduct(request.code, productId, unitId),
      0
    );
  }

  function setPlannedQuantity(unitId: string, rawValue: string) {
    const unit = availableUnits.find((item) => item.id === unitId);
    if (!unit) return;
    const parsed = Number(rawValue);
    const quantity = Number.isFinite(parsed) ? Math.max(0, Math.min(parsed, unit.quantity_base)) : 0;
    plannedQuantities = { ...plannedQuantities, [unitId]: quantity };
    dispatchAttempt = null;
    if (reason === 'Surtido parcial por disponibilidad') reason = '';
  }

  function requestPlanMatchesRemainingDemand(): boolean {
    if (!selectedRequest) return false;
    const keys = new Set(
      selectedRequest.details
        .filter((detail) =>
          (dispatchProductId == null || detail.product_id === dispatchProductId) &&
          (dispatchProductUnitId == null || detail.unit_id === dispatchProductUnitId)
        )
        .map((detail) => `${detail.product_id}:${detail.unit_id}`)
    );
    for (const key of keys) {
      const parts = key.split(':').map(Number);
      if (parts[0] == null || parts[1] == null) continue;
      const [productId, unitId] = parts;
      const planned = selectedUnits
        .filter((unit) => unit.product_id === productId && unit.base_unit_id === unitId)
        .reduce((sum, unit) => sum + (plannedQuantities[unit.id] ?? 0), 0);
      const requestedRemaining = remainingForProduct(selectedRequest, productId, unitId);
      if (Math.abs(planned - requestedRemaining) > 0.000001) return false;
    }
    return true;
  }

  let dispatchRequiresReason = $derived(
    mode === 'replenishment' || (selectedRequest != null && !requestPlanMatchesRemainingDemand())
  );

  async function loadWarehouses() {
    const all: Warehouse[] = [];
    const scopedBranchId = branch.accessAllBranches
      ? undefined
      : branch.id ?? branch.branches[0]?.id;
    if (!branch.accessAllBranches && !scopedBranchId) {
      throw new Error('Tu usuario no tiene una sucursal autorizada para recibir traslados.');
    }
    let page = 1;
    let pages = 1;
    do {
      const result = await getWarehouses({
        branchId: scopedBranchId,
        page,
        size: 100,
        status: 'active'
      });
      all.push(...result.items);
      pages = Math.max(1, result.meta.pages);
      page += 1;
    } while (page <= pages);

    warehouses = all.filter((warehouse) => warehouse.status === 'active');
    centralWarehouses = canDispatchFromMatrix ? warehouses
      .filter((warehouse) => warehouse.isCentral && !warehouse.branchId && warehouse.storageEligible)
      .sort((left, right) => left.name.localeCompare(right.name, 'es-SV')) : [];
    branchWarehouses = warehouses
      .filter(
        (warehouse) =>
          !warehouse.isCentral &&
          warehouse.branchId &&
          warehouse.storageEligible &&
          (branch.accessAllBranches || warehouse.branchId === scopedBranchId)
      )
      .sort((left, right) =>
        `${left.branchName} ${left.name}`.localeCompare(
          `${right.branchName} ${right.name}`,
          'es-SV'
        )
      );
    sourceWarehouseId = centralWarehouses[0]?.id ?? '';
    destinationWarehouseId = branchWarehouses[0]?.id ?? '';
    receiverWarehouseId = branch.accessAllBranches
      ? ALL_WAREHOUSES
      : receivingWarehouses[0]?.id ?? '';
  }

  async function loadRequests() {
    requestLoading = true;
    requestWarning = null;
    try {
      const all: PurchaseRequest[] = [];
      let page = 1;
      let pages = 1;
      do {
        const result = await purchaseRequestsApi.list({ page, size: 100 });
        all.push(...result.items);
        pages = Math.max(1, result.meta.pages);
        page += 1;
      } while (page <= pages);
      requests = all
        .filter((item) => eligibleRequestStatuses.has(item.status))
        .sort((left, right) => right.request_date.localeCompare(left.request_date));
    } catch (cause) {
      requests = [];
      requestWarning =
        cause instanceof Error
          ? `No se pudieron consultar las solicitudes: ${cause.message}`
          : 'No se pudieron consultar las solicitudes aprobadas.';
    } finally {
      requestLoading = false;
    }
  }

  async function loadAvailableUnits(warehouseId: string) {
    const sequence = ++stockSequence;
    loadingStock = true;
    error = null;
    stockError = null;
    plannedQuantities = {};
    try {
      const units = await inventoryApi.listTransferUnits(warehouseId, 'available');
      if (sequence === stockSequence) availableUnits = units;
    } catch (cause) {
      if (sequence === stockSequence) {
        availableUnits = [];
        stockError = cause instanceof Error ? cause.message : 'No se pudo cargar el inventario central.';
      }
    } finally {
      if (sequence === stockSequence) loadingStock = false;
    }
  }

  async function loadRecentMovements(warehouseId: string) {
    const sequence = ++receiptSequence;
    if (!warehouseId) {
      warehouseMovements = [];
      transferMovements = [];
      receiptError = null;
      receiptLoading = false;
      return;
    }
    receiptLoading = true;
    receiptError = null;
    warehouseMovements = [];
    try {
      const [receipts, transfers] = await Promise.all([
        inventoryApi.listWarehouseMovements(warehouseId, 100, 'receipt'),
        inventoryApi.listWarehouseMovements(warehouseId, 1000, 'transfer')
      ]);
      if (sequence === receiptSequence) {
        warehouseMovements = receipts;
        transferMovements = transfers;
      }
    } catch (cause) {
      if (sequence === receiptSequence) {
        warehouseMovements = [];
        transferMovements = [];
        receiptError = cause instanceof Error
          ? `No se pudieron cargar las recepciones recientes: ${cause.message}`
          : 'No se pudieron cargar las recepciones recientes de la matriz.';
      }
    } finally {
      if (sequence === receiptSequence) receiptLoading = false;
    }
  }

  async function loadDestinationLocations(warehouseId: string) {
    const sequence = ++destinationSequence;
    loadingDestination = true;
    destinationLocationId = '';
    destinationLocations = [];
    try {
      const eligible: LocationOut[] = [];
      let page = 1;
      let pages = 1;
      do {
        const result = await listLocations(warehouseId, { page, size: 100 });
        eligible.push(
          ...result.items.filter(
            (location) =>
              location.warehouse_id === warehouseId &&
              location.is_active &&
              location.storage_eligible &&
              location.lifecycle_status === 'active'
          )
        );
        pages = Math.max(1, result.meta.pages);
        page += 1;
      } while (page <= pages);
      if (sequence !== destinationSequence) return;
      destinationLocations = eligible.sort((left, right) =>
        left.code.localeCompare(right.code, 'es-SV')
      );
      destinationLocationId = destinationLocations[0]?.id ?? '';
    } catch (cause) {
      if (sequence === destinationSequence) {
        error = cause instanceof Error ? cause.message : 'No se pudieron cargar las ubicaciones destino.';
      }
    } finally {
      if (sequence === destinationSequence) loadingDestination = false;
    }
  }

  async function loadTransitForWarehouse(warehouseId: string) {
    const sequence = ++transitSequence;
    loadingTransit = true;
    transitError = null;
    inTransitUnits = inTransitUnits.filter((unit) => unit.warehouse_id !== warehouseId);
    try {
      const units = await inventoryApi.listTransferUnits(warehouseId, 'in_transit');
      if (sequence === transitSequence) {
        inTransitUnits = [
          ...inTransitUnits.filter((unit) => unit.warehouse_id !== warehouseId),
          ...units
        ];
      }
    } catch (cause) {
      if (sequence === transitSequence) {
        transitError = cause instanceof Error
          ? `No se pudieron cargar las recepciones pendientes: ${cause.message}`
          : 'No se pudieron cargar las recepciones pendientes de esta bodega.';
      }
    } finally {
      if (sequence === transitSequence) loadingTransit = false;
    }
  }

  async function loadTransitForAllWarehouses() {
    const sequence = ++transitSequence;
    loadingTransit = true;
    transitError = null;
    try {
      const results = await Promise.allSettled(
        receivingWarehouses.map((warehouse) =>
          inventoryApi.listTransferUnits(warehouse.id, 'in_transit')
        )
      );
      if (sequence !== transitSequence) return;

      inTransitUnits = results.flatMap((result) =>
        result.status === 'fulfilled' ? result.value : []
      );
      const failedCount = results.filter((result) => result.status === 'rejected').length;
      transitError = failedCount > 0
        ? `No se pudieron consultar las recepciones pendientes de ${failedCount} bodega(s). Las demás sí se muestran.`
        : null;
    } finally {
      if (sequence === transitSequence) loadingTransit = false;
    }
  }

  async function loadTransitForSelection(warehouseId: string) {
    if (warehouseId === ALL_WAREHOUSES) {
      await loadTransitForAllWarehouses();
      return;
    }
    if (!warehouseId) {
      transitSequence += 1;
      inTransitUnits = [];
      transitError = null;
      loadingTransit = false;
      return;
    }
    await loadTransitForWarehouse(warehouseId);
  }

  async function chooseReceiverWarehouse(warehouseId: string) {
    receiverWarehouseId = warehouseId;
    selectedReceiptUnitIds = [];
    receiptQuantities = {};
    await loadTransitForSelection(warehouseId);
  }

  async function chooseSource(warehouseId: string) {
    sourceWarehouseId = warehouseId;
    availableUnits = [];
    warehouseMovements = [];
    transferMovements = [];
    if (warehouseId) {
      await Promise.all([loadAvailableUnits(warehouseId), loadRecentMovements(warehouseId)]);
    } else {
      availableUnits = [];
      await loadRecentMovements('');
    }
  }

  async function chooseDestination(warehouseId: string) {
    destinationWarehouseId = warehouseId;
    selectedRequestId = '';
    requestInventoryItemIds = [];
    requestBaseUnitIds = {};
    plannedQuantities = {};
    if (!warehouseId) {
      destinationLocations = [];
      destinationLocationId = '';
      return;
    }
    await Promise.all([
      loadDestinationLocations(warehouseId),
      loadTransitForWarehouse(warehouseId)
    ]);
  }

  async function chooseRequest(requestId: string, focusProductId: number | null = null, focusUnitId: number | null = null) {
    const sequence = ++requestSequence;
    selectedRequestId = requestId;
    dispatchProductId = focusProductId;
    dispatchProductUnitId = focusUnitId;
    plannedQuantities = {};
    reason = '';
    requestInventoryItemIds = [];
    requestBaseUnitIds = {};
    const request = requests.find((item) => item.id === requestId);
    if (!request) return;
    destinationWarehouseId = request.warehouse_id;
    await Promise.all([
      loadDestinationLocations(request.warehouse_id),
      loadTransitForWarehouse(request.warehouse_id)
    ]);
    const productIds = [...new Set(request.details.map((detail) => detail.product_id))];
    const identities = await Promise.all(
      productIds.map((productId) =>
        inventoryApi.getItemByTarget({ productId }).catch(() => null)
      )
    );
    if (sequence !== requestSequence) return;
    const itemByProduct: Record<number, NonNullable<(typeof identities)[number]>> = {};
    for (let index = 0; index < identities.length; index += 1) {
      const item = identities[index];
      const productId = productIds[index];
      if (item && productId != null) itemByProduct[productId] = item;
    }
    requestInventoryItemIds = Object.values(itemByProduct).map((item) => item.id);
    requestBaseUnitIds = Object.fromEntries(
      Object.entries(itemByProduct).map(([productId, item]) => [Number(productId), item.base_unit_id])
    );

    const nextPlan: Record<string, number> = {};
    const plannedByProduct = new Map<string, number>();
    for (const detail of request.details) {
      if (focusProductId != null && detail.product_id !== focusProductId) continue;
      if (focusUnitId != null && detail.unit_id !== focusUnitId) continue;
      const baseUnitId = requestBaseUnitIds[detail.product_id];
      if (baseUnitId == null || baseUnitId !== detail.unit_id) continue;
      const key = `${detail.product_id}:${detail.unit_id}`;
      if (!plannedByProduct.has(key)) {
        const remainingDemand = remainingForProduct(request, detail.product_id, detail.unit_id);
        const available = availableUnits
          .filter((unit) => unit.product_id === detail.product_id && unit.base_unit_id === detail.unit_id)
          .reduce((total, unit) => total + unit.quantity_base, 0);
        plannedByProduct.set(key, Math.min(remainingDemand, available));
      }
    }
    const remainingByProduct = new Map(plannedByProduct);
    for (const unit of requestFilteredUnits) {
      const key = `${unit.product_id}:${unit.base_unit_id}`;
      const remaining = remainingByProduct.get(key) ?? 0;
      const quantity = Math.min(remaining, unit.quantity_base);
      if (quantity > 0) nextPlan[unit.id] = quantity;
      remainingByProduct.set(key, Math.max(remaining - quantity, 0));
    }
    plannedQuantities = nextPlan;
    const stockShort = [...plannedByProduct.entries()].some(([key, planned]) => {
      const parts = key.split(':').map(Number);
      if (parts[0] == null || parts[1] == null) return false;
      const [productId, unitId] = parts;
      return planned + 0.000001 < remainingForProduct(request, productId, unitId);
    });
    if (stockShort) reason = 'Surtido parcial por disponibilidad';
  }

  async function prepareRequestDispatch(requestId: string, productId: number, unitId: number) {
    if (loadingStock || stockError) return;
    showDispatchForm = true;
    mode = 'request';
    success = null;
    error = null;
    await chooseRequest(requestId, productId, unitId);
    await tick();
    scrollToDispatchPanel();
  }

  async function prepareManualDispatch() {
    if (loadingStock || stockError) return;
    showDispatchForm = true;
    mode = 'replenishment';
    selectedRequestId = '';
    dispatchProductId = null;
    dispatchProductUnitId = null;
    requestInventoryItemIds = [];
    requestBaseUnitIds = {};
    plannedQuantities = {};
    reason = '';
    success = null;
    error = null;
    const destinationId = destinationWarehouseId || branchWarehouses[0]?.id || '';
    if (destinationId) await chooseDestination(destinationId);
    await tick();
    scrollToDispatchPanel();
  }

  function scrollToDispatchPanel() {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    document.getElementById('transfer-dispatch-panel')?.scrollIntoView({
      behavior: prefersReducedMotion ? 'auto' : 'smooth',
      block: 'start'
    });
  }

  function transferReference(): string {
    const code = `TR-${new Date().toISOString().slice(0, 10).replaceAll('-', '')}-${crypto.randomUUID().slice(0, 6).toUpperCase()}`;
    const linkedRequest = selectedRequest ? ` · Solicitud ${selectedRequest.code}` : '';
    const note = reason.trim() || (selectedRequest ? 'Surtido según solicitud' : 'Abastecimiento autorizado');
    return `${code}${linkedRequest} · ${note}`.slice(0, 160);
  }

  function dispatchSelectedUnits() {
    if (
      saving ||
      loadingStock ||
      stockError ||
      !sourceWarehouseId ||
      !destinationWarehouseId ||
      !destinationLocationId ||
      !selectedUnits.length ||
      (dispatchRequiresReason && !reason.trim()) ||
      (mode === 'request' && !selectedRequest)
    ) return;

    const allocations = selectedUnits.map((unit) => ({
      unit,
      quantity_base: plannedQuantities[unit.id] ?? 0
    }));
    const allocationsByItem = new Map<string, number>();
    for (const { unit, quantity_base } of allocations) {
      const key = `${unit.inventory_item_id}:${unit.base_unit_id}`;
      allocationsByItem.set(key, (allocationsByItem.get(key) ?? 0) + quantity_base);
    }
    for (const [key, quantity] of allocationsByItem) {
      const available = availableUnits
        .filter((unit) => `${unit.inventory_item_id}:${unit.base_unit_id}` === key)
        .reduce((sum, unit) => sum + unit.quantity_base, 0);
      if (quantity > available + 0.000001) {
        error = 'La cantidad del plan supera el inventario disponible. Actualiza las existencias e intenta de nuevo.';
        return;
      }
    }

    const reference = transferReference();
    const sentSummary = allocationSummary(selectedUnits);
    const fingerprint = [
      destinationWarehouseId,
      destinationLocationId,
      reference,
      ...allocations
        .map(({ unit, quantity_base }) => `${unit.id}:${quantity_base}`)
        .sort()
    ].join('|');
    const attempt =
      dispatchAttempt?.fingerprint === fingerprint
        ? dispatchAttempt
        : { fingerprint, idempotencyKey: crypto.randomUUID() };
    dispatchAttempt = attempt;

    confirmation.request({
      kind: 'transfer',
      title: 'Despachar unidades a sucursal',
      description:
        'Solo se despachará la cantidad indicada; el remanente seguirá disponible en la matriz. Si se divide una unidad logística, se crea una hija trazable con peso y volumen estimados; al recibirla, la sucursal debe verificar sus medidas antes de liberar el inventario.',
      resourceName: `${sentSummary} · ${selectedDestination?.branchName ?? selectedDestination?.name ?? ''} · ${destinationLocationId}`,
      confirmLabel: 'Confirmar despacho',
      execute: async () => {
        saving = true;
        success = null;
        error = null;
        try {
          await inventoryApi.transferAllocations(
            allocations,
            destinationLocationId,
            reference,
            attempt.idempotencyKey
          );
          plannedQuantities = {};
          dispatchAttempt = null;
          success = `Despacho ${reference} registrado por ${sentSummary}. Los remanentes permanecen en la matriz.`;
          await Promise.all([
            loadAvailableUnits(sourceWarehouseId),
            loadTransitForWarehouse(destinationWarehouseId),
            loadRecentMovements(sourceWarehouseId)
          ]);
        } catch (cause) {
          error = cause instanceof Error ? cause.message : 'No se pudo registrar el despacho.';
        } finally {
          saving = false;
        }
      }
    });
  }

  function toggleReceiptUnit(unitId: string) {
    if (selectedReceiptUnitIds.includes(unitId)) {
      selectedReceiptUnitIds = selectedReceiptUnitIds.filter((id) => id !== unitId);
      return;
    }
    const unit = inTransitUnits.find((item) => item.id === unitId);
    if (!unit) return;
    selectedReceiptUnitIds = [...selectedReceiptUnitIds, unitId];
    receiptQuantities = {
      ...receiptQuantities,
      [unitId]: receiptQuantities[unitId] ?? unit.quantity_base
    };
  }

  function setReceiptQuantity(unitId: string, rawValue: string) {
    const unit = inTransitUnits.find((item) => item.id === unitId);
    if (!unit) return;
    const parsed = Number(rawValue);
    const quantity = Number.isFinite(parsed)
      ? Math.max(0, Math.min(parsed, unit.quantity_base))
      : 0;
    receiptQuantities = { ...receiptQuantities, [unitId]: quantity };
    receiptAttempts = {};
  }

  function receiveGroup(reference: string, units: TransferHandlingUnit[]) {
    if (!canReceiveTransfers) {
      error = 'Tu perfil necesita el permiso de recepción de inventario para confirmar la llegada.';
      return;
    }
    const selected = units.filter(
      (unit) =>
        selectedReceiptUnitIds.includes(unit.id) &&
        (receiptQuantities[unit.id] ?? unit.quantity_base) > 0
    );
    if (!selected.length || saving) return;
    const firstSelected = selected[0];
    if (!firstSelected) return;
    const allocations = selected.map((unit) => ({
      unit,
      quantity_base: receiptQuantities[unit.id] ?? unit.quantity_base
    }));
    const warehouseId = firstSelected.warehouse_id;
    const receivingWarehouse = warehouses.find((warehouse) => warehouse.id === warehouseId);
    const receivingWarehouseLabel = receivingWarehouse
      ? warehouseLabel(receivingWarehouse)
      : [firstSelected.warehouse_code, firstSelected.warehouse_name, firstSelected.branch_name]
          .filter((value) => Boolean(value))
          .join(' · ') || 'Bodega destino';
    const key = `${warehouseId}:${reference}`;
    const fingerprint = [
      warehouseId,
      ...allocations
        .map(({ unit, quantity_base }) => `${unit.id}:${quantity_base}`)
        .sort()
    ].join('|');
    const previous = receiptAttempts[key];
    const attempt = previous?.fingerprint === fingerprint
      ? previous
      : { fingerprint, idempotencyKey: crypto.randomUUID() };
    receiptAttempts = { ...receiptAttempts, [key]: attempt };
    const receiptReference = `RECIBIDO · ${reference}`.slice(0, 160);
    const receivedSummary = receiptQuantitySummary(selected);
    const remainingInTransit = allocations.reduce(
      (total, { unit, quantity_base }) => total + unit.quantity_base - quantity_base,
      0
    );

    confirmation.request({
      kind: 'transfer',
      title: 'Confirmar recepción en sucursal',
      description:
        'Se registrará únicamente la cantidad contada. Lo recibido quedará en cuarentena para verificarlo y elegir su ubicación final; el faltante seguirá en tránsito.',
      resourceName: `${receivedSummary} · ${receivingWarehouseLabel}`,
      confirmLabel: 'Confirmar recepción',
      execute: async () => {
        saving = true;
        error = null;
        success = null;
        try {
          await inventoryApi.receiveTransferAllocations(
            allocations,
            firstSelected.location_id,
            receiptReference,
            attempt.idempotencyKey
          );
          selectedReceiptUnitIds = selectedReceiptUnitIds.filter(
            (id) => !selected.some((unit) => unit.id === id)
          );
          receiptQuantities = Object.fromEntries(
            Object.entries(receiptQuantities).filter(
              ([unitId]) => !selected.some((unit) => unit.id === unitId)
            )
          );
          receiptAttempts = Object.fromEntries(
            Object.entries(receiptAttempts).filter(([attemptKey]) => attemptKey !== key)
          );
          success = remainingInTransit > 0
            ? `Recepción de ${receivedSummary} registrada en ${receivingWarehouseLabel}. El faltante (${formatQuantity(remainingInTransit)}) sigue en tránsito. Verifica y ubica lo recibido desde Inventario.`
            : `Recepción de ${receivedSummary} registrada en ${receivingWarehouseLabel}. Verifica y elige la ubicación final desde Inventario.`;
          await loadTransitForSelection(receiverWarehouseId);
        } catch (cause) {
          error = cause instanceof Error ? cause.message : 'No se pudo confirmar la recepción.';
        } finally {
          saving = false;
        }
      }
    });
  }

  function receiptQuantitySummary(units: TransferHandlingUnit[]): string {
    const totals = new Map<number, { label: string; quantity: number }>();
    for (const unit of units) {
      const current = totals.get(unit.base_unit_id) ?? {
        label: unit.base_unit_symbol ?? unit.base_unit_name ?? 'unidad base',
        quantity: 0
      };
      current.quantity += receiptQuantities[unit.id] ?? unit.quantity_base;
      totals.set(unit.base_unit_id, current);
    }
    return [...totals.values()]
      .filter(({ quantity }) => quantity > 0)
      .map(({ label, quantity }) => `${formatQuantity(quantity)} ${label}`)
      .join(' · ');
  }

  onMount(() => {
    void (async () => {
      loading = true;
      error = null;
      try {
        await loadWarehouses();
        if (canDispatchFromMatrix) {
          const unitPromise = catalogApi.listUnits(true)
            .then((items) => { catalogUnits = items; })
            .catch(() => { catalogUnits = []; });
          await Promise.all([
            loadRequests(),
            unitPromise,
            sourceWarehouseId ? loadAvailableUnits(sourceWarehouseId) : Promise.resolve(),
            sourceWarehouseId ? loadRecentMovements(sourceWarehouseId) : Promise.resolve()
          ]);
        }
        if (receiverWarehouseId) await loadTransitForSelection(receiverWarehouseId);
      } catch (cause) {
        error = cause instanceof Error ? cause.message : 'No se pudo preparar el módulo de traslados.';
      } finally {
        loading = false;
      }
    })();
  });
</script>

<svelte:head>
  <title>Traslados · GestionaSV</title>
</svelte:head>

<div class="mx-auto w-full max-w-7xl space-y-6 px-4 py-6 sm:px-6">
  <header class="space-y-2">
    <p class="text-sm font-medium text-primary">Inventario · {canDispatchFromMatrix ? 'Bodega matriz' : branch.active?.name ?? 'Sucursal asignada'}</p>
    <h1 class="text-2xl font-semibold text-foreground">{canDispatchFromMatrix ? 'Traslados a sucursales' : 'Recepciones de traslado'}</h1>
    <p class="max-w-3xl text-sm text-foreground-muted">
      {canDispatchFromMatrix
        ? 'Empieza por las existencias liberadas en la matriz. Abre un producto para ver qué sucursales lo solicitaron, cuánto queda pendiente y cuándo lo necesitan; decide cuánto enviar. También puedes hacer un envío sin solicitud.'
        : 'Revisa cada unidad que llegó a tu sucursal, registra la cantidad contada y déjala en cuarentena hasta verificarla y asignarle su ubicación final.'}
    </p>
  </header>

  {#if error}
    <div class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert">{error}</div>
  {/if}
  {#if success}
    <div class="rounded-xl border border-success/30 bg-success/10 px-4 py-3 text-sm text-success" role="status">{success}</div>
  {/if}

  {#if loading}
    <section class="rounded-2xl border border-border bg-surface p-6 text-sm text-foreground-muted" aria-live="polite">
      Cargando existencias, destinos y solicitudes…
    </section>
  {:else if canDispatchFromMatrix && centralWarehouses.length === 0}
    <section class="rounded-2xl border border-warning/30 bg-warning/10 p-5 text-sm text-foreground">
      No hay una bodega matriz activa y habilitada para almacenar inventario.
    </section>
  {:else}
    {#if canDispatchFromMatrix}
      {#if stockLoadState === 'loading'}
        <section class="rounded-2xl border border-border bg-surface px-5 py-6 text-sm text-foreground-muted" role="status" aria-live="polite">
          Consultando existencias liberadas de la matriz…
        </section>
      {:else if stockLoadState === 'error'}
        <section class="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-danger/30 bg-danger/10 px-5 py-4 text-sm text-danger" role="alert">
          <span>No se pudo confirmar el inventario disponible. {stockError}</span>
          <Button variant="secondary" size="sm" onclick={() => void loadAvailableUnits(sourceWarehouseId)}>Reintentar inventario</Button>
        </section>
      {:else}
      <TransferSupplyDashboard
        warehouseName={selectedSource ? warehouseLabel(selectedSource) : 'Bodega matriz'}
        products={supplyProducts}
        receipts={recentReceipts}
        requestError={requestWarning}
        handlingUnitCount={availableUnits.length}
        receiptLoading={receiptLoading}
        receiptError={receiptError}
        onPrepareRequest={prepareRequestDispatch}
        onPrepareManualDispatch={prepareManualDispatch}
      />
      {/if}

    {#if showDispatchForm}
    <section id="transfer-dispatch-panel" class="scroll-mt-24 space-y-5 rounded-2xl border border-primary/30 bg-surface p-5 sm:p-6">
      <div class="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 class="text-lg font-semibold text-foreground">Preparar despacho desde existencias</h2>
          <p class="mt-1 text-sm text-foreground-muted">Elige cuánto enviar de las unidades que ya están liberadas en la matriz. El resto se queda disponible aquí.</p>
        </div>
        <div class="flex items-center gap-2">
          <span class="rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">{availableUnits.length} unidad(es) logística(s) disponible(s)</span>
          <button type="button" class="rounded-lg border border-border px-3 py-2 text-sm text-foreground-muted hover:bg-surface-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary" onclick={() => { showDispatchForm = false; }}>
            Cerrar
          </button>
        </div>
      </div>

      <div class="grid gap-4 md:grid-cols-2">
        <label class="space-y-1.5 text-sm font-medium text-foreground">
          Bodega de salida
          <select class="w-full rounded-xl border border-border bg-surface px-3 py-2.5" value={sourceWarehouseId} onchange={(event) => void chooseSource(event.currentTarget.value)}>
            {#each centralWarehouses as warehouse (warehouse.id)}
              <option value={warehouse.id}>{warehouseLabel(warehouse)}</option>
            {/each}
          </select>
        </label>
        <div class="space-y-1.5 text-sm">
          <p class="font-medium text-foreground">Tipo de despacho</p>
          <p class="rounded-xl border border-border bg-surface-subtle px-3 py-2.5 text-foreground-muted">
            {mode === 'request' ? 'Atender pendiente de sucursal' : 'Abastecimiento adicional sin solicitud'}
          </p>
        </div>
      </div>

      {#if branchWarehouses.length === 0}
        <p class="rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-foreground">
          No hay bodegas de sucursal activas y habilitadas para recibir. Configura una ubicación de almacenamiento en cada bodega destino.
        </p>
      {/if}

      {#if mode === 'request'}
        <div class="space-y-2 rounded-xl border border-border-subtle bg-surface-subtle p-4">
          {#if selectedRequest}
            <div class="flex flex-wrap items-center justify-between gap-2 text-sm">
              <div>
                <p class="text-xs font-medium uppercase tracking-wide text-foreground-muted">Destino y referencia</p>
                <p class="text-foreground"><span class="font-semibold">{selectedRequest.branch_name ?? selectedDestination?.branchName ?? 'Sucursal'}</span> · {selectedRequest.code}</p>
                <p class="text-xs text-foreground-muted">{selectedRequest.warehouse_name ?? selectedDestination?.name ?? 'Bodega de solicitud'}</p>
              </div>
              <a class="text-primary hover:underline" href={`/purchase-requests/${selectedRequest.id}`}>Ver solicitud</a>
            </div>
            <p class="text-xs text-foreground-muted">
              Solicitada el {formatCalendarDate(selectedRequest.request_date)}
              · Requerida para {formatCalendarDate(selectedRequest.required_date)}
            </p>
            {#if dispatchProductId != null}
              {@const demandQuantity = selectedRequest.details
                .filter((detail) => detail.product_id === dispatchProductId && detail.unit_id === dispatchProductUnitId)
                .reduce((total, detail) => total + (Number(detail.quantity) || 0), 0)}
              {@const demandSent = requestBaseUnitIds[dispatchProductId] === dispatchProductUnitId ? dispatchedForRequestProduct(selectedRequest.code, dispatchProductId, dispatchProductUnitId ?? 0) : 0}
              {@const demandPending = Math.max(demandQuantity - demandSent, 0)}
              <p class="text-sm text-foreground"><span class="font-medium">Pendiente de este producto:</span> {formatQuantity(demandPending)} {requestUnitLabel(dispatchProductUnitId ?? 0)}</p>
            {/if}
          {:else if requestLoading}
            <p class="text-sm text-foreground-muted">Cargando la referencia elegida desde el producto…</p>
          {:else}
            <p class="text-sm text-warning">Vuelve al producto y usa “Preparar despacho” en la sucursal que corresponda.</p>
          {/if}
          <p class="text-xs text-foreground-muted">La solicitud se usa como referencia de trazabilidad. El despacho no cambia su estado de compras.</p>
        </div>
      {:else}
        <label class="block space-y-1.5 text-sm font-medium text-foreground">
          Sucursal destino
          <select class="w-full rounded-xl border border-border bg-surface px-3 py-2.5" value={destinationWarehouseId} onchange={(event) => void chooseDestination(event.currentTarget.value)}>
            <option value="">Selecciona una bodega</option>
            {#each branchWarehouses as warehouse (warehouse.id)}
              <option value={warehouse.id}>{warehouseLabel(warehouse)}</option>
            {/each}
          </select>
        </label>
      {/if}

      <div class="grid gap-4 md:grid-cols-2">
        <label class="space-y-1.5 text-sm font-medium text-foreground">
          Punto de recepción en sucursal
          <select class="w-full rounded-xl border border-border bg-surface px-3 py-2.5" bind:value={destinationLocationId} disabled={loadingDestination || destinationLocations.length === 0}>
            <option value="">{loadingDestination ? 'Cargando ubicaciones…' : 'Selecciona una ubicación activa'}</option>
            {#each destinationLocations as location (location.id)}
              <option value={location.id}>{location.code} · {location.area ?? 'Área'} · Pasillo {location.aisle} · Rack {location.rack} · Nivel {location.level} · Posición {location.position}</option>
            {/each}
          </select>
          {#if destinationWarehouseId && !loadingDestination && destinationLocations.length === 0}
            <span class="block text-xs text-warning">La bodega destino necesita una ubicación activa apta para almacenar.</span>
          {:else}
            <span class="block text-xs text-foreground-muted">Es la zona donde llega el envío. Al confirmar la recepción queda en cuarentena; después puedes elegir la ubicación final.</span>
          {/if}
        </label>
        <label class="space-y-1.5 text-sm font-medium text-foreground">
          Motivo o nota del despacho
          <input class="w-full rounded-xl border border-border bg-surface px-3 py-2.5" bind:value={reason} maxlength="120" placeholder={mode === 'request' ? 'Obligatorio si cambias la cantidad pendiente' : 'Indica por qué se envía este abastecimiento'} aria-required={dispatchRequiresReason} />
          {#if dispatchRequiresReason}<span class="block text-xs text-warning">Registra el motivo del surtido parcial, excedente o abastecimiento.</span>{:else if mode === 'request'}<span class="block text-xs text-foreground-muted">La cantidad coincide con lo pendiente; la nota es opcional.</span>{/if}
        </label>
      </div>

      <div class="space-y-3">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 class="font-semibold text-foreground">Plan de surtido</h3>
            <p class="text-xs text-foreground-muted">Ajusta la cantidad por unidad logística. Si envías solo una parte, se crea una unidad hija y el resto permanece en esta bodega.</p>
          </div>
        </div>

        {#if loadingStock}
          <p class="rounded-xl border border-border px-4 py-5 text-sm text-foreground-muted">Consultando existencias de la matriz…</p>
        {:else if stockError}
          <p class="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-danger/30 bg-danger/10 px-4 py-4 text-sm text-danger" role="alert">
            <span>No se pudo confirmar el inventario disponible. {stockError}</span>
            <Button variant="secondary" size="sm" onclick={() => void loadAvailableUnits(sourceWarehouseId)}>Reintentar inventario</Button>
          </p>
        {:else if mode === 'request' && !selectedRequest}
          <p class="rounded-xl border border-border px-4 py-5 text-sm text-foreground-muted">{requestLoading ? 'Cargando la solicitud elegida…' : 'Elige el despacho desde el reparto por producto y sucursal.'}</p>
        {:else if mode === 'request' && selectedRequest && requestInventoryItemIds.length === 0}
          <p class="rounded-xl border border-warning/30 bg-warning/10 px-4 py-4 text-sm text-foreground">Los productos de esta solicitud aún no tienen identidad activa en Inventario. Habilítalos antes de preparar el envío.</p>
        {:else if mode === 'request' && selectedRequest && requestUnitMismatches.length > 0}
          <p class="rounded-xl border border-warning/30 bg-warning/10 px-4 py-4 text-sm text-foreground">Hay productos cuya unidad solicitada no es la unidad base del inventario. Configura su conversión para evitar enviar cantidades incorrectas.</p>
        {:else if requestFilteredUnits.length === 0}
          <p class="rounded-xl border border-border px-4 py-5 text-sm text-foreground-muted">{mode === 'request' && selectedRequest ? 'La matriz no tiene unidades disponibles de los productos de esta solicitud.' : 'La matriz no tiene unidades disponibles para enviar.'}</p>
        {:else}
          <div class="overflow-x-auto rounded-xl border border-border">
            <table class="min-w-full divide-y divide-border text-sm">
              <thead class="bg-surface-subtle text-left text-xs uppercase tracking-wide text-foreground-muted">
                <tr><th class="px-3 py-3">Producto</th><th class="px-3 py-3">Unidad logística</th><th class="px-3 py-3">Origen</th><th class="px-3 py-3 text-right">Disponible</th><th class="px-3 py-3">Cantidad a enviar</th><th class="px-3 py-3">Lote</th></tr>
              </thead>
              <tbody class="divide-y divide-border">
                {#each requestFilteredUnits as unit (unit.id)}
                  <tr class="hover:bg-surface-subtle/60">
                    <td class="px-3 py-3"><div class="font-medium text-foreground">{unit.product_name ?? 'Producto sin nombre'}</div><div class="font-mono text-xs text-foreground-muted">{unit.product_sku ?? 'SKU sin registrar'}</div></td>
                    <td class="px-3 py-3"><div class="font-mono text-xs text-primary">{unit.code}</div><div class="text-xs text-foreground-muted">{unit.origin_handling_unit_id ? `Fraccionada de ${unit.origin_handling_unit_code ?? unit.origin_handling_unit_id.slice(0, 8)}` : unit.measurement_status === 'verified' ? 'Medición verificada' : unit.measurement_source === 'split_estimate' ? 'Medidas estimadas tras fraccionar' : unit.measurement_status === 'complete' ? 'Medición completa' : 'Medición pendiente'}</div></td>
                    <td class="px-3 py-3 text-foreground-muted">{unit.location_code}</td>
                    <td class="px-3 py-3 text-right font-medium text-foreground">{formatQuantity(unit.quantity_base)} {unit.base_unit_symbol ?? unit.base_unit_name ?? 'base'}</td>
                    <td class="px-3 py-3"><label class="sr-only" for={`allocation-${unit.id}`}>Cantidad a enviar de {unit.code}</label><input id={`allocation-${unit.id}`} class="w-36 rounded-lg border border-border bg-surface px-3 py-2 text-right" type="number" min="0" max={unit.quantity_base} step="0.000001" value={plannedQuantities[unit.id] ?? 0} oninput={(event) => setPlannedQuantity(unit.id, event.currentTarget.value)} aria-label={`Cantidad a enviar de ${unit.code}`} /><span class="ml-2 text-xs text-foreground-muted">{unit.base_unit_symbol ?? unit.base_unit_name ?? 'base'}</span></td>
                    <td class="px-3 py-3 text-foreground-muted">{unit.lot_code ?? '—'}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      </div>

      <footer class="flex flex-wrap items-center justify-between gap-4 border-t border-border pt-4">
        <div class="space-y-1 text-sm text-foreground-muted">
          <p>A enviar: <strong class="text-foreground">{selectedUnits.length}</strong> unidad(es) logística(s) · <strong class="text-foreground">{allocationSummary(selectedUnits) || '0 unidades'}</strong></p>
          {#if partialAllocationCount > 0}<p class="max-w-2xl text-xs text-warning">{partialAllocationCount} unidad(es) se dividirán. El remanente seguirá en la matriz; peso y volumen quedan estimados y requerirán verificación en destino.</p>{/if}
          {#if mode === 'request' && selectedRequest && selectedQuantity > 0 && !requestPlanMatchesRemainingDemand()}<p class="text-xs text-warning">El plan difiere de la cantidad pendiente de la solicitud; escribe el motivo antes de despachar.</p>{/if}
        </div>
        <Button disabled={saving || loadingStock || Boolean(stockError) || selectedUnits.length === 0 || !destinationLocationId || (dispatchRequiresReason && !reason.trim()) || (mode === 'request' && (!selectedRequest || requestUnitMismatches.length > 0))} onclick={dispatchSelectedUnits}>
          {saving ? 'Procesando…' : `Despachar ${allocationSummary(selectedUnits) || 'unidades'}`}
        </Button>
      </footer>
    </section>
    {/if}
    {/if}

    <section class="space-y-4 rounded-2xl border border-border bg-surface p-5 sm:p-6">
      <div class="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 class="text-lg font-semibold text-foreground">Recepciones de traslado pendientes</h2>
          <p class="mt-1 text-sm text-foreground-muted">Revisa los envíos que están en tránsito hacia cada bodega. Filtra una sola o muestra todas las bodegas disponibles para tu usuario.</p>
        </div>
        <span class="rounded-full border border-warning/30 bg-warning/10 px-3 py-1 text-xs font-medium text-warning">
          {#if pendingReceiptLoadState === 'loading'}Consultando pendientes…
          {:else if pendingReceiptLoadState === 'error'}Pendientes no disponibles
          {:else if pendingReceiptLoadState === 'partial'}{receiverUnits.length} unidad(es) cargada(s) · consulta parcial
          {:else}{receiverUnits.length} unidad(es) pendiente(s)
          {/if}
        </span>
      </div>

      <label class="block max-w-2xl space-y-1.5 text-sm font-medium text-foreground">
        Bodega destino a consultar
        <select class="w-full rounded-xl border border-border bg-surface px-3 py-2.5" value={receiverWarehouseId} onchange={(event) => void chooseReceiverWarehouse(event.currentTarget.value)}>
          <option value={ALL_WAREHOUSES}>Todas las bodegas</option>
          {#each receivingWarehouses as warehouse (warehouse.id)}
            <option value={warehouse.id}>{warehouseLabel(warehouse)}</option>
          {/each}
        </select>
      </label>

      {#if transitError && pendingReceiptLoadState === 'partial'}
        <p class="rounded-xl border border-danger/30 bg-danger/10 px-3 py-3 text-sm text-danger" role="alert">{transitError}</p>
      {/if}

      {#if !canReceiveTransfers}
        <p class="rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-foreground">
          Tu perfil puede consultar estos traslados, pero necesita el permiso de recepción de inventario para registrar cantidades recibidas.
        </p>
      {/if}
      {#if receivingWarehouses.length === 0}
        <p class="rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-foreground">
          No hay bodegas activas aptas para recibir en tu alcance. Pide al administrador que habilite una ubicación de almacenamiento.
        </p>
      {/if}

      {#if pendingReceiptLoadState === 'loading'}
        <p class="rounded-xl border border-border px-4 py-5 text-sm text-foreground-muted">Consultando traslados en tránsito…</p>
      {:else if pendingReceiptLoadState === 'error'}
        <div class="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-danger/30 bg-danger/10 px-4 py-4 text-sm text-danger" role="alert">
          <span>No se pudo confirmar cuántas recepciones están pendientes. {transitError}</span>
          <Button variant="secondary" size="sm" onclick={() => void loadTransitForSelection(receiverWarehouseId)}>Reintentar consulta</Button>
        </div>
      {:else if pendingReceiptLoadState === 'empty'}
        <div class="rounded-xl border border-border border-dashed px-4 py-7 text-center">
          <p class="font-medium text-foreground">No hay traslados pendientes de recibir</p>
          <p class="mt-1 text-sm text-foreground-muted">{receiverWarehouseId === ALL_WAREHOUSES ? 'No hay envíos pendientes en las bodegas disponibles.' : 'Los envíos a esta bodega aparecerán aquí hasta que se confirme su llegada.'}</p>
        </div>
      {:else}
        {#each pendingGroups as group (group.key)}
          <article class="space-y-3 rounded-xl border border-border p-4">
            <header class="flex flex-wrap items-center justify-between gap-3">
              <div><p class="font-mono text-sm font-semibold text-primary">{group.reference}</p><p class="text-xs text-foreground-muted">Destino: {group.warehouseLabel} · {group.units.length} unidad(es)</p></div>
              <p class="text-sm font-medium text-foreground">{quantitySummary(group.units)}</p>
            </header>
            <div class="overflow-x-auto rounded-lg border border-border">
              <table class="min-w-full divide-y divide-border text-sm">
                <thead class="bg-surface-subtle text-left text-xs uppercase tracking-wide text-foreground-muted"><tr><th class="px-3 py-2.5">Recibir</th><th class="px-3 py-2.5">Producto</th><th class="px-3 py-2.5">Unidad logística</th><th class="px-3 py-2.5">Punto de recepción</th><th class="px-3 py-2.5 text-right">En tránsito</th><th class="px-3 py-2.5 text-right">Cantidad contada</th></tr></thead>
                <tbody class="divide-y divide-border">
                  {#each group.units as unit (unit.id)}
                    <tr>
                      <td class="px-3 py-3"><input type="checkbox" aria-label={`Confirmar recepción de ${unit.code}`} checked={selectedReceiptUnitIds.includes(unit.id)} onchange={() => toggleReceiptUnit(unit.id)} /></td>
                      <td class="px-3 py-3"><div class="font-medium text-foreground">{unit.product_name ?? 'Producto sin nombre'}</div><div class="font-mono text-xs text-foreground-muted">{unit.product_sku ?? 'SKU sin registrar'}</div></td>
                      <td class="px-3 py-3 font-mono text-xs text-primary">{unit.code}{#if unit.origin_handling_unit_code}<span class="block font-sans text-[11px] text-foreground-muted">Fraccionada de {unit.origin_handling_unit_code}</span>{/if}</td>
                      <td class="px-3 py-3 text-foreground-muted">{unit.location_code}</td>
                      <td class="px-3 py-3 text-right font-medium text-foreground">{formatQuantity(unit.quantity_base)} {unit.base_unit_symbol ?? unit.base_unit_name ?? 'base'}</td>
                      <td class="px-3 py-3 text-right">
                        <label class="sr-only" for={`receipt-quantity-${unit.id}`}>Cantidad contada de {unit.code}</label>
                        <input
                          id={`receipt-quantity-${unit.id}`}
                          class="w-36 rounded-lg border border-border bg-surface px-3 py-2 text-right"
                          type="number"
                          min="0"
                          max={unit.quantity_base}
                          step="0.000001"
                          value={receiptQuantities[unit.id] ?? unit.quantity_base}
                          oninput={(event) => setReceiptQuantity(unit.id, event.currentTarget.value)}
                          aria-label={`Cantidad contada de ${unit.code}`}
                        />
                        <span class="ml-2 text-xs text-foreground-muted">{unit.base_unit_symbol ?? unit.base_unit_name ?? 'base'}</span>
                        {#if (receiptQuantities[unit.id] ?? unit.quantity_base) < unit.quantity_base - 0.000001}
                          <span class="mt-1 block text-xs text-warning">Faltan {formatQuantity(unit.quantity_base - (receiptQuantities[unit.id] ?? unit.quantity_base))}; seguirá en tránsito.</span>
                        {/if}
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
            <div class="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3">
              <p class="text-xs text-foreground-muted">Recibir ahora: <strong class="text-foreground">{receiptQuantitySummary(group.units) || '0 unidades'}</strong></p>
              <Button variant="secondary" size="sm" disabled={!canReceiveTransfers || saving || !group.units.some((unit) => selectedReceiptUnitIds.includes(unit.id) && (receiptQuantities[unit.id] ?? unit.quantity_base) > 0)} onclick={() => receiveGroup(group.reference, group.units)}>
                {saving ? 'Registrando…' : 'Confirmar recepción contada'}
              </Button>
            </div>
          </article>
        {/each}
      {/if}
    </section>
  {/if}
</div>
