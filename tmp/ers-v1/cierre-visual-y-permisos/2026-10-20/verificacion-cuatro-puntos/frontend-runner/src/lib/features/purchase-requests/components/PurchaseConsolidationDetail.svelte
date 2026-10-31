<script lang="ts">
  import '../consolidation-fields.css';
  import { goto } from '$app/navigation';
  import { page as currentPage } from '$app/state';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import PurchaseConsolidationHistory from './PurchaseConsolidationHistory.svelte';
  import PurchaseConsolidationInventoryPanel from './PurchaseConsolidationInventoryPanel.svelte';
  import PurchaseConsolidationRfqs from '$lib/features/purchase-quotations/components/PurchaseConsolidationRfqs.svelte';
  import PurchaseConsolidationAdjudication from './PurchaseConsolidationAdjudication.svelte';
  import PurchaseRequestProductPicker from './PurchaseRequestProductPicker.svelte';
  import PurchaseFlowRibbon from './PurchaseFlowRibbon.svelte';
  import { api, HttpError } from '$lib/api/client';
  import { catalogApi } from '$lib/api/catalog';
  import { purchaseConsolidationsApi } from '$lib/api/purchase-consolidations';
  import { branch } from '$lib/stores/branch.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { Product } from '$lib/types/catalog';
  import type {
    ApprovedRequestCandidate,
    BranchDemandLevel,
    PurchaseConsolidation,
    PurchaseConsolidationInventorySnapshot
  } from '$lib/types/purchase-consolidation';
  import type { WarehouseOut } from '$lib/api/client';

  interface SourceDraft {
    sourceId: string;
    originalQuantity: string;
    includedQuantity: string;
    reason: string;
    originalDemandLevel: BranchDemandLevel | '';
    demandLevel: BranchDemandLevel | '';
  }
  interface CentralDraft {
    productId: number;
    quantity: string;
    originalQuantity: string;
    reason: string;
  }
  interface NewCentralDemand {
    productId: number;
    sku: string;
    name: string;
    quantity: number;
    reason: string;
  }

  let id = $derived(currentPage.params.id ?? '');
  const today = () => new Date().toISOString().slice(0, 10);
  const ninetyDaysAgo = () => {
    const value = new Date();
    value.setDate(value.getDate() - 90);
    return value.toISOString().slice(0, 10);
  };
  let item = $state<PurchaseConsolidation | null>(null);
  let loadGeneration = 0;
  let sourceDrafts = $state<Record<string, SourceDraft>>({});
  let centralDrafts = $state<Record<string, CentralDraft>>({});
  let newCentralDemands = $state<NewCentralDemand[]>([]);
  let candidates = $state<ApprovedRequestCandidate[]>([]);
  let warehouses = $state<WarehouseOut[]>([]);
  let centralWarehouses = $derived(
    warehouses.filter(
      (warehouse) => warehouse.is_central && warehouse.status === 'active'
    )
  );
  let inventorySnapshot = $state<PurchaseConsolidationInventorySnapshot | null>(null);
  let inventorySnapshotLoading = $state(false);
  let selectedRequestIds = $state<string[]>([]);
  let notesDraft = $state('');
  let loading = $state(true);
  let saving = $state(false);
  let loadingCandidates = $state(false);
  let warehousesLoading = $state(false);
  let warehousesError = $state<string | null>(null);
  let candidatesError = $state<string | null>(null);
  let error = $state<string | null>(null);
  let successMessage = $state<string | null>(null);
  let changeReason = $state('');
  let searchProduct = $state('');
  let centralCatalogProducts = $state<Product[]>([]);
  let centralCatalogPage = $state(0);
  let centralCatalogPages = $state(0);
  let centralCatalogLoading = $state(false);
  let centralCatalogError = $state<string | null>(null);
  let centralCatalogStarted = false;
  let selectedProductId = $state('');
  let selectedCentralProduct = $state<Product | null>(null);
  let centralQuantity = $state('1');
  let centralReason = $state('');
  let newSourceReason = $state('');
  let sourceDateFrom = $state(ninetyDaysAgo());
  let sourceDateTo = $state(today());
  let sourceBranchId = $state(branch.id ?? '');
  let showCancelForm = $state(false);
  let cancelReason = $state('');
  let showCloseForm = $state(false);
  let closeReason = $state('');
  let closeCoveredOutsideConsolidation = $state(false);
  let centralWarehouseId = $state('');
  let originalCentralWarehouseId = $state('');
  let centralDestinationRepairMessage = $state('');
  let selectedCentralWarehouseName = $derived(
    centralWarehouses.find((warehouse) => warehouse.id === centralWarehouseId)?.name ??
      (centralWarehouseId === item?.central_warehouse_id ? item?.central_warehouse_name : null)
  );
  let warehouseDefaultsAppliedForId: string | null = null;
  let selectedCentralWarehouseIsValid = $derived(
    !centralWarehouseId || centralWarehouses.some((warehouse) => warehouse.id === centralWarehouseId)
  );
  let legacyCentralWarehouse = $derived(
    centralWarehouseId
      ? warehouses.find((warehouse) => warehouse.id === centralWarehouseId && !centralWarehouses.some((central) => central.id === warehouse.id))
      : undefined
  );
  let automaticCandidatesLoaded = false;
  const centralDestinationError = 'El borrador tiene cantidades destinadas a bodega central, pero falta elegir la bodega. Selecciónala arriba o pon esas cantidades en 0.';

  let branchDemandGroups = $derived.by(() => {
    const groups = new Map<string, {
      sourceIds: string[];
      requestIds: Set<string>;
      branchName: string;
    }>();
    for (const line of item?.lines ?? []) {
      for (const source of line.sources) {
        const key = `${source.branch_id}:${line.product_id}`;
        const group = groups.get(key) ?? {
          sourceIds: [],
          requestIds: new Set<string>(),
          branchName: source.branch_name ?? 'Sucursal'
        };
        group.sourceIds.push(source.id);
        group.requestIds.add(source.purchase_request_id);
        groups.set(key, group);
      }
    }
    const result = new Map<string, { sourceIds: string[]; requestCount: number; branchName: string }>();
    for (const [key, group] of groups) {
      result.set(key, {
        sourceIds: group.sourceIds,
        requestCount: group.requestIds.size,
        branchName: group.branchName
      });
    }
    return result;
  });

  function branchDemandKey(productId: number, branchId: string) {
    return `${branchId}:${productId}`;
  }

  function demandLevelLabel(level: BranchDemandLevel | '') {
    if (level === 'low') return 'Demanda baja';
    if (level === 'medium') return 'Demanda media';
    if (level === 'high') return 'Demanda alta';
    return 'Sin clasificar';
  }

  function message(err: unknown) {
    return err instanceof HttpError ? err.message : err instanceof Error ? err.message : 'Ocurrió un error inesperado.';
  }

  async function load(requestId = id) {
    const generation = ++loadGeneration;
    if (!requestId) {
      item = null;
      loading = false;
      return;
    }
    loading = true;
    error = null;
    try {
      const loaded = await purchaseConsolidationsApi.get(requestId);
      if (generation !== loadGeneration) return;
      applyLoadedConsolidation(loaded);
    } catch (err: unknown) {
      if (generation !== loadGeneration) return;
      error = message(err);
      item = null;
    } finally {
      if (generation === loadGeneration) loading = false;
    }
  }

  function valueChanged(current: string, original: string) {
    return Number(current) !== Number(original);
  }

  function branchDraftQuantity(line: PurchaseConsolidation['lines'][number]) {
    if (line.sources.length === 0) return Number(line.branch_quantity);
    return line.sources.reduce((sum, source) =>
      sum + Number(sourceDrafts[source.id]?.includedQuantity ?? source.included_quantity), 0
    );
  }

  function centralDraftQuantity(line: PurchaseConsolidation['lines'][number]) {
    return Number(centralDrafts[line.id]?.quantity ?? line.central_quantity);
  }

  function hasCentralDemand() {
    return (item?.lines.some((line) => centralDraftQuantity(line) > 0) ?? false)
      || newCentralDemands.some((demand) => demand.quantity > 0);
  }

  function clearResolvedCentralDestinationError() {
    if (error === centralDestinationError && (centralWarehouseId || !hasCentralDemand())) error = null;
  }

  function selectCentralWarehouse(event: Event) {
    centralWarehouseId = (event.currentTarget as HTMLSelectElement).value;
    centralDestinationRepairMessage = '';
    inventorySnapshot = null;
    clearResolvedCentralDestinationError();
  }

  function totalDraftQuantity(line: PurchaseConsolidation['lines'][number]) {
    return branchDraftQuantity(line) + centralDraftQuantity(line);
  }

  function setDemandLevel(productId: number, branchId: string, level: BranchDemandLevel | '') {
    if (!item) return;
    const next = { ...sourceDrafts };
    for (const line of item.lines) {
      if (line.product_id !== productId) continue;
      for (const source of line.sources) {
        const draft = next[source.id];
        if (source.branch_id !== branchId || !draft) continue;
        next[source.id] = { ...draft, demandLevel: level };
      }
    }
    sourceDrafts = next;
  }

  function applyLoadedConsolidation(loaded: PurchaseConsolidation) {
    item = loaded;
    centralWarehouseId = loaded.central_warehouse_id ?? '';
    originalCentralWarehouseId = loaded.central_warehouse_id ?? '';
    notesDraft = loaded.notes ?? '';
    sourceDrafts = Object.fromEntries(loaded.lines.flatMap((line) => line.sources.map((source) => [source.id, {
      sourceId: source.id,
      originalQuantity: source.included_quantity,
      includedQuantity: source.included_quantity,
      reason: source.reason ?? '',
      originalDemandLevel: source.demand_level ?? '',
      demandLevel: source.demand_level ?? ''
    }])));
    centralDrafts = Object.fromEntries(loaded.lines.map((line) => [line.id, {
      productId: line.product_id,
      quantity: line.central_quantity,
      originalQuantity: line.central_quantity,
      reason: line.central_reason ?? ''
    }]));
  }

  async function save() {
    if (!item || saving) return;
    saving = true;
    error = null;
    successMessage = null;
    try {
      const sourceChanges = Object.values(sourceDrafts)
        .filter((source) =>
          valueChanged(source.includedQuantity, source.originalQuantity)
          || source.demandLevel !== source.originalDemandLevel
        )
        .map((source) => ({
          source_id: source.sourceId,
          included_quantity: Number(source.includedQuantity),
          reason: source.reason,
          ...(source.demandLevel !== source.originalDemandLevel
            ? { demand_level: source.demandLevel || null }
            : {})
        }));
      const centralChanges = item.lines
        .filter((line) => {
          const draft = centralDrafts[line.id];
          return draft && valueChanged(draft.quantity, draft.originalQuantity);
        })
        .map((line) => {
          const draft = centralDrafts[line.id];
          return { line_id: line.id, product_id: draft?.productId ?? line.product_id, quantity: Number(draft?.quantity ?? 0), reason: draft?.reason ?? '' };
        });
      const centralAdds = newCentralDemands.map((draft) => ({ product_id: draft.productId, quantity: draft.quantity, reason: draft.reason }));
      const normalizedNotes = notesDraft.trim() || null;
      const notesChanged = normalizedNotes !== (item.notes?.trim() || null);
      if (sourceChanges.length + centralChanges.length + centralAdds.length === 0 && !notesChanged && centralWarehouseId === originalCentralWarehouseId) {
        error = 'No hay cambios que guardar.';
        return;
      }
      if (hasCentralDemand() && (!centralWarehouseId || !selectedCentralWarehouseIsValid)) {
        error = centralWarehouseId
          ? 'El destino actual no está disponible como bodega madre activa. Elige una bodega madre o pon las cantidades centrales en 0.'
          : centralDestinationError;
        return;
      }
      if (Object.values(sourceDrafts).some((source) =>
        valueChanged(source.includedQuantity, source.originalQuantity) && !source.reason.trim()
      )) {
        error = 'Escribe el motivo de cada cambio de cantidad en las solicitudes de sucursal.';
        return;
      }
      if ([...centralChanges, ...centralAdds].some((change) => !change.reason.trim())) {
        error = 'Escribe el motivo de cada cambio de cantidad del plan central.';
        return;
      }
      if (!changeReason.trim()) {
        error = 'Explica el motivo general de los cambios antes de guardar.';
        return;
      }
      const updated = await purchaseConsolidationsApi.update(item.id, {
        change_reason: changeReason,
        source_changes: sourceChanges,
        central_demands: [...centralChanges, ...centralAdds],
        notes: normalizedNotes,
        ...(centralWarehouseId !== originalCentralWarehouseId
          ? { central_warehouse_id: centralWarehouseId || null }
          : {})
      });
      newCentralDemands = [];
      inventorySnapshot = null;
      changeReason = '';
      applyLoadedConsolidation(updated);
      successMessage = 'Borrador guardado. El historial conserva los cambios y sus motivos.';
    } catch (err: unknown) {
      error = message(err);
    } finally {
      saving = false;
    }
  }

  async function loadWarehouses() {
    warehousesLoading = true;
    warehousesError = null;
    try {
      const scopeBranch = branch.accessAllBranches ? '' : (branch.id ?? '');
      const loadedWarehouses = await api.warehouses.catalogue({
        branch_id: scopeBranch,
        include_company_central: true
      });
      warehouses = loadedWarehouses;
      const mothers = loadedWarehouses.filter(
        (warehouse) =>
          warehouse.is_central &&
          warehouse.status === 'active'
      );
      const onlyMother = mothers.length === 1 ? mothers[0] : undefined;
      if (item && warehouseDefaultsAppliedForId !== item.id) {
        warehouseDefaultsAppliedForId = item.id;
        const savedDestinationIsValid = mothers.some(
          (warehouse) => warehouse.id === item?.central_warehouse_id
        );
        if (!savedDestinationIsValid && onlyMother && (item.central_warehouse_id || hasCentralDemand())) {
          centralWarehouseId = onlyMother.id;
          centralDestinationRepairMessage = item.central_warehouse_id
            ? 'El destino guardado era una bodega de sucursal. Seleccioné la casa matriz activa; guarda los cambios para corregir este borrador.'
            : 'Este plan tiene cantidades centrales. Seleccioné la casa matriz activa; guarda los cambios para vincular el destino.';
        }
      }
    } catch (err: unknown) {
      warehouses = [];
      warehousesError = message(err);
    } finally {
      warehousesLoading = false;
    }
  }

  async function loadInventorySnapshot() {
    if (!item || !centralWarehouseId || !selectedCentralWarehouseIsValid || centralWarehouseId !== originalCentralWarehouseId || inventorySnapshotLoading) return;
    inventorySnapshotLoading = true;
    error = null;
    try {
      inventorySnapshot = await purchaseConsolidationsApi.inventorySnapshot(item.id);
    } catch (err: unknown) {
      error = message(err);
      inventorySnapshot = null;
    } finally {
      inventorySnapshotLoading = false;
    }
  }

  async function loadCentralCatalogPage(page = centralCatalogPage + 1) {
    if (centralCatalogLoading || (centralCatalogPage > 0 && page > centralCatalogPages)) return;
    centralCatalogLoading = true;
    centralCatalogError = null;
    try {
      const response = await catalogApi.listProducts({ active_only: true, page, size: 100 });
      const eligibleProducts = response.items.filter(
        (product) => product.can_purchase !== false && product.lifecycle_status === 'active'
      );
      const knownIds = new Set(centralCatalogProducts.map((product) => product.id_product));
      centralCatalogProducts = page === 1
        ? eligibleProducts
        : [...centralCatalogProducts, ...eligibleProducts.filter((product) => !knownIds.has(product.id_product))];
      centralCatalogPage = response.meta.page;
      centralCatalogPages = response.meta.pages;
    } catch (err: unknown) {
      centralCatalogError = message(err);
    } finally {
      centralCatalogLoading = false;
    }
  }

  function cancelCentralDemandEntry() {
    selectedProductId = '';
    selectedCentralProduct = null;
    searchProduct = '';
    centralQuantity = '1';
    centralReason = '';
    error = null;
  }

  function queueCentralDemand() {
    const product = selectedCentralProduct?.id_product === Number(selectedProductId)
      ? selectedCentralProduct
      : centralCatalogProducts.find((candidate) => String(candidate.id_product) === selectedProductId);
    const quantity = Number(centralQuantity);
    if (!centralWarehouseId || !selectedCentralWarehouseIsValid) {
      error = 'Elige una bodega marcada como madre antes de agregar demanda central.';
      return;
    }
    if (!product || !Number.isFinite(quantity) || quantity <= 0 || !centralReason.trim()) {
      error = 'Selecciona un producto, una cantidad mayor que cero y explica la necesidad central.';
      return;
    }
    newCentralDemands = [...newCentralDemands, {
      productId: product.id_product, sku: product.sku, name: product.name,
      quantity, reason: centralReason.trim()
    }];
    selectedProductId = '';
    selectedCentralProduct = null;
    centralQuantity = '1';
    centralReason = '';
    searchProduct = '';
    error = null;
  }

  async function loadEligibleRequests() {
    if (!item) return;
    loadingCandidates = true;
    candidatesError = null;
    try {
      const response = await purchaseConsolidationsApi.eligibleRequests({
        date_from: sourceDateFrom,
        date_to: sourceDateTo,
        branch_id: sourceBranchId || undefined,
        page: 1,
        size: 100
      });
      candidates = response.items;
    } catch (err: unknown) {
      candidatesError = message(err);
      candidates = [];
    } finally {
      loadingCandidates = false;
    }
  }

  function toggleRequest(id: string, checked: boolean) {
    selectedRequestIds = checked ? [...new Set([...selectedRequestIds, id])] : selectedRequestIds.filter((requestId) => requestId !== id);
  }

  async function addRequests() {
    if (!item || selectedRequestIds.length === 0 || !newSourceReason.trim()) {
      error = 'Selecciona solicitudes y explica por qué se agregan a este consolidado.';
      return;
    }
    saving = true;
    error = null;
    successMessage = null;
    try {
      item = await purchaseConsolidationsApi.addRequests(item.id, { request_ids: selectedRequestIds, reason: newSourceReason.trim() });
      selectedRequestIds = [];
      newSourceReason = '';
      await load();
      await loadEligibleRequests();
      if (item) successMessage = 'Solicitudes agregadas al borrador y registradas en el historial.';
    } catch (err: unknown) {
      error = message(err);
    } finally {
      saving = false;
    }
  }

  async function cancelDraft() {
    if (!item || !cancelReason.trim()) {
      error = 'Indica el motivo de cancelación.';
      return;
    }
    saving = true;
    try {
      item = await purchaseConsolidationsApi.cancel(item.id, cancelReason.trim());
      showCancelForm = false;
      cancelReason = '';
      await load();
    } catch (err: unknown) {
      error = message(err);
    } finally {
      saving = false;
    }
  }

  async function closeConsolidation() {
    if (!item || !closeReason.trim()) {
      error = 'Indica el motivo para cerrar el consolidado.';
      return;
    }
    if (hasUnsavedDraftChanges) {
      error = 'Guarda los cambios pendientes antes de cerrar el consolidado.';
      return;
    }
    saving = true;
    error = null;
    successMessage = null;
    try {
      const closedItem = await purchaseConsolidationsApi.close(
        item.id,
        closeReason.trim(),
        closeCoveredOutsideConsolidation
      );
      item = closedItem;
      const closureEvent = [...closedItem.events].reverse().find((event) => event.action === 'closed');
      showCloseForm = false;
      closeReason = '';
      closeCoveredOutsideConsolidation = false;
      successMessage = closureEvent?.changes['coverage_basis'] === 'covered_outside_consolidation'
        ? 'Consolidado cerrado. La demanda pendiente quedó registrada como cubierta fuera de este consolidado; no se creó otra solicitud.'
        : 'Consolidado cerrado. Las adjudicaciones y su historial se conservaron.';
      await load();
    } catch (err: unknown) {
      error = message(err);
    } finally {
      saving = false;
    }
  }

  function formatDate(value: string | null) {
    if (!value) return '—';
    return new Intl.DateTimeFormat('es-SV', { timeZone: 'America/El_Salvador', day: '2-digit', month: '2-digit', year: 'numeric' }).format(new Date(value));
  }
  function formatQuantity(value: string | number) {
    return new Intl.NumberFormat('es-SV', { maximumFractionDigits: 6 }).format(Number(value));
  }

  function totalsByUnit(valueForLine: (line: PurchaseConsolidation['lines'][number]) => number) {
    const totals = new Map<number, { unitName: string; quantity: number }>();
    for (const line of item?.lines ?? []) {
      const current = totals.get(line.unit_id);
      totals.set(line.unit_id, {
        unitName: line.unit_name,
        quantity: (current?.quantity ?? 0) + valueForLine(line)
      });
    }
    return [...totals.entries()]
      .map(([, total]) => `${formatQuantity(total.quantity)} ${total.unitName}`)
      .join(' · ') || '0';
  }

  let hasUnsavedCentralChanges = $derived(
    item?.lines.some((line) => {
      const draft = centralDrafts[line.id];
      return draft && valueChanged(draft.quantity, draft.originalQuantity);
    }) ?? false
  );

  let hasUnsavedDraftChanges = $derived.by(() => {
    if (!item || item.status !== 'draft') return false;
    return Object.values(sourceDrafts).some((source) =>
      valueChanged(source.includedQuantity, source.originalQuantity)
      || source.demandLevel !== source.originalDemandLevel
    )
      || Object.values(centralDrafts).some((draft) => valueChanged(draft.quantity, draft.originalQuantity))
      || newCentralDemands.length > 0
      || selectedRequestIds.length > 0
      || (notesDraft.trim() || null) !== (item.notes?.trim() || null)
      || centralWarehouseId !== originalCentralWarehouseId;
  });

  $effect(() => {
    const requestId = id;
    if (requestId) void load(requestId);
    else {
      item = null;
      loading = false;
    }
  });
  $effect(() => {
    const canEdit = item?.status === 'draft';
    if (canEdit && !automaticCandidatesLoaded) {
      automaticCandidatesLoaded = true;
      void loadEligibleRequests();
    }
  });

  $effect(() => {
    if (item?.status === 'draft') {
      void loadWarehouses();
      if (permissions.hasPermission('purchase_requests:manage') && !centralCatalogStarted) {
        centralCatalogStarted = true;
        void loadCentralCatalogPage(1);
      }
    }
  });
</script>

<div class="purchase-consolidation-detail min-h-full bg-background px-4 pb-8 pt-4 sm:px-6 sm:pt-6 md:px-8 md:pt-8">
  <div class="mb-5 flex flex-wrap items-end justify-between gap-4">
    <div>
      <a href="/purchase-requests" class="text-sm text-primary hover:underline">← Solicitudes y consolidados</a>
      <p class="mt-2 text-xs font-semibold uppercase tracking-wider text-primary">Consolidado de compra</p>
      <h1 class="mt-1 text-2xl font-semibold text-foreground">{item?.code ?? 'Cargando…'}</h1>
      {#if item}<p class="mt-1 text-sm text-foreground-muted">Período {formatDate(item.period_start)} — {formatDate(item.period_end)} · {item.status === 'draft' ? 'Borrador editable' : item.status === 'frozen' ? 'Enviado a cotización · Inmutable' : item.status === 'closed' ? 'Consolidación cerrada' : 'Cancelado'}</p>{/if}
    </div>
    {#if item}<span class={`rounded-full border px-3 py-1.5 text-xs font-semibold ${item.status === 'closed' ? 'border-success/30 bg-success/10 text-success' : item.status === 'cancelled' ? 'border-danger/30 bg-danger/10 text-danger' : item.status === 'frozen' ? 'border-primary/30 bg-primary/10 text-primary' : 'border-warning/30 bg-warning/10 text-warning'}`}>{item.status === 'draft' ? 'Borrador' : item.status === 'frozen' ? 'Enviado a cotización' : item.status === 'closed' ? 'Consolidado cerrado' : 'Cancelado'}</span>{/if}
  </div>

  <PurchaseFlowRibbon currentStep={item?.status === 'frozen' || item?.status === 'closed' ? 3 : 2} closed={item?.status === 'closed'} />

  {#if error}<div class="mb-4 flex items-start justify-between gap-3 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert"><span>{error}</span><button type="button" class="text-danger" aria-label="Cerrar mensaje" onclick={() => error = null}>×</button></div>{/if}
  {#if successMessage}<div class="mb-4 rounded-xl border border-success/30 bg-success/10 px-4 py-3 text-sm text-success" role="status">{successMessage}</div>{/if}
  {#if loading}
    <Card class="space-y-3 p-4">{#each Array(4) as _}<div class="skeleton h-14 w-full rounded-md"></div>{/each}</Card>
  {:else if !item}
    <Card class="p-8 text-center"><p class="text-sm text-foreground-muted">No se pudo cargar el consolidado.</p><Button class="mt-3" size="sm" onclick={() => void load()}>Reintentar</Button></Card>
  {:else}
    {#if item.status === 'closed'}
      <Card class="mb-4 border border-success/25 p-4">
        <h2 class="font-semibold text-foreground">Consolidación cerrada</h2>
        <p class="mt-1 text-sm text-foreground-muted">Se conservaron las solicitudes fuente y las decisiones. Puedes continuar las órdenes de compra adjudicadas; los productos cubiertos por inventario o compras individuales quedan explicados en el historial. La recepción de mercancía sigue su propio flujo.</p>
      </Card>
    {:else if permissions.hasPermission('purchase_requests:manage') && (item.status === 'draft' || item.status === 'frozen')}
      <Card class="mb-4 border border-success/20 p-4">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="max-w-3xl">
            <h2 class="font-semibold text-foreground">¿Ya terminaste de gestionar esta demanda?</h2>
            <p class="mt-1 text-sm text-foreground-muted">Cierra cuando termine la gestión de esta demanda consolidada. Puede estar adjudicada aquí o ya cubierta por inventario y compras individuales.</p>
          </div>
          <Button variant="success" disabled={saving || hasUnsavedDraftChanges} onclick={() => showCloseForm = !showCloseForm}>
            {showCloseForm ? 'Ocultar cierre' : 'Cerrar consolidado'}
          </Button>
        </div>
        {#if hasUnsavedDraftChanges}
          <p class="mt-3 text-xs text-warning" role="status">Guarda los cambios pendientes antes de cerrar.</p>
        {/if}
        {#if showCloseForm}
          <div class="mt-4 border-t border-border pt-4">
            <label class="consolidation-field-label">Motivo del cierre <span class="text-danger">*</span>
              <textarea id="close-reason" required aria-describedby="close-guidance" maxlength="2000" rows="2" bind:value={closeReason} placeholder="Ej. productos recibidos mediante compras individuales; no se requiere otra compra" class="consolidation-field-control h-auto py-2"></textarea>
            </label>
            <label for="close-covered-outside" class="mt-3 flex cursor-pointer items-start gap-3 rounded-lg border border-warning/25 bg-warning/5 p-3 text-sm text-foreground">
              <input
                id="close-covered-outside"
                type="checkbox"
                checked={closeCoveredOutsideConsolidation}
                onchange={(event) => {
                  closeCoveredOutsideConsolidation = (event.currentTarget as HTMLInputElement).checked;
                  error = null;
                }}
                class="mt-0.5 h-4 w-4 shrink-0 accent-primary"
              />
              <span>
                La demanda pendiente ya está cubierta por inventario recibido o por una compra/cotización individual finalizada; no debe solicitarse otra vez.
                <span class="mt-1 block text-xs text-foreground-muted">Al confirmar, los productos y cantidades sin adjudicación en este consolidado quedarán anotados en el historial. No se crea otra solicitud ni se modifica el inventario.</span>
              </span>
            </label>
            <p id="close-guidance" class="mt-2 text-xs text-foreground-muted">Al cerrar no podrás agregar RFQ ni modificar o revertir adjudicaciones. Las órdenes de compra que ya tengan adjudicación siguen disponibles; las solicitudes y órdenes existentes no se cancelan.</p>
            <div class="mt-3 flex flex-wrap justify-end gap-2">
              <Button variant="secondary" disabled={saving} onclick={() => { showCloseForm = false; closeReason = ''; closeCoveredOutsideConsolidation = false; }}>Seguir revisando</Button>
              <Button variant="success" disabled={saving || hasUnsavedDraftChanges || !closeReason.trim()} onclick={closeConsolidation}>{saving ? 'Cerrando…' : 'Confirmar cierre'}</Button>
            </div>
          </div>
        {/if}
      </Card>
    {/if}

    <div class="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
      <Card class="p-4"><p class="text-xs uppercase tracking-wider text-foreground-muted">Demanda de sucursales</p><p class="mt-2 text-sm font-semibold leading-6 text-foreground">{totalsByUnit(branchDraftQuantity)}</p><p class="mt-1 text-xs text-foreground-muted">Cantidades incluidas ahora · agrupadas por unidad</p></Card>
      <Card class="p-4"><p class="text-xs uppercase tracking-wider text-foreground-muted">Plan central</p><p class="mt-2 text-sm font-semibold leading-6 text-foreground">{totalsByUnit(centralDraftQuantity)}</p><p class="mt-1 text-xs text-foreground-muted">{centralWarehouseId ? (centralWarehouses.find((warehouse) => warehouse.id === centralWarehouseId)?.name ?? item.central_warehouse_name ?? 'Bodega seleccionada') : 'Bodega madre sin definir'}</p>{#if hasUnsavedCentralChanges}<p class="mt-1 text-xs text-warning">Incluye cantidades editadas que aún no se han guardado.</p>{/if}{#if newCentralDemands.length > 0}<p class="mt-1 text-xs text-warning">Hay {newCentralDemands.length} demanda(s) nueva(s) pendiente(s) de guardar; aparecen abajo.</p>{/if}</Card>
      <Card class="p-4"><p class="text-xs uppercase tracking-wider text-foreground-muted">Total consolidado</p><p class="mt-2 text-sm font-semibold leading-6 text-primary">{totalsByUnit(totalDraftQuantity)}</p><p class="mt-1 text-xs text-foreground-muted">Incluye cantidades editadas; no se suman unidades diferentes entre sí.</p>{#if newCentralDemands.length > 0}<p class="mt-1 text-xs text-warning">Aún no incluye las demandas nuevas listadas abajo.</p>{/if}</Card>
    </div>

    <PurchaseConsolidationRfqs consolidationId={item.id} status={item.status} />
    <div id="adjudication" class="scroll-mt-24">
      <PurchaseConsolidationAdjudication consolidationId={item.id} status={item.status} />
    </div>

    {#if item.status === 'draft' && permissions.hasPermission('purchase_requests:manage')}
      <Card class="mb-4 p-4">
        <label class="consolidation-field-label max-w-xl">Bodega madre destino (opcional)
          <select value={centralWarehouseId} onchange={selectCentralWarehouse} disabled={warehousesLoading || warehousesError !== null} class="consolidation-field-control">
            <option value="">Sin demanda central</option>
            {#if legacyCentralWarehouse}<option value={legacyCentralWarehouse.id}>{legacyCentralWarehouse.name} · {legacyCentralWarehouse.branch_name} (no disponible como bodega madre)</option>{/if}
            {#each centralWarehouses as warehouse (warehouse.id)}<option value={warehouse.id}>{warehouse.name} · Casa matriz</option>{/each}
          </select>
        </label>
        <p class="mt-2 max-w-3xl text-xs text-foreground-muted">La casa matriz recibe las cantidades del plan central. Las cantidades solicitadas por las sucursales conservan su destino; el traslado desde la matriz a cada tienda se registra después.</p>
        {#if centralDestinationRepairMessage}<p class="mt-2 max-w-3xl text-xs text-warning" role="status">{centralDestinationRepairMessage}</p>{/if}
        {#if centralWarehouseId && !selectedCentralWarehouseIsValid}
          <p class="mt-2 text-xs text-danger" role="alert">El destino guardado ({item.central_warehouse_name ?? legacyCentralWarehouse?.name ?? 'bodega seleccionada'}) no está disponible como bodega madre activa. Cámbialo aquí antes de guardar el plan central.</p>
        {/if}
        {#if warehousesError}
          <div class="mt-2 flex flex-wrap items-center gap-2 text-xs text-danger" role="alert"><span>No se pudo cargar la lista de bodegas: {warehousesError}</span><button type="button" class="text-primary underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary" onclick={loadWarehouses}>Reintentar</button></div>
        {:else if warehousesLoading}
          <p class="mt-2 text-xs text-foreground-muted" role="status">Cargando bodegas…</p>
        {:else if centralWarehouses.length === 0}
          <p class="mt-2 text-xs text-warning" role="status">No hay una bodega madre activa configurada. Abre <a class="underline" href="/warehouses">Almacenes</a> y marca la bodega de reserva central.</p>
        {:else if warehouses.length === 0}
          <p class="mt-2 text-xs text-foreground-muted" role="status">No hay bodegas activas disponibles para tu ámbito.</p>
        {/if}
      </Card>
    {/if}

    {#if permissions.hasPermission('inventory:read')}
      <PurchaseConsolidationInventoryPanel
        lines={item.lines}
        snapshot={inventorySnapshot}
        warehouseId={centralWarehouseId}
        savedWarehouseId={originalCentralWarehouseId}
        warehouseName={item.central_warehouse_name}
        loading={inventorySnapshotLoading}
        onRefresh={loadInventorySnapshot}
      />
    {/if}

    <Card class="mb-4 overflow-hidden p-0">
      <div class="border-b border-border p-4"><h2 class="font-semibold text-foreground">Demanda por producto</h2><p class="mt-1 text-xs text-foreground-muted">Cada cantidad mantiene la solicitud, sucursal, almacén y valor original. El nivel manual se comparte entre todas las solicitudes del mismo producto y sucursal; no expresa prioridad ni cambia cantidades.</p></div>
      {#if item.lines.length === 0}
        <p class="px-4 py-10 text-center text-sm text-foreground-muted">Este borrador aún no tiene líneas.</p>
      {:else}
        <div class="hidden overflow-x-auto xl:block">
          <table class="w-full min-w-[1100px] text-sm">
            <thead class="bg-surface-muted text-xs text-foreground-muted"><tr><th scope="col" class="px-4 py-3 text-left">Producto</th><th scope="col" class="px-4 py-3 text-left">Unidad</th><th scope="col" class="px-4 py-3 text-right">Solicitado</th><th scope="col" class="px-4 py-3 text-right">Incluido</th><th scope="col" class="px-4 py-3 text-right">Plan central</th><th scope="col" class="px-4 py-3 text-right">Total</th><th scope="col" class="px-4 py-3 text-left">Fuentes</th></tr></thead>
            <tbody class="divide-y divide-border">
              {#each item.lines as line (line.id)}
                {@const centralDraft = centralDrafts[line.id]}
                <tr class="align-top hover:bg-surface-muted/50">
                  <td class="px-4 py-3"><p class="font-medium text-foreground">{line.product_name}</p><p class="mt-0.5 font-mono text-xs text-foreground-muted">{line.product_sku}</p></td>
                  <td class="px-4 py-3 text-foreground-muted">{line.unit_name}</td>
                  <td class="px-4 py-3 text-right font-mono">{formatQuantity(line.sources.reduce((sum, source) => sum + Number(source.requested_quantity), 0))}</td>
                  <td class="px-4 py-3 text-right">
                    <div class="space-y-2">
                      {#each line.sources as source (source.id)}
                        {@const draft = sourceDrafts[source.id]}
                        {@const demandGroup = branchDemandGroups.get(branchDemandKey(line.product_id, source.branch_id))}
                        <div class="min-w-48 rounded-md border border-border p-2 text-left">
                          <div class="flex items-center justify-between gap-2 text-xs">
                            <a href={`/purchase-requests/${source.purchase_request_id}`} class="font-mono text-primary hover:underline">{source.request_code}</a>
                            <span class="flex items-center gap-2 text-foreground-muted">
                              Solicitado originalmente: {formatQuantity(source.requested_quantity)}
                              {#if draft && item.status === 'draft'}
                                <button type="button" class="font-medium text-danger hover:underline" onclick={() => draft.includedQuantity = '0'}>Excluir</button>
                              {/if}
                            </span>
                          </div>
                          {#if draft}
                            <input aria-label={`Cantidad incluida ${line.product_name} ${source.request_code}`} type="number" min="0" max={source.requested_quantity} step="0.000001" bind:value={draft.includedQuantity} disabled={item.status !== 'draft'} class="mt-2 h-8 w-full rounded border border-border bg-surface px-2 text-right font-mono text-xs text-foreground disabled:opacity-60" />
                            <input aria-label={`Motivo del ajuste ${source.request_code}`} aria-required={valueChanged(draft.includedQuantity, draft.originalQuantity)} bind:value={draft.reason} disabled={item.status !== 'draft'} placeholder="Obligatorio al cambiar cantidad" class="mt-2 h-8 w-full rounded border border-border bg-surface px-2 text-xs text-foreground placeholder:text-foreground-muted disabled:opacity-60" />
                            {#if demandGroup && demandGroup.sourceIds[0] === source.id}
                              <label class="mt-2 block text-[11px] text-foreground-muted">Nivel de demanda · {source.branch_name ?? 'Sucursal'}
                                <span class="mt-1 block">Se comparte entre {demandGroup.requestCount} {demandGroup.requestCount === 1 ? 'solicitud' : 'solicitudes'} de esta sucursal para este producto.</span>
                                <select aria-label={`Nivel de demanda ${line.product_name} ${source.branch_name ?? 'sucursal'}`} value={draft.demandLevel} onchange={(event) => setDemandLevel(line.product_id, source.branch_id, event.currentTarget.value as BranchDemandLevel | '')} disabled={item.status !== 'draft'} class="mt-1 h-8 w-full rounded border border-border bg-surface px-2 text-xs text-foreground disabled:opacity-60">
                                  <option value="">Sin clasificar</option>
                                  <option value="low">Demanda baja</option>
                                  <option value="medium">Demanda media</option>
                                  <option value="high">Demanda alta</option>
                                </select>
                              </label>
                            {:else if demandGroup}
                              <p class="mt-2 text-[11px] text-foreground-muted">Nivel compartido para esta sucursal y producto: {demandLevelLabel(sourceDrafts[demandGroup.sourceIds[0] ?? '']?.demandLevel ?? '')}</p>
                            {/if}
                          {:else}
                            <p class="mt-2 text-xs text-foreground-muted">Cargando línea…</p>
                          {/if}
                          <p class="mt-1 text-[11px] text-foreground-muted">{source.branch_name ?? 'Sucursal'} · {source.warehouse_name ?? 'Almacén'} · Solicitó {source.requester_name ?? '—'} · Requerida {formatDate(source.required_date)}</p>
                        </div>
                      {/each}
                      {#if line.sources.length === 0}<span class="text-xs text-foreground-muted">Demanda central</span>{/if}
                    </div>
                  </td>
                  <td class="px-4 py-3 text-right">
                    {#if centralDraft}
                      <input aria-label={`Cantidad central ${line.product_name}`} type="number" min="0" step="0.000001" bind:value={centralDraft.quantity} oninput={clearResolvedCentralDestinationError} disabled={item.status !== 'draft'} class="h-8 w-28 rounded border border-border bg-surface px-2 text-right font-mono text-xs text-foreground disabled:opacity-60" />
                      {#if valueChanged(centralDraft.quantity, centralDraft.originalQuantity)}
                        <input aria-label={`Motivo de cantidad central ${line.product_name}`} aria-required="true" bind:value={centralDraft.reason} placeholder="Obligatorio al cambiar cantidad" disabled={item.status !== 'draft'} class="mt-2 h-8 w-36 rounded border border-border bg-surface px-2 text-xs text-foreground placeholder:text-foreground-muted disabled:opacity-60" />
                      {:else if Number(line.central_quantity) > 0}
                        <p class="mt-1 max-w-36 text-left text-[11px] text-foreground-muted">{line.central_reason}</p>
                      {/if}
                    {:else}
                      <span class="text-xs text-foreground-muted">—</span>
                    {/if}
                  </td>
                  <td class="px-4 py-3 text-right font-mono font-semibold text-foreground">{formatQuantity(line.sources.reduce((sum, source) => sum + Number(sourceDrafts[source.id]?.includedQuantity ?? source.included_quantity), 0) + Number(centralDrafts[line.id]?.quantity ?? line.central_quantity))}</td>
                  <td class="px-4 py-3 text-xs text-foreground-muted">{line.sources.length} solicitud(es)</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
        <ul class="divide-y divide-border xl:hidden">
          {#each item.lines as line (line.id)}
            {@const centralDraft = centralDrafts[line.id]}
            {@const includedTotal = line.sources.reduce((sum, source) => sum + Number(sourceDrafts[source.id]?.includedQuantity ?? source.included_quantity), 0)}
            <li class="space-y-3 p-4">
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0"><h3 class="break-words text-sm font-semibold text-foreground">{line.product_name}</h3><p class="mt-1 font-mono text-xs text-foreground-muted">{line.product_sku} · {line.unit_name}</p></div>
                <div class="shrink-0 text-right"><p class="text-[11px] text-foreground-muted">Total consolidado</p><p class="font-mono text-sm font-semibold text-primary">{formatQuantity(includedTotal + Number(centralDraft?.quantity ?? line.central_quantity))}</p></div>
              </div>
              <dl class="grid grid-cols-2 gap-x-3 gap-y-2 rounded-lg bg-surface-muted p-3 text-xs">
                <div><dt class="text-foreground-muted">Solicitado</dt><dd class="mt-0.5 font-mono text-foreground">{formatQuantity(line.sources.reduce((sum, source) => sum + Number(source.requested_quantity), 0))} {line.unit_name}</dd></div>
                <div><dt class="text-foreground-muted">Incluido</dt><dd class="mt-0.5 font-mono text-foreground">{formatQuantity(includedTotal)} {line.unit_name}</dd></div>
              </dl>
              {#if line.sources.length > 0}
                <div>
                  <p class="mb-2 text-xs font-medium text-foreground-muted">Solicitudes de origen</p>
                  <ul class="space-y-2">
                    {#each line.sources as source (source.id)}
                      {@const draft = sourceDrafts[source.id]}
                      {@const demandGroup = branchDemandGroups.get(branchDemandKey(line.product_id, source.branch_id))}
                      <li class="rounded-lg border border-border p-3">
                        <div class="flex flex-wrap items-start justify-between gap-2">
                          <div><a href={`/purchase-requests/${source.purchase_request_id}`} class="font-mono text-xs font-medium text-primary hover:underline">{source.request_code}</a><p class="mt-1 text-xs text-foreground-muted">{source.branch_name ?? 'Sucursal'} · {source.warehouse_name ?? 'Almacén'}</p><p class="mt-1 text-xs text-foreground-muted">Solicitó {source.requester_name ?? '—'} · Requerida {formatDate(source.required_date)}</p></div>
                          <span class="text-xs text-foreground-muted">Solicitado: {formatQuantity(source.requested_quantity)} {line.unit_name}</span>
                        </div>
                        {#if draft}
                          <label class="consolidation-field-label mt-3">Cantidad incluida
                            <input type="number" min="0" max={source.requested_quantity} step="0.000001" bind:value={draft.includedQuantity} disabled={item.status !== 'draft'} class="consolidation-field-control text-right font-mono disabled:opacity-60" />
                          </label>
                          {#if demandGroup && demandGroup.sourceIds[0] === source.id}
                            <label class="consolidation-field-label mt-2">Nivel de demanda · {source.branch_name ?? 'Sucursal'}
                              <span class="text-xs font-normal text-foreground-muted">Se comparte entre {demandGroup.requestCount} {demandGroup.requestCount === 1 ? 'solicitud' : 'solicitudes'} de esta sucursal para este producto.</span>
                              <select aria-label={`Nivel de demanda ${line.product_name} ${source.branch_name ?? 'sucursal'}`} value={draft.demandLevel} onchange={(event) => setDemandLevel(line.product_id, source.branch_id, event.currentTarget.value as BranchDemandLevel | '')} disabled={item.status !== 'draft'} class="consolidation-field-control disabled:opacity-60">
                                <option value="">Sin clasificar</option>
                                <option value="low">Demanda baja</option>
                                <option value="medium">Demanda media</option>
                                <option value="high">Demanda alta</option>
                              </select>
                            </label>
                          {:else if demandGroup}
                            <p class="mt-3 text-xs text-foreground-muted">Nivel compartido para esta sucursal y producto: {demandLevelLabel(sourceDrafts[demandGroup.sourceIds[0] ?? '']?.demandLevel ?? '')}</p>
                          {/if}
                          {#if valueChanged(draft.includedQuantity, draft.originalQuantity)}
                            <label class="consolidation-field-label mt-2">Motivo del ajuste <span class="text-danger">*</span>
                              <input aria-required="true" bind:value={draft.reason} disabled={item.status !== 'draft'} placeholder="Obligatorio al cambiar cantidad" class="consolidation-field-control disabled:opacity-60" />
                            </label>
                          {/if}
                          {#if item.status === 'draft'}
                            <button type="button" class="mt-2 min-h-10 rounded px-2 text-xs font-medium text-danger hover:bg-danger/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger" onclick={() => draft.includedQuantity = '0'}>Excluir esta solicitud</button>
                          {/if}
                        {/if}
                      </li>
                    {/each}
                  </ul>
                </div>
              {:else}
                <p class="text-xs text-foreground-muted">Demanda exclusiva para la bodega central.</p>
              {/if}
              {#if centralDraft}
                <div class="border-t border-border pt-3">
                  <label class="consolidation-field-label">Plan de bodega central ({line.unit_name})
                    <input aria-label={`Cantidad central ${line.product_name}`} type="number" min="0" step="0.000001" bind:value={centralDraft.quantity} oninput={clearResolvedCentralDestinationError} disabled={item.status !== 'draft'} class="consolidation-field-control text-right font-mono disabled:opacity-60" />
                  </label>
                  {#if valueChanged(centralDraft.quantity, centralDraft.originalQuantity)}
                    <label class="consolidation-field-label mt-2">Motivo del cambio <span class="text-danger">*</span>
                      <input aria-label={`Motivo de cantidad central ${line.product_name}`} aria-required="true" bind:value={centralDraft.reason} placeholder="Obligatorio al cambiar cantidad" disabled={item.status !== 'draft'} class="consolidation-field-control disabled:opacity-60" />
                    </label>
                  {:else if Number(line.central_quantity) > 0}
                    <p class="mt-1 text-xs text-foreground-muted">Motivo registrado: {line.central_reason}</p>
                  {/if}
                </div>
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
      <div class="border-t border-border p-4">
        <label class="consolidation-field-label">Notas del consolidado<textarea rows="2" bind:value={notesDraft} disabled={item.status !== 'draft'} class="consolidation-field-control h-auto py-2"></textarea></label>
      </div>
    </Card>

    {#if item.status === 'draft' && permissions.hasPermission('purchase_requests:manage')}
      <Card class="mb-4 p-4">
        <h2 class="font-semibold text-foreground">Agregar demanda central</h2>
        <p class="mt-1 text-xs text-foreground-muted" data-testid="central-demand-destination-note">
          Demanda central opcional e independiente de las solicitudes de sucursal.
          {#if selectedCentralWarehouseName}
            Si la agregas, quedará planeada para {selectedCentralWarehouseName}; no registra existencias ni genera traslados automáticamente.
          {:else}
            Elige primero una bodega madre arriba. Agregarla no registra existencias ni genera traslados automáticamente.
          {/if}
        </p>
        <p class="mt-1 text-xs text-foreground-muted">Elige un producto de la lista o escribe su nombre o SKU. Solo aparecen productos activos habilitados para compra.</p>
        <div class="mt-4 min-w-0">
          {#if centralCatalogLoading && centralCatalogPage === 0}
            <div class="rounded-md border border-border bg-surface-muted px-3 py-4 text-sm text-foreground-muted" role="status" aria-busy="true">Cargando productos habilitados para compra…</div>
          {:else if centralCatalogError && centralCatalogPage === 0}
            <div class="flex flex-wrap items-center justify-between gap-3 rounded-md border border-danger/30 bg-danger/10 px-3 py-3 text-sm text-foreground" role="alert">
              <span>No se pudo cargar el catálogo: {centralCatalogError}</span>
              <Button size="sm" variant="secondary" onclick={() => void loadCentralCatalogPage(1)}>Reintentar</Button>
            </div>
          {:else}
            <PurchaseRequestProductPicker
              id="central-demand-product"
              label="Producto para agregar"
              bind:value={selectedProductId}
              bind:query={searchProduct}
              products={centralCatalogProducts}
              hasMoreProducts={centralCatalogPage < centralCatalogPages}
              loadingMoreProducts={centralCatalogLoading}
              loadMoreError={centralCatalogError}
              onloadmore={() => void loadCentralCatalogPage()}
              onselect={(product) => {
                selectedCentralProduct = product;
                error = null;
              }}
            />
          {/if}
        </div>
        <div class="mt-4 grid grid-cols-1 items-end gap-3 sm:grid-cols-[minmax(9rem,0.35fr)_minmax(14rem,1fr)_auto]">
          <label class="consolidation-field-label">Cantidad
            <input aria-label="Cantidad de demanda central" type="number" min="0.000001" step="0.000001" bind:value={centralQuantity} class="consolidation-field-control" />
          </label>
          <label class="consolidation-field-label">Motivo u objetivo
            <input aria-label="Motivo de demanda central" bind:value={centralReason} placeholder="Ej. reposición para bodega" class="consolidation-field-control" />
          </label>
          <div class="flex flex-wrap items-center justify-end gap-2">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onclick={cancelCentralDemandEntry}
            >
              Cancelar
            </Button>
        <Button class="w-full sm:w-auto" size="sm" disabled={!centralWarehouseId || !selectedCentralWarehouseIsValid} onclick={queueCentralDemand}>Agregar demanda</Button>
          </div>
        </div>
        {#if newCentralDemands.length > 0}<ul class="mt-3 divide-y divide-border rounded-lg border border-border">{#each newCentralDemands as demand, index}<li class="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm"><span><span class="font-mono text-xs text-foreground-muted">{demand.sku}</span> · {demand.name} · {formatQuantity(demand.quantity)} · <span class="text-foreground-muted">{demand.reason}</span></span><button type="button" class="text-xs text-danger hover:underline" onclick={() => newCentralDemands = newCentralDemands.filter((_, itemIndex) => itemIndex !== index)}>Quitar</button></li>{/each}</ul>{/if}
        {#if !centralWarehouseId}<p class="mt-2 text-xs text-foreground-muted" role="status">Para agregar una cantidad aquí, primero elige una bodega madre arriba. Si no necesitas demanda central, deja el formulario vacío.</p>{/if}
      </Card>

      <Card class="mb-4 overflow-hidden p-0">
        <details ontoggle={(event) => (event.currentTarget as HTMLDetailsElement).open && candidates.length === 0 && void loadEligibleRequests()}>
          <summary class="cursor-pointer list-none px-4 py-4"><span class="font-semibold text-foreground">Agregar solicitudes aprobadas</span><span class="ml-2 text-xs text-foreground-muted">Se conserva su solicitud y cantidad original.</span></summary>
          <div class="border-t border-border p-4">
            <div class="grid grid-cols-1 gap-3 sm:grid-cols-4">
              <label class="consolidation-field-label">Desde<input type="date" bind:value={sourceDateFrom} class="consolidation-field-control" /></label>
              <label class="consolidation-field-label">Hasta<input type="date" bind:value={sourceDateTo} class="consolidation-field-control" /></label>
              <label class="consolidation-field-label">Sucursal
                <select bind:value={sourceBranchId} class="consolidation-field-control">{#if branch.accessAllBranches}<option value="">Todas las sucursales</option>{/if}{#each branch.branches as option (option.id)}<option value={option.id}>{option.name}</option>{/each}</select>
              </label>
              <div class="flex items-end"><Button size="sm" variant="secondary" onclick={loadEligibleRequests}>Buscar aprobadas</Button></div>
            </div>
            {#if loadingCandidates}<p class="py-5 text-sm text-foreground-muted" role="status">Buscando solicitudes…</p>{:else if candidatesError}
              <div class="flex flex-wrap items-center justify-between gap-3 py-5 text-sm text-danger" role="alert"><span>No se pudieron buscar solicitudes: {candidatesError}</span><Button size="sm" variant="secondary" onclick={loadEligibleRequests}>Reintentar</Button></div>
            {:else if candidates.length === 0}<p class="py-5 text-sm text-foreground-muted">No hay solicitudes disponibles para agregar.</p>{:else}
              <div class="mt-3 max-h-64 overflow-auto rounded-lg border border-border">
                {#each candidates as candidate (candidate.id)}<label class="flex cursor-pointer items-center gap-3 border-b border-border px-3 py-2 last:border-0 hover:bg-surface-muted"><input type="checkbox" checked={selectedRequestIds.includes(candidate.id)} onchange={(event) => toggleRequest(candidate.id, (event.currentTarget as HTMLInputElement).checked)} class="h-4 w-4 accent-primary"/><span class="min-w-0 flex-1"><span class="font-mono text-xs text-primary">{candidate.code}</span><span class="ml-3 text-sm text-foreground">{candidate.branch_name ?? 'Sucursal'} · {candidate.warehouse_name ?? 'Almacén'}</span></span><span class="text-xs text-foreground-muted">{candidate.line_count} líneas</span></label>{/each}
              </div>
              <div class="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_auto]"><input aria-label="Motivo de agregar solicitudes" bind:value={newSourceReason} placeholder="Motivo para agregarlas" class="consolidation-field-control"/><Button size="sm" disabled={saving || selectedRequestIds.length === 0} onclick={addRequests}>Agregar seleccionadas ({selectedRequestIds.length})</Button></div>
            {/if}
          </div>
        </details>
      </Card>

      <Card class="mb-4 p-4">
        <label class="consolidation-field-label">Motivo general de los cambios <span class="text-danger">*</span><input aria-label="Motivo general de los cambios" aria-required="true" bind:value={changeReason} placeholder="Ej. ajuste tras revisar inventario y pedidos en camino" class="consolidation-field-control" /></label>
      </Card>
      <div class="mb-6 flex flex-wrap items-center justify-between gap-3">
        <Button variant="danger" onclick={() => showCancelForm = !showCancelForm}>Cancelar borrador</Button>
        <Button disabled={saving} onclick={save}>{saving ? 'Guardando…' : 'Guardar cambios'}</Button>
      </div>
      {#if showCancelForm}<Card class="mb-6 border border-danger/30 p-4"><div class="flex flex-wrap items-end gap-3"><label class="consolidation-field-label min-w-64 flex-1">Motivo de cancelación<input bind:value={cancelReason} class="consolidation-field-control" /></label><Button size="sm" variant="danger" disabled={saving} onclick={cancelDraft}>Confirmar cancelación</Button></div></Card>{/if}
    {/if}

    <PurchaseConsolidationHistory events={item.events} />
  {/if}
</div>

<style>
  :global(.purchase-consolidation-detail .hover-lift) { transition: none; }
  :global(.purchase-consolidation-detail .hover-lift:hover) { transform: none; box-shadow: var(--shadow-md); }
</style>
