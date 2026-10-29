<script lang="ts">
  import '../consolidation-fields.css';
  import { goto } from '$app/navigation';
  import { page as currentPage } from '$app/state';
  import { onMount } from 'svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import PurchaseFlowRibbon from './PurchaseFlowRibbon.svelte';
  import { api, HttpError } from '$lib/api/client';
  import { purchaseConsolidationsApi } from '$lib/api/purchase-consolidations';
  import { branch } from '$lib/stores/branch.svelte';
  import type {
    ApprovedRequestCandidate,
    BranchDemandLevel,
    SelectedPurchaseRequestResolution
  } from '$lib/types/purchase-consolidation';
  import type { WarehouseOut } from '$lib/api/client';

  function todayInput() {
    const d = new Date();
    return new Date(d.getTime() - d.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
  }
  function daysAgoInput(days: number) {
    const d = new Date();
    d.setDate(d.getDate() - days);
    return new Date(d.getTime() - d.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
  }

  let periodStart = $state(currentPage.url.searchParams.get('date_from') || daysAgoInput(29));
  let periodEnd = $state(currentPage.url.searchParams.get('date_to') || todayInput());
  let branchId = $state(branch.id ?? '');
  let warehouseId = $state('');
  let centralWarehouseId = $state('');
  let centralWarehouseInitialized = false;
  let search = $state('');
  let notes = $state('');
  let candidates = $state<ApprovedRequestCandidate[]>([]);
  let demandLevels = $state<Record<string, BranchDemandLevel | ''>>({});
  let selectedCandidatesById = $state<Record<string, {
    candidate: ApprovedRequestCandidate;
    countPeriodStart: string;
    countPeriodEnd: string;
  }>>({});
  let selectedRequestResolutionsById = $state<Record<string, SelectedPurchaseRequestResolution>>({});
  let warehouses = $state<WarehouseOut[]>([]);
  let centralWarehouses = $derived(
    warehouses.filter(
      (item) => item.is_central && item.status === 'active'
    )
  );
  let warehousesLoading = $state(false);
  let warehousesError = $state<string | null>(null);
  let selectedIds = $state((currentPage.url.searchParams.get('request_ids') || '').split(',').filter(Boolean));
  let failedSelectedCandidateIds = $state<string[]>([]);
  let loading = $state(false);
  let submitting = $state(false);
  let error = $state<string | null>(null);
  let candidatesError = $state<string | null>(null);
  let selectedCandidatesError = $state<string | null>(null);
  let requestGeneration = 0;
  let warehouseGeneration = 0;
  let selectedIdsWithoutDetails = $derived(selectedIds.filter((requestId) => !selectedCandidatesById[requestId]));
  let selectedIdsOutsidePeriod = $derived(selectedIds.filter((requestId) => {
    const candidate = selectedCandidatesById[requestId]?.candidate;
    if (!candidate) return false;
    const requestDate = localDateInput(candidate.request_date);
    return requestDate < periodStart || requestDate > periodEnd;
  }));

  let selectedDemandGroups = $derived.by(() => {
    const groups = new Map<string, {
      key: string;
      branchId: string;
      branchName: string;
      productId: number;
      productSku: string;
      productName: string;
      requestCount: number | null;
    }>();
    for (const requestId of selectedIds) {
      const snapshot = selectedCandidatesById[requestId];
      if (!snapshot) continue;
      const candidate = snapshot.candidate;
      for (const detail of candidate.details) {
        const key = `${candidate.branch_id}:${detail.product_id}`;
        const existing = groups.get(key);
        const requestCount = snapshot.countPeriodStart === periodStart && snapshot.countPeriodEnd === periodEnd
          ? (detail.request_count ?? null)
          : null;
        if (existing) {
          if (existing.requestCount === null && requestCount !== null) existing.requestCount = requestCount;
          continue;
        }
        groups.set(key, {
          key,
          branchId: candidate.branch_id,
          branchName: candidate.branch_name ?? 'Sucursal sin nombre',
          productId: detail.product_id,
          productSku: detail.product_sku ?? `PRD-${detail.product_id}`,
          productName: detail.product_name ?? `Producto ${detail.product_id}`,
          requestCount
        });
      }
    }
    return [...groups.values()].sort((a, b) =>
      a.branchName.localeCompare(b.branchName, 'es') || a.productName.localeCompare(b.productName, 'es')
    );
  });

  function errorMessage(err: unknown, fallback: string) {
    return err instanceof HttpError ? err.message : err instanceof Error ? err.message : fallback;
  }

  async function hydrateSelectedChunk(requestIds: string[], dateFrom: string, dateTo: string): Promise<{
    items: ApprovedRequestCandidate[];
    resolutions: SelectedPurchaseRequestResolution[];
    unavailableIds: string[];
    failedIds: string[];
    errorMessage: string | null;
  }> {
    try {
      const page = await purchaseConsolidationsApi.eligibleRequests({
        date_from: dateFrom,
        date_to: dateTo,
        request_ids: requestIds,
        page: 1,
        size: 100
      });
      const foundIds = new Set(page.items.map((candidate) => candidate.id));
      let resolutions: SelectedPurchaseRequestResolution[];
      try {
        resolutions = await purchaseConsolidationsApi.resolveSelectedRequests(requestIds);
      } catch (err: unknown) {
        if (err instanceof HttpError && err.status === 403 && requestIds.length > 1) {
          // Resolve mixed-access selections individually so an inaccessible ID
          // cannot hide diagnostics for requests the user is allowed to see.
          const midpoint = Math.ceil(requestIds.length / 2);
          const [left, right] = await Promise.all([
            hydrateSelectedChunk(requestIds.slice(0, midpoint), dateFrom, dateTo),
            hydrateSelectedChunk(requestIds.slice(midpoint), dateFrom, dateTo)
          ]);
          return {
            items: [...left.items, ...right.items],
            resolutions: [...left.resolutions, ...right.resolutions],
            unavailableIds: [...left.unavailableIds, ...right.unavailableIds],
            failedIds: [...left.failedIds, ...right.failedIds],
            errorMessage: left.errorMessage ?? right.errorMessage
          };
        }
        if (err instanceof HttpError && err.status === 403) {
          return {
            items: page.items,
            resolutions: [],
            unavailableIds: requestIds.filter((requestId) => !foundIds.has(requestId)),
            failedIds: [],
            errorMessage: null
          };
        }
        const loadedCandidates = page.items.map((candidate) => candidate.id);
        return {
          items: page.items,
          resolutions: page.items.map((candidate) => ({
            id: candidate.id,
            code: candidate.code,
            eligibility: 'eligible',
            consolidations: []
          })),
          unavailableIds: [],
          failedIds: requestIds.filter((requestId) => !loadedCandidates.includes(requestId)),
          errorMessage: errorMessage(err, 'No se pudo actualizar el estado de algunas solicitudes.')
        };
      }
      const resolvedIds = new Set(resolutions.map((resolution) => resolution.id));
      return {
        items: page.items,
        resolutions,
        unavailableIds: requestIds.filter((requestId) => !foundIds.has(requestId) && !resolvedIds.has(requestId)),
        failedIds: [],
        errorMessage: null
      };
    } catch (err: unknown) {
      if (err instanceof HttpError && err.status === 403 && requestIds.length > 1) {
        // Split a mixed batch so one out-of-scope request cannot hide valid selected requests.
        const midpoint = Math.ceil(requestIds.length / 2);
        const [left, right] = await Promise.all([
          hydrateSelectedChunk(requestIds.slice(0, midpoint), dateFrom, dateTo),
          hydrateSelectedChunk(requestIds.slice(midpoint), dateFrom, dateTo)
        ]);
        return {
          items: [...left.items, ...right.items],
          resolutions: [...left.resolutions, ...right.resolutions],
          unavailableIds: [...left.unavailableIds, ...right.unavailableIds],
          failedIds: [...left.failedIds, ...right.failedIds],
          errorMessage: left.errorMessage ?? right.errorMessage
        };
      }

      if (err instanceof HttpError && err.status === 403) {
        return { items: [], resolutions: [], unavailableIds: requestIds, failedIds: [], errorMessage: null };
      }
      return {
        items: [],
        resolutions: [],
        unavailableIds: [],
        failedIds: requestIds,
        errorMessage: errorMessage(err, 'No se pudo actualizar el detalle de algunas solicitudes.')
      };
    }
  }

  async function loadWarehouses() {
    const generation = ++warehouseGeneration;
    warehousesLoading = true;
    warehousesError = null;
    try {
      const result = await api.warehouses.catalogue({
        branch_id: branch.accessAllBranches ? '' : branchId,
        include_company_central: true
      });
      if (generation === warehouseGeneration) {
        warehouses = result;
        if (!centralWarehouseInitialized) {
          const mother = result.filter(
            (item) => item.is_central && item.status === 'active'
          );
          const onlyMother = mother.length === 1 ? mother[0] : undefined;
          if (onlyMother) centralWarehouseId = onlyMother.id;
          centralWarehouseInitialized = true;
        }
      }
    } catch (err: unknown) {
      if (generation === warehouseGeneration) {
        warehouses = [];
        warehousesError = err instanceof HttpError ? err.message : err instanceof Error ? err.message : 'No se pudieron consultar las bodegas.';
      }
    } finally {
      if (generation === warehouseGeneration) warehousesLoading = false;
    }
  }

  async function loadCandidates() {
    const generation = ++requestGeneration;
    const queryDateFrom = periodStart;
    const queryDateTo = periodEnd;
    const selectedRequestIds = [...selectedIds];
    loading = true;
    candidatesError = null;
    selectedCandidatesError = null;
    try {
      const selectedChunks = Array.from(
        { length: Math.ceil(selectedRequestIds.length / 100) },
        (_, index) => selectedRequestIds.slice(index * 100, (index + 1) * 100)
      );
      const [responseResult, selectedResponses] = await Promise.all([
        purchaseConsolidationsApi.eligibleRequests({
          date_from: queryDateFrom,
          date_to: queryDateTo,
          branch_id: branchId || undefined,
          warehouse_id: warehouseId || undefined,
          q: search.trim() || undefined,
          page: 1,
          size: 100
        }).then((value) => ({ value })).catch((reason: unknown) => ({ reason })),
        Promise.all(selectedChunks.map((requestIds) => hydrateSelectedChunk(requestIds, queryDateFrom, queryDateTo)))
      ]);
      if (generation === requestGeneration) {
        if ('value' in responseResult) candidates = responseResult.value.items;
        else {
          candidatesError = errorMessage(responseResult.reason, 'No se pudieron consultar las solicitudes aprobadas.');
          candidates = [];
        }

        const unavailableIds = new Set(selectedResponses.flatMap((result) => result.unavailableIds));
        const failedIds = new Set(selectedResponses.flatMap((result) => result.failedIds));
        const resolved = new Map(
          selectedResponses.flatMap((result) => result.resolutions).map((resolution) => [resolution.id, resolution])
        );
        const refreshed = new Map([
          ...('value' in responseResult ? responseResult.value.items : []),
          ...selectedResponses.flatMap((result) => result.items)
        ].map((candidate) => [candidate.id, candidate]));
        const next = { ...selectedCandidatesById };
        const nextResolutions = { ...selectedRequestResolutionsById };
        for (const requestId of selectedRequestIds) {
          const candidate = refreshed.get(requestId);
          const resolution = resolved.get(requestId);
          if (resolution) nextResolutions[requestId] = resolution;
          else if (unavailableIds.has(requestId)) delete nextResolutions[requestId];
          else if (!failedIds.has(requestId)) delete nextResolutions[requestId];

          if (candidate && (!resolution || resolution.eligibility === 'eligible')) {
            next[requestId] = { candidate, countPeriodStart: queryDateFrom, countPeriodEnd: queryDateTo };
          } else if (resolution && resolution.eligibility !== 'eligible') {
            delete next[requestId];
          } else if (unavailableIds.has(requestId)) delete next[requestId];
          else if (!failedIds.has(requestId) && !candidate) delete next[requestId];
        }
        selectedCandidatesById = next;
        selectedRequestResolutionsById = nextResolutions;
        failedSelectedCandidateIds = [...failedIds];
        const hydrationFailure = selectedResponses.find((result) => result.errorMessage)?.errorMessage;
        if (hydrationFailure) {
          selectedCandidatesError = 'No se pudo actualizar el detalle de algunas solicitudes. Se conserva la información cargada anteriormente; intenta actualizar de nuevo.';
        }
      }
    } catch (err: unknown) {
      if (generation === requestGeneration) {
        // A hydration error must not erase the independently loaded candidate list.
        selectedCandidatesError = errorMessage(err, 'No se pudo actualizar el detalle de las solicitudes seleccionadas.');
        failedSelectedCandidateIds = selectedRequestIds.filter((requestId) => !selectedCandidatesById[requestId]);
      }
    } finally {
      if (generation === requestGeneration) loading = false;
    }
  }

  function toggleRequest(id: string, checked: boolean) {
    selectedIds = checked ? [...new Set([...selectedIds, id])] : selectedIds.filter((item) => item !== id);
    failedSelectedCandidateIds = failedSelectedCandidateIds.filter((item) => item !== id);
    const selectedCandidate = candidates.find((item) => item.id === id);
    if (checked && selectedCandidate) {
      selectedCandidatesById = {
        ...selectedCandidatesById,
        [id]: { candidate: selectedCandidate, countPeriodStart: periodStart, countPeriodEnd: periodEnd }
      };
      selectedRequestResolutionsById = {
        ...selectedRequestResolutionsById,
        [id]: { id, code: selectedCandidate.code, eligibility: 'eligible', consolidations: [] }
      };
    } else if (!checked) {
      const next = { ...selectedCandidatesById };
      delete next[id];
      selectedCandidatesById = next;
      const nextResolutions = { ...selectedRequestResolutionsById };
      delete nextResolutions[id];
      selectedRequestResolutionsById = nextResolutions;
    }
  }

  async function createConsolidation() {
    if (!canCreateConsolidation()) return;
    submitting = true;
    error = null;
    try {
      const created = await purchaseConsolidationsApi.create({
        request_ids: selectedIds,
        demand_levels: selectedDemandGroups.flatMap((group) => {
          const level = demandLevels[group.key];
          return level ? [{ branch_id: group.branchId, product_id: group.productId, level }] : [];
        }),
        period_start: periodStart,
        period_end: periodEnd,
        central_warehouse_id: centralWarehouseId || null,
        notes: notes.trim() || null
      });
      await goto(`/purchase-consolidations/${created.id}`);
    } catch (err: unknown) {
      error = err instanceof HttpError ? err.message : err instanceof Error ? err.message : 'No se pudo crear el borrador.';
      if (err instanceof HttpError && err.code === 'purchase_consolidation_request_already_linked') {
        await loadCandidates();
      }
    } finally {
      submitting = false;
    }
  }

  function formatDate(value: string | null) {
    if (!value) return '—';
    return new Intl.DateTimeFormat('es-SV', { timeZone: 'America/El_Salvador', day: '2-digit', month: '2-digit', year: 'numeric' }).format(new Date(value));
  }

  function localDateInput(value: string) {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/El_Salvador', year: 'numeric', month: '2-digit', day: '2-digit'
    }).formatToParts(new Date(value));
    const part = (type: Intl.DateTimeFormatPartTypes) => parts.find((item) => item.type === type)?.value ?? '';
    return `${part('year')}-${part('month')}-${part('day')}`;
  }

  function canCreateConsolidation() {
    return selectedIds.length > 0
      && selectedIds.length <= 100
      && selectedIdsWithoutDetails.length === 0
      && selectedIdsOutsidePeriod.length === 0
      && !submitting;
  }

  function consolidationStatusLabel(status: string) {
    if (status === 'draft') return 'Borrador';
    if (status === 'frozen') return 'Congelado';
    if (status === 'closed') return 'Cerrado';
    return status;
  }

  onMount(() => {
    void loadWarehouses();
    void loadCandidates();
  });
</script>

<div class="purchase-consolidation-create min-h-full bg-background px-4 pb-8 pt-4 sm:px-6 sm:pt-6 md:px-8 md:pt-8">
  <div class="mb-5 flex flex-wrap items-end justify-between gap-4">
    <div>
      <a href="/purchase-requests" class="text-sm text-primary hover:underline">← Solicitudes y consolidados</a>
      <h1 class="mt-2 text-xl font-semibold text-foreground">Nuevo consolidado · Borrador</h1>
      <p class="mt-1 text-sm text-foreground-muted">Agrupa solicitudes aprobadas sin cambiar sus cantidades originales.</p>
    </div>
  </div>

  <PurchaseFlowRibbon currentStep={2} />

  {#if error}<div class="mb-4 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert">{error}</div>{/if}

  <Card class="mb-4 p-4">
    <h2 class="text-sm font-semibold text-foreground">Período y destino</h2>
    <div class="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <label class="consolidation-field-label">Desde<input type="date" bind:value={periodStart} onchange={() => void loadCandidates()} class="consolidation-field-control" /></label>
      <label class="consolidation-field-label">Hasta<input type="date" bind:value={periodEnd} onchange={() => void loadCandidates()} class="consolidation-field-control" /></label>
      <label class="consolidation-field-label">Sucursal fuente
        <select bind:value={branchId} onchange={() => { warehouseId = ''; void loadWarehouses(); void loadCandidates(); }} class="consolidation-field-control">
          {#if branch.accessAllBranches}<option value="">Todas las sucursales</option>{/if}
          {#each branch.branches as item (item.id)}<option value={item.id}>{item.name}</option>{/each}
        </select>
      </label>
      <label class="consolidation-field-label">Almacén para filtrar
        <select bind:value={warehouseId} onchange={() => void loadCandidates()} disabled={warehousesLoading || warehousesError !== null} class="consolidation-field-control">
          <option value="">{warehousesLoading ? 'Cargando almacenes…' : 'Todos los almacenes'}</option>{#each warehouses as item (item.id)}<option value={item.id}>{item.name}</option>{/each}
        </select>
      </label>
      <label class="consolidation-field-label sm:col-span-2">Bodega central (opcional)
        <select bind:value={centralWarehouseId} disabled={warehousesLoading || warehousesError !== null || centralWarehouses.length === 0} class="consolidation-field-control">
        <option value="">Sin plan de bodega central</option>{#each centralWarehouses as item (item.id)}<option value={item.id}>{item.name} · Casa matriz</option>{/each}
        </select>
        <span class="text-xs font-normal text-foreground-muted">La bodega madre de la empresa queda seleccionada por defecto. El plan central queda en esa bodega; no crea una orden ni mueve existencias. La recepción y distribución se registran en sus pasos respectivos.</span>
      </label>
      <label class="consolidation-field-label sm:col-span-2">Notas del lote<textarea bind:value={notes} rows="2" class="consolidation-field-control"></textarea></label>
    </div>
    {#if warehousesError}
      <div class="mt-3 flex flex-wrap items-center gap-2 text-xs text-danger" role="alert">
        <span>No se pudo cargar la lista de bodegas: {warehousesError}</span>
        <button type="button" class="text-primary underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary" onclick={loadWarehouses}>Reintentar</button>
      </div>
    {:else if !warehousesLoading && warehouses.length === 0}
      <p class="mt-3 text-xs text-foreground-muted" role="status">No hay bodegas activas disponibles para este ámbito.</p>
    {:else if !warehousesLoading && centralWarehouses.length === 0}
      <p class="mt-3 text-xs text-warning" role="status">
        No hay una bodega madre configurada. Puedes consolidar solicitudes de sucursal; para añadir plan central, configura una bodega en <a class="underline" href="/warehouses">Almacenes</a> y márcala como bodega madre.
      </p>
    {/if}
  </Card>

  <Card class="overflow-hidden p-0">
    <div class="flex flex-col gap-3 border-b border-border p-4 sm:flex-row sm:items-center sm:justify-between">
      <div><h2 class="text-sm font-semibold text-foreground">Solicitudes aprobadas disponibles</h2><p class="mt-1 text-xs text-foreground-muted">Solo se agregan al borrador; no se cambia el estado de las solicitudes.</p></div>
      <div class="flex flex-wrap gap-2">
        <input aria-label="Buscar solicitudes aprobadas" bind:value={search} onkeydown={(event) => event.key === 'Enter' && loadCandidates()} placeholder="Buscar por código o justificación" class="consolidation-field-control !w-64" />
        <Button size="sm" variant="secondary" onclick={() => void loadCandidates()}>Buscar</Button>
      </div>
    </div>
    {#if loading}
      <div class="space-y-3 p-4" role="status" aria-label="Cargando solicitudes">{#each Array(4) as _}<div class="skeleton h-12 w-full rounded-md"></div>{/each}</div>
    {:else if candidatesError}
      <div class="flex flex-wrap items-center justify-between gap-3 px-4 py-8 text-sm text-danger" role="alert">
        <span>No se pudieron cargar las solicitudes: {candidatesError}</span>
        <Button size="sm" variant="secondary" onclick={() => void loadCandidates()}>Reintentar</Button>
      </div>
    {:else if candidates.length === 0}
      <div class="px-6 py-12 text-center text-sm text-foreground-muted">No hay solicitudes aprobadas disponibles en esos filtros.</div>
    {:else}
      <div class="hidden overflow-x-auto lg:block">
        <table class="w-full min-w-[800px] text-sm">
          <thead class="bg-surface-muted text-xs text-foreground-muted"><tr><th scope="col" class="w-12 px-4 py-3"><span class="sr-only">Seleccionar</span></th><th scope="col" class="px-4 py-3 text-left">Código</th><th scope="col" class="px-4 py-3 text-left">Sucursal</th><th scope="col" class="px-4 py-3 text-left">Almacén</th><th scope="col" class="px-4 py-3 text-left">Solicitante</th><th scope="col" class="px-4 py-3 text-left">Requerida</th><th scope="col" class="px-4 py-3 text-left">Fecha</th><th scope="col" class="px-4 py-3 text-right">Líneas</th></tr></thead>
          <tbody class="divide-y divide-border">
            {#each candidates as item (item.id)}
              <tr class="hover:bg-surface-muted">
                <td class="px-4 py-3"><input type="checkbox" aria-label={`Seleccionar ${item.code}`} checked={selectedIds.includes(item.id)} onchange={(event) => toggleRequest(item.id, (event.currentTarget as HTMLInputElement).checked)} class="h-4 w-4 accent-primary" /></td>
                <td class="px-4 py-3 font-mono text-xs font-medium text-foreground">{item.code}</td>
                <td class="px-4 py-3 text-foreground-muted">{item.branch_name ?? '—'}</td>
                <td class="px-4 py-3 text-foreground-muted">{item.warehouse_name ?? '—'}</td>
                <td class="px-4 py-3 text-foreground-muted">{item.requester_name ?? '—'}</td>
                <td class="px-4 py-3 text-foreground-muted">{formatDate(item.required_date)}</td>
                <td class="px-4 py-3 text-foreground-muted">{formatDate(item.request_date)}</td>
                <td class="px-4 py-3 text-right font-mono">{item.line_count}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <ul class="divide-y divide-border lg:hidden">
        {#each candidates as item (item.id)}
          <li class="flex items-start gap-3 p-4">
            <input type="checkbox" aria-label={`Seleccionar ${item.code}`} checked={selectedIds.includes(item.id)} onchange={(event) => toggleRequest(item.id, (event.currentTarget as HTMLInputElement).checked)} class="mt-1 h-5 w-5 rounded accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary" />
            <div class="min-w-0 flex-1">
              <p class="font-mono text-sm font-semibold text-primary">{item.code}</p>
              <dl class="mt-2 grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
                <div><dt class="text-foreground-muted">Sucursal</dt><dd class="mt-0.5 break-words text-foreground">{item.branch_name ?? '—'}</dd></div>
                <div><dt class="text-foreground-muted">Almacén</dt><dd class="mt-0.5 break-words text-foreground">{item.warehouse_name ?? '—'}</dd></div>
                <div><dt class="text-foreground-muted">Solicitante</dt><dd class="mt-0.5 break-words text-foreground">{item.requester_name ?? '—'}</dd></div>
                <div><dt class="text-foreground-muted">Fecha requerida</dt><dd class="mt-0.5 text-foreground">{formatDate(item.required_date)}</dd></div>
                <div><dt class="text-foreground-muted">Fecha</dt><dd class="mt-0.5 text-foreground">{formatDate(item.request_date)}</dd></div>
                <div><dt class="text-foreground-muted">Líneas</dt><dd class="mt-0.5 font-mono text-foreground">{item.line_count}</dd></div>
              </dl>
            </div>
          </li>
        {/each}
      </ul>
    {/if}
    {#if selectedIds.length > 0}
      <section class="border-t border-border bg-surface-muted/20 p-4" aria-labelledby="selected-requests-heading">
        <div class="mb-3">
          <h3 id="selected-requests-heading" class="text-sm font-semibold text-foreground">Solicitudes seleccionadas</h3>
          <p class="mt-1 text-xs text-foreground-muted">La selección permanece al cambiar filtros. Revisa aquí todas las solicitudes y quita cualquiera antes de crear el borrador.</p>
          {#if selectedCandidatesError}<p class="mt-2 text-xs text-danger" role="status">{selectedCandidatesError}</p>{/if}
        </div>
        <ul class="grid grid-cols-1 gap-2 xl:grid-cols-2">
          {#each selectedIds as requestId (requestId)}
            {@const selectedCandidate = selectedCandidatesById[requestId]?.candidate}
            {@const selectedResolution = selectedRequestResolutionsById[requestId]}
            {@const requestCode = selectedCandidate?.code ?? selectedResolution?.code ?? 'Solicitud seleccionada'}
            <li class="flex min-w-0 items-start justify-between gap-3 rounded-lg border border-border bg-surface p-3">
              <div class="min-w-0">
                <p class="truncate font-mono text-xs font-semibold text-foreground">{requestCode}</p>
                {#if selectedCandidate}
                  <p class="mt-1 truncate text-xs text-foreground-muted">{selectedCandidate.branch_name ?? 'Sucursal'} · {selectedCandidate.details.length} línea(s) · {formatDate(selectedCandidate.request_date)}</p>
                {:else if selectedResolution?.eligibility === 'already_consolidated'}
                  <p class="mt-1 text-xs text-warning">Ya incluida en {selectedResolution.consolidations.map((item) => `${item.code} · ${consolidationStatusLabel(item.status)}`).join(', ')}.</p>
                  <div class="mt-2 flex flex-wrap gap-2">
                    {#each selectedResolution.consolidations as consolidation (consolidation.id)}
                      <a class="text-xs font-medium text-primary underline hover:no-underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary" href={`/purchase-consolidations/${consolidation.id}`} aria-label={`Abrir consolidado ${consolidation.code}`}>
                        Abrir {consolidation.code}
                      </a>
                    {/each}
                  </div>
                {:else if selectedResolution?.eligibility === 'not_eligible'}
                  <p class="mt-1 text-xs text-danger">La solicitud ya no está aprobada para consolidar. Quítala para continuar.</p>
                {:else if selectedResolution?.eligibility === 'unavailable'}
                  <p class="mt-1 text-xs text-danger">No se puede consultar esta solicitud con tu acceso. Quítala para continuar.</p>
                {:else if selectedResolution?.eligibility === 'eligible'}
                  <p class="mt-1 text-xs text-danger">No se pudo cargar el detalle de la solicitud. Intenta Buscar otra vez.</p>
                {:else}
                  <p class="mt-1 text-xs text-foreground-muted">No se pudo resolver la solicitud seleccionada.</p>
                {/if}
                {#if selectedCandidate && selectedIdsOutsidePeriod.includes(requestId)}<p class="mt-1 text-xs text-danger">Fuera del período. Ajusta las fechas o quita esta solicitud.</p>{/if}
                {#if !selectedCandidate && failedSelectedCandidateIds.includes(requestId)}<p class="mt-1 text-xs text-danger">No se pudo actualizar el estado. Intenta Buscar otra vez; un fallo de consulta no significa que ya esté consolidada.</p>
                {:else if !selectedCandidate && !selectedResolution}<p class="mt-1 text-xs text-danger">No está disponible para consolidar. Quítala para continuar.</p>{/if}
              </div>
              <button type="button" aria-label={`Quitar ${requestCode} de esta selección`} class="shrink-0 rounded-md px-2 py-1 text-xs font-medium text-danger hover:bg-danger/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger" onclick={() => toggleRequest(requestId, false)}>Quitar de esta selección</button>
            </li>
          {/each}
        </ul>
      </section>
    {/if}
    {#if selectedDemandGroups.length > 0}
      <section class="border-t border-border bg-surface-muted/30 p-4" aria-labelledby="branch-demand-heading">
        <div class="mb-3">
          <h3 id="branch-demand-heading" class="text-sm font-semibold text-foreground">Demanda por sucursal y producto</h3>
          <p class="mt-1 text-xs text-foreground-muted">El conteo ayuda a ver cuántas veces se pidió el producto en esa sucursal durante el período. Referencia manual: baja = ocasional, media = recurrente, alta = frecuente. No hay umbrales automáticos; tú eliges y no cambia las cantidades ni la prioridad.</p>
        </div>
        <ul class="grid grid-cols-1 gap-3 xl:grid-cols-2">
          {#each selectedDemandGroups as group (group.key)}
            <li class="grid grid-cols-1 gap-3 rounded-lg border border-border bg-surface p-3 sm:grid-cols-[minmax(0,1fr)_12rem] sm:items-center">
              <div class="min-w-0">
                <p class="break-words text-sm font-medium text-foreground">{group.productName}</p>
                <p class="mt-0.5 font-mono text-xs text-foreground-muted">{group.productSku}</p>
                <p class="mt-1 text-xs text-foreground-muted">{group.branchName} · {#if group.requestCount === null}Sin conteo disponible para el período actual; revisa las fechas y solicitudes seleccionadas{:else}{group.requestCount} {group.requestCount === 1 ? 'solicitud aprobada o procesada' : 'solicitudes aprobadas o procesadas'} en este período{/if}</p>
              </div>
              <label class="consolidation-field-label">Nivel manual
                <select aria-label={`Nivel de demanda ${group.productName} ${group.branchName}`} value={demandLevels[group.key] ?? ''} onchange={(event) => demandLevels = { ...demandLevels, [group.key]: (event.currentTarget.value as BranchDemandLevel | '') }} class="consolidation-field-control">
                  <option value="">Sin clasificar</option>
                  <option value="low">Demanda baja</option>
                  <option value="medium">Demanda media</option>
                  <option value="high">Demanda alta</option>
                </select>
              </label>
            </li>
          {/each}
        </ul>
      </section>
    {/if}
    <div class="flex flex-col gap-3 border-t border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <p class="text-xs text-foreground-muted">{selectedIds.length} solicitud(es) seleccionada(s). {#if selectedIds.length > 0}La selección se conserva al cambiar filtros.{:else}Marca solicitudes aprobadas para iniciar el borrador.{/if}</p>
        {#if selectedIds.length > 100}<p class="mt-1 text-xs text-danger">Un consolidado admite hasta 100 solicitudes; quita {selectedIds.length - 100}.</p>
        {:else if selectedIdsWithoutDetails.length > 0}<p class="mt-1 text-xs text-danger">Quita las solicitudes no elegibles o sin detalle disponible antes de continuar.</p>
        {:else if selectedIdsOutsidePeriod.length > 0}<p class="mt-1 text-xs text-danger">Ajusta el período o quita las solicitudes que quedaron fuera de las fechas.</p>{/if}
      </div>
      <div class="flex gap-2"><Button variant="secondary" onclick={() => goto('/purchase-requests')}>Cancelar</Button><Button disabled={!canCreateConsolidation()} onclick={createConsolidation}>{submitting ? 'Creando…' : 'Crear borrador'}</Button></div>
    </div>
  </Card>
</div>

<style>
  :global(.purchase-consolidation-create .hover-lift) { transition: none; }
  :global(.purchase-consolidation-create .hover-lift:hover) { transform: none; box-shadow: var(--shadow-md); }
</style>
