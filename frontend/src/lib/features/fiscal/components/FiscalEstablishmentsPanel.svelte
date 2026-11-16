<script lang="ts">
  import { onMount } from 'svelte';
  import Badge from '#lib/components/ui/Badge.svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import Modal from '#lib/components/ui/Modal.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { fiscalApi } from '#lib/api/fiscal.ts';
  import {
    ESTABLISHMENT_PREFIX,
    ESTABLISHMENT_TYPE_LABELS,
    isEstablishmentCode,
    isPointOfSaleCode,
    nextEstablishmentCode,
    nextPointOfSaleCode
  } from '#lib/features/fiscal/labels.ts';
  import type {
    BranchOption,
    EconomicActivity,
    Establishment,
    EstablishmentType,
    PointOfSale
  } from '#lib/types/fiscal.ts';

  let { canManage }: { canManage: boolean } = $props();

  const TYPES: EstablishmentType[] = ['02', '01', '04', '07'];
  const inputClass =
    'h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground placeholder:text-foreground-muted focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-60';

  let establishments = $state<Establishment[]>([]);
  let branches = $state<BranchOption[]>([]);
  let activities = $state<EconomicActivity[]>([]);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let notice = $state<string | null>(null);

  // Establishment form
  let estOpen = $state(false);
  let estEditing = $state<Establishment | null>(null);
  let estBranch = $state('');
  let estType = $state<EstablishmentType>('01');
  let estCode = $state('');
  let estActivity = $state('');
  let estActive = $state(true);
  let estError = $state<string | null>(null);
  let estSaving = $state(false);

  // Point of sale form
  let posOpen = $state(false);
  let posEstablishment = $state<Establishment | null>(null);
  let posEditing = $state<PointOfSale | null>(null);
  let posCode = $state('');
  let posName = $state('');
  let posActive = $state(true);
  let posError = $state<string | null>(null);
  let posSaving = $state(false);

  const freeBranches = $derived(branches.filter((b) => b.establishment_id === null));
  const takenCodes = $derived(
    establishments.filter((e) => e.id !== estEditing?.id).map((e) => e.code)
  );
  const estCodeValid = $derived(isEstablishmentCode(estType, estCode));

  async function load() {
    loading = true;
    loadError = null;
    try {
      [establishments, branches, activities] = await Promise.all([
        fiscalApi.listEstablishments(),
        fiscalApi.listBranchOptions(),
        fiscalApi.listActivities()
      ]);
    } catch (cause) {
      loadError =
        cause instanceof HttpError ? cause.message : 'No se pudieron cargar los establecimientos.';
    } finally {
      loading = false;
    }
  }

  onMount(() => void load());

  function openCreate() {
    estEditing = null;
    const first = freeBranches[0];
    estBranch = first?.id ?? '';
    estType = first?.is_headquarters ? '02' : '01';
    estCode = nextEstablishmentCode(estType, takenCodes);
    estActivity = activities.find((a) => a.is_primary)?.id ?? '';
    estActive = true;
    estError = null;
    estOpen = true;
  }

  function openEdit(item: Establishment) {
    estEditing = item;
    estBranch = item.branch_id;
    estType = item.establishment_type;
    estCode = item.code;
    estActivity = item.activity_id ?? '';
    estActive = item.is_active;
    estError = null;
    estOpen = true;
  }

  function changeBranch() {
    if (estEditing) return;
    const branch = branches.find((b) => b.id === estBranch);
    if (branch) changeType(branch.is_headquarters ? '02' : '01');
  }

  function changeType(next: EstablishmentType) {
    estType = next;
    if (!isEstablishmentCode(next, estCode)) estCode = nextEstablishmentCode(next, takenCodes);
  }

  async function saveEstablishment(event: SubmitEvent) {
    event.preventDefault();
    estSaving = true;
    estError = null;
    const code = estCode.trim().toUpperCase();
    const activity = estActivity || null;
    try {
      if (estEditing) {
        await fiscalApi.updateEstablishment(estEditing.id, {
          establishment_type: estType,
          code,
          activity_id: activity,
          is_active: estActive
        });
        notice = `Se guardaron los cambios de ${code}.`;
      } else {
        await fiscalApi.createEstablishment({
          branch_id: estBranch,
          establishment_type: estType,
          code,
          activity_id: activity
        });
        notice = `La sucursal quedó registrada como establecimiento ${code}. Agrégale sus cajas.`;
      }
      estOpen = false;
      await load();
    } catch (cause) {
      estError =
        cause instanceof HttpError ? cause.message : 'No se pudo guardar el establecimiento.';
    } finally {
      estSaving = false;
    }
  }

  function openPointCreate(item: Establishment) {
    posEstablishment = item;
    posEditing = null;
    posCode = nextPointOfSaleCode(item.points_of_sale.map((p) => p.code));
    posName = `Caja ${item.points_of_sale.length + 1}`;
    posActive = true;
    posError = null;
    posOpen = true;
  }

  function openPointEdit(item: Establishment, point: PointOfSale) {
    posEstablishment = item;
    posEditing = point;
    posCode = point.code;
    posName = point.name;
    posActive = point.is_active;
    posError = null;
    posOpen = true;
  }

  async function savePoint(event: SubmitEvent) {
    event.preventDefault();
    if (!posEstablishment) return;
    posSaving = true;
    posError = null;
    const code = posCode.trim().toUpperCase();
    try {
      if (posEditing) {
        await fiscalApi.updatePointOfSale(posEditing.id, {
          code,
          name: posName.trim(),
          is_active: posActive
        });
      } else {
        await fiscalApi.createPointOfSale(posEstablishment.id, { code, name: posName.trim() });
      }
      notice = `Se guardó el punto de venta ${posEstablishment.code}${code}.`;
      posOpen = false;
      await load();
    } catch (cause) {
      posError =
        cause instanceof HttpError ? cause.message : 'No se pudo guardar el punto de venta.';
    } finally {
      posSaving = false;
    }
  }

  function activityLabel(id: string | null): string {
    const activity = activities.find((a) => a.id === id);
    return activity ? `${activity.code} · ${activity.description}` : 'La principal de la empresa';
  }
</script>

<div class="space-y-4">
  <div class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
    <p class="max-w-3xl text-sm text-foreground-muted">
      Cada sucursal que opera ante Hacienda es un establecimiento, y cada caja es un punto de venta.
      Sus códigos forman el número de control del documento, por ejemplo
      <span class="font-mono text-foreground">DTE-01-S001P001-…</span>
    </p>
    {#if canManage}
      <div class="flex flex-col items-start gap-1 sm:items-end">
        <Button
          onclick={openCreate}
          disabled={loading || freeBranches.length === 0}
          describedby="est-register-help"
        >
          Registrar establecimiento
        </Button>
        {#if !loading && !loadError && freeBranches.length === 0}
          <p id="est-register-help" class="text-xs text-foreground-muted">
            {establishments.length > 0
              ? 'Todas las sucursales ya son establecimientos.'
              : 'Primero registra una sucursal en Sucursales.'}
          </p>
        {/if}
      </div>
    {/if}
  </div>

  {#if notice}
    <p
      class="rounded-xl border border-success/30 bg-success/10 p-3 text-sm text-success"
      role="status"
    >
      {notice}
    </p>
  {/if}

  {#if loading}
    <div class="grid gap-3 md:grid-cols-2" aria-busy="true">
      <p class="sr-only" role="status">Cargando establecimientos…</p>
      <div class="skeleton h-48 rounded-xl motion-reduce:animate-none" aria-hidden="true"></div>
      <div class="skeleton h-48 rounded-xl motion-reduce:animate-none" aria-hidden="true"></div>
    </div>
  {:else if loadError}
    <div
      class="flex flex-col gap-3 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger sm:flex-row sm:items-center sm:justify-between"
      role="alert"
    >
      <span>{loadError}</span>
      <Button variant="secondary" size="sm" onclick={() => void load()}>Reintentar</Button>
    </div>
  {:else if establishments.length === 0}
    <div class="rounded-xl border border-border bg-surface-elevated px-6 py-12 text-center">
      <div
        class="mx-auto flex h-11 w-11 items-center justify-center rounded-xl bg-surface-muted text-foreground-muted"
        aria-hidden="true"
      >
        <svg
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.8"
        >
          <path d="M3 21h18M5 21V7l7-4 7 4v14M9 21v-6h6v6" />
        </svg>
      </div>
      <p class="mt-3 text-sm font-semibold text-foreground">Aún no hay establecimientos</p>
      <p class="mt-1 text-sm text-foreground-muted">
        Registra la casa matriz y cada sucursal que emite documentos.
      </p>
      {#if canManage && freeBranches.length > 0}
        <Button class="mt-4" size="sm" onclick={openCreate}>Registrar el primero</Button>
      {/if}
    </div>
  {:else}
    <div class="grid gap-3 md:grid-cols-2">
      {#each establishments as item (item.id)}
        <article class="flex flex-col rounded-xl border border-border bg-surface-elevated p-4">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <p class="flex flex-wrap items-center gap-2">
                <span class="font-mono text-lg font-semibold text-foreground">{item.code}</span>
                <Badge variant="neutral">{ESTABLISHMENT_TYPE_LABELS[item.establishment_type]}</Badge
                >
                {#if !item.is_active}<Badge variant="danger">Inactivo</Badge>{/if}
              </p>
              <h3 class="mt-1 break-words font-medium text-foreground">{item.branch_name}</h3>
            </div>
            {#if canManage}
              <Button variant="secondary" size="sm" onclick={() => openEdit(item)}>Editar</Button>
            {/if}
          </div>
          <dl class="mt-3 space-y-2 text-sm">
            <div>
              <dt class="text-xs text-foreground-muted">Dirección en el DTE</dt>
              <dd class="break-words text-foreground">
                {item.address.complement}, {item.address.district}, {item.address.municipality},
                {item.address.department}
              </dd>
              {#if item.address.complete}
                <dd class="font-mono text-xs text-foreground-muted">
                  Departamento {item.address.department_code} · municipio {item.address
                    .municipality_code}
                  · distrito {item.address.district_code}
                </dd>
              {:else}
                <dd class="mt-1 text-xs text-warning">
                  La dirección de la sucursal no tiene códigos de Hacienda; corrígela en Sucursales.
                </dd>
              {/if}
            </div>
            <div>
              <dt class="text-xs text-foreground-muted">Actividad económica</dt>
              <dd class="break-words text-foreground">{activityLabel(item.activity_id)}</dd>
            </div>
          </dl>
          <div class="mt-4 border-t border-border pt-3">
            <div class="flex items-center justify-between gap-2">
              <h4 class="text-xs font-semibold uppercase tracking-wider text-foreground-muted">
                Puntos de venta
              </h4>
              {#if canManage}
                <Button variant="ghost" size="sm" onclick={() => openPointCreate(item)}>
                  Agregar caja
                </Button>
              {/if}
            </div>
            {#if item.points_of_sale.length === 0}
              <p class="mt-2 text-sm text-foreground-muted">
                Sin cajas: este establecimiento aún no puede emitir.
              </p>
            {:else}
              <ul class="mt-2 space-y-1">
                {#each item.points_of_sale as point (point.id)}
                  <li
                    class="flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-surface-muted/50"
                  >
                    <span class="min-w-0 truncate">
                      <span class="font-mono text-foreground">{point.code}</span>
                      <span class="text-foreground-muted"> · {point.name}</span>
                      {#if !point.is_active}<span class="text-xs text-danger">
                          (inactiva)</span
                        >{/if}
                    </span>
                    {#if canManage}
                      <Button variant="ghost" size="sm" onclick={() => openPointEdit(item, point)}>
                        Editar
                      </Button>
                    {/if}
                  </li>
                {/each}
              </ul>
            {/if}
          </div>
        </article>
      {/each}
    </div>
  {/if}
</div>

<Modal
  open={estOpen}
  title={estEditing ? `Editar ${estEditing.code}` : 'Registrar establecimiento'}
  onclose={() => (estOpen = false)}
  size="md"
>
  <form class="space-y-4" onsubmit={saveEstablishment}>
    {#if estError}
      <p
        class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
        role="alert"
      >
        {estError}
      </p>
    {/if}
    <div>
      <label for="est-branch" class="mb-1 block text-sm font-medium text-foreground">Sucursal</label
      >
      {#if estEditing}
        <p id="est-branch" class="text-sm text-foreground">{estEditing.branch_name}</p>
      {:else}
        <select
          id="est-branch"
          bind:value={estBranch}
          onchange={changeBranch}
          required
          class={inputClass}
        >
          {#each freeBranches as branch (branch.id)}
            <option value={branch.id}
              >{branch.name}{branch.is_headquarters ? ' (casa matriz)' : ''}</option
            >
          {/each}
        </select>
      {/if}
      <p class="mt-1 text-xs text-foreground-muted">
        El documento usa la dirección, el teléfono y el correo de la sucursal.
      </p>
    </div>
    <div class="grid gap-4 sm:grid-cols-2">
      <div>
        <label for="est-type" class="mb-1 block text-sm font-medium text-foreground">Tipo</label>
        <select
          id="est-type"
          value={estType}
          onchange={(e) =>
            changeType((e.currentTarget as HTMLSelectElement).value as EstablishmentType)}
          class={inputClass}
        >
          {#each TYPES as type (type)}
            <option value={type}>{ESTABLISHMENT_TYPE_LABELS[type]}</option>
          {/each}
        </select>
      </div>
      <div>
        <label for="est-code" class="mb-1 block text-sm font-medium text-foreground">Código</label>
        <input
          id="est-code"
          bind:value={estCode}
          maxlength="4"
          required
          aria-describedby="est-code-help"
          class="{inputClass} font-mono uppercase"
        />
        <p
          id="est-code-help"
          class="mt-1 text-xs {estCodeValid ? 'text-foreground-muted' : 'text-danger'}"
        >
          Letra {ESTABLISHMENT_PREFIX[estType]} y tres dígitos, por ejemplo {ESTABLISHMENT_PREFIX[
            estType
          ]}001.
        </p>
      </div>
    </div>
    <div>
      <label for="est-activity" class="mb-1 block text-sm font-medium text-foreground">
        Actividad de sus operaciones
      </label>
      <select id="est-activity" bind:value={estActivity} class={inputClass}>
        <option value="">La principal de la empresa</option>
        {#each activities as activity (activity.id)}
          <option value={activity.id}>{activity.code} · {activity.description}</option>
        {/each}
      </select>
    </div>
    {#if estEditing}
      <label class="flex min-h-11 items-center gap-2 text-sm text-foreground">
        <input type="checkbox" bind:checked={estActive} /> Activo para emitir documentos
      </label>
    {/if}
    <div class="flex justify-end gap-2 border-t border-border pt-4">
      <Button type="button" variant="ghost" onclick={() => (estOpen = false)}>Cancelar</Button>
      <Button type="submit" disabled={estSaving || !estCodeValid || (!estEditing && !estBranch)}>
        {estSaving ? 'Guardando…' : 'Guardar'}
      </Button>
    </div>
  </form>
</Modal>

<Modal
  open={posOpen}
  title={posEditing
    ? `Editar caja ${posEditing.code}`
    : `Nueva caja en ${posEstablishment?.code ?? ''}`}
  onclose={() => (posOpen = false)}
  size="sm"
>
  <form class="space-y-4" onsubmit={savePoint}>
    {#if posError}
      <p
        class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
        role="alert"
      >
        {posError}
      </p>
    {/if}
    <div>
      <label for="pos-code" class="mb-1 block text-sm font-medium text-foreground">Código</label>
      <input
        id="pos-code"
        bind:value={posCode}
        maxlength="4"
        required
        class="{inputClass} font-mono uppercase"
      />
      <p
        class="mt-1 text-xs {isPointOfSaleCode(posCode) ? 'text-foreground-muted' : 'text-danger'}"
      >
        Letra P y tres dígitos, por ejemplo P001.
      </p>
    </div>
    <div>
      <label for="pos-name" class="mb-1 block text-sm font-medium text-foreground">Nombre</label>
      <input
        id="pos-name"
        bind:value={posName}
        minlength="2"
        maxlength="120"
        required
        class={inputClass}
      />
    </div>
    {#if posEditing}
      <label class="flex min-h-11 items-center gap-2 text-sm text-foreground">
        <input type="checkbox" bind:checked={posActive} /> Activa
      </label>
    {/if}
    <div class="flex justify-end gap-2 border-t border-border pt-4">
      <Button type="button" variant="ghost" onclick={() => (posOpen = false)}>Cancelar</Button>
      <Button type="submit" disabled={posSaving || !isPointOfSaleCode(posCode)}>
        {posSaving ? 'Guardando…' : 'Guardar'}
      </Button>
    </div>
  </form>
</Modal>
