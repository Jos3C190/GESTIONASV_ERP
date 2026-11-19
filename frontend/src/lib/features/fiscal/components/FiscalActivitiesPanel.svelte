<script lang="ts">
  import { onMount } from 'svelte';
  import AsyncSmartSelect, {
    type AsyncSmartOption
  } from '#lib/components/ui/AsyncSmartSelect.svelte';
  import Badge from '#lib/components/ui/Badge.svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { fiscalApi } from '#lib/api/fiscal.ts';
  import { confirmation } from '#lib/stores/confirmation.svelte.ts';
  import RentaFields from '#lib/features/sales/components/RentaFields.svelte';
  import { rentaComplete, rentaLabel } from '#lib/features/sales/renta-labels.ts';
  import type { EconomicActivity } from '#lib/types/fiscal.ts';

  let { canManage }: { canManage: boolean } = $props();

  let activities = $state<EconomicActivity[]>([]);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let selected = $state('');
  let adding = $state(false);
  /** Clasificación de renta en edición, por actividad. */
  let drafts = $state<Record<string, { operation: number | null; income: number | null }>>({});

  function draft(activity: EconomicActivity) {
    return (
      drafts[activity.id] ?? {
        operation: activity.renta_operation_type ?? null,
        income: activity.renta_income_type ?? null
      }
    );
  }

  async function saveRenta(activity: EconomicActivity) {
    const value = draft(activity);
    await run(() => fiscalApi.setActivityRenta(activity.id, value.operation, value.income));
    delete drafts[activity.id];
  }

  async function load() {
    loading = true;
    loadError = null;
    try {
      activities = await fiscalApi.listActivities();
    } catch (cause) {
      loadError =
        cause instanceof HttpError ? cause.message : 'No se pudieron cargar las actividades.';
    } finally {
      loading = false;
    }
  }

  onMount(() => void load());

  async function searchCatalog(query: string): Promise<AsyncSmartOption[]> {
    const items = await fiscalApi.catalog('CAT-019', { search: query.trim(), limit: 30 });
    const taken = new Set(activities.map((a) => a.code));
    return items
      .filter((item) => !taken.has(item.code))
      .map((item) => ({ value: item.code, label: `${item.code} · ${item.name}` }));
  }

  async function run(action: () => Promise<unknown>) {
    actionError = null;
    try {
      await action();
      await load();
    } catch (cause) {
      actionError = cause instanceof HttpError ? cause.message : 'No se pudo completar la acción.';
    }
  }

  async function add() {
    if (!selected) return;
    adding = true;
    await run(() => fiscalApi.addActivity(selected));
    selected = '';
    adding = false;
  }

  function remove(activity: EconomicActivity) {
    confirmation.request({
      kind: 'delete',
      title: 'Quitar actividad económica',
      description: 'Los documentos ya emitidos conservan la actividad con la que se emitieron.',
      resourceName: `${activity.code} · ${activity.description}`,
      confirmLabel: 'Quitar',
      execute: async () => {
        await fiscalApi.deleteActivity(activity.id);
        await load();
      }
    });
  }
</script>

<section class="overflow-hidden rounded-xl border border-border bg-surface-elevated">
  <div class="border-b border-border p-4">
    <h2 class="font-semibold text-foreground">Actividades económicas</h2>
    <p class="mt-1 text-sm text-foreground-muted">
      Registra todas las actividades de la empresa según el catálogo de Hacienda. Cada documento
      lleva la actividad que corresponde a la operación; la principal es la que se usa por defecto.
    </p>
  </div>

  {#if canManage}
    <div class="flex flex-col gap-2 border-b border-border p-4 sm:flex-row sm:items-end">
      <div class="min-w-0 flex-1">
        <AsyncSmartSelect
          id="fiscal-activity-search"
          label="Agregar actividad"
          bind:value={selected}
          placeholder="Buscar por código o nombre…"
          loadOptions={searchCatalog}
        />
      </div>
      <Button onclick={() => void add()} disabled={!selected || adding}>
        {adding ? 'Agregando…' : 'Agregar'}
      </Button>
    </div>
  {/if}

  {#if actionError}
    <p
      class="m-4 rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
      role="alert"
    >
      {actionError}
    </p>
  {/if}

  {#if loading}
    <div class="space-y-3 p-4" aria-busy="true">
      <p class="sr-only" role="status">Cargando actividades…</p>
      <div class="skeleton h-12 rounded-lg motion-reduce:animate-none" aria-hidden="true"></div>
      <div class="skeleton h-12 rounded-lg motion-reduce:animate-none" aria-hidden="true"></div>
    </div>
  {:else if loadError}
    <div
      class="m-4 flex flex-col gap-3 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger sm:flex-row sm:items-center sm:justify-between"
      role="alert"
    >
      <span>{loadError}</span>
      <Button variant="secondary" size="sm" onclick={() => void load()}>Reintentar</Button>
    </div>
  {:else if activities.length === 0}
    <div class="px-6 py-12 text-center">
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
          <path d="M4 6h16M4 12h16M4 18h10" />
        </svg>
      </div>
      <p class="mt-3 text-sm font-semibold text-foreground">Aún no hay actividades</p>
      <p class="mt-1 text-sm text-foreground-muted">
        {canManage
          ? 'Busca la actividad en el catálogo de Hacienda y agrégala; la primera queda como principal.'
          : 'Quien administra la configuración fiscal debe registrarlas.'}
      </p>
    </div>
  {:else}
    <ul class="divide-y divide-border">
      {#each activities as activity (activity.id)}
        <li class="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div class="min-w-0">
            <p class="flex flex-wrap items-center gap-2 text-sm font-medium text-foreground">
              <span class="font-mono">{activity.code}</span>
              {#if activity.is_primary}<Badge variant="primary">Principal</Badge>{/if}
            </p>
            <p class="mt-0.5 break-words text-sm text-foreground-muted">
              {activity.description || 'Código fuera del catálogo vigente'}
            </p>
            <p class="mt-1 text-xs text-foreground-muted">
              Renta sugerida al facturar: {rentaLabel(
                activity.renta_operation_type,
                activity.renta_income_type
              )}
            </p>
            {#if canManage}
              {@const value = draft(activity)}
              <div class="mt-2 grid gap-2 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
                <RentaFields
                  operation={value.operation}
                  income={value.income}
                  onchange={(operation, income) => (drafts[activity.id] = { operation, income })}
                />
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={!drafts[activity.id] || !rentaComplete(value.operation, value.income)}
                  onclick={() => void saveRenta(activity)}>Guardar renta</Button
                >
              </div>
            {/if}
          </div>
          {#if canManage}
            <div class="flex gap-2">
              {#if !activity.is_primary}
                <Button
                  variant="secondary"
                  size="sm"
                  onclick={() => void run(() => fiscalApi.setPrimaryActivity(activity.id))}
                >
                  Marcar como principal
                </Button>
              {/if}
              <Button variant="ghost" size="sm" onclick={() => remove(activity)}>Quitar</Button>
            </div>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</section>
