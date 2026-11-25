<script lang="ts">
  import { onMount } from 'svelte';
  import Badge from '#lib/components/ui/Badge.svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { discountPoliciesApi } from '#lib/api/price-lists.ts';
  import type { RolePolicy } from '#lib/types/price-list.ts';

  interface Draft {
    line: string;
    global: string;
  }

  let roles = $state<RolePolicy[]>([]);
  let drafts = $state<Record<string, Draft>>({});
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let savingId = $state<string | null>(null);
  let rowError = $state<Record<string, string>>({});
  let saved = $state<string | null>(null);

  function toDraft(role: RolePolicy): Draft {
    return {
      line: String(Number(role.max_line_discount_percent)),
      global: String(Number(role.max_global_discount_percent))
    };
  }

  async function load() {
    loading = true;
    loadError = null;
    try {
      roles = await discountPoliciesApi.list();
      drafts = Object.fromEntries(roles.map((role) => [role.role_id, toDraft(role)]));
    } catch (cause) {
      loadError =
        cause instanceof HttpError
          ? cause.message
          : 'No se pudieron cargar los topes de descuento.';
    } finally {
      loading = false;
    }
  }

  onMount(() => void load());

  function changed(role: RolePolicy): boolean {
    const draft = drafts[role.role_id];
    const original = toDraft(role);
    return (
      !!draft &&
      (Number(draft.line) !== Number(original.line) ||
        Number(draft.global) !== Number(original.global))
    );
  }

  async function save(role: RolePolicy) {
    const draft = drafts[role.role_id];
    if (!draft) return;
    savingId = role.role_id;
    rowError = { ...rowError, [role.role_id]: '' };
    saved = null;
    try {
      const updated = await discountPoliciesApi.save(role.role_id, {
        max_line_discount_percent: String(draft.line || 0),
        max_global_discount_percent: String(draft.global || 0)
      });
      roles = roles.map((r) => (r.role_id === role.role_id ? updated : r));
      drafts = { ...drafts, [role.role_id]: toDraft(updated) };
      saved = `Se guardaron los topes de ${updated.role_name}.`;
    } catch (cause) {
      rowError = {
        ...rowError,
        [role.role_id]: cause instanceof HttpError ? cause.message : 'No se pudo guardar.'
      };
    } finally {
      savingId = null;
    }
  }

  function update(roleId: string, patch: Partial<Draft>) {
    const current = drafts[roleId];
    if (current) drafts = { ...drafts, [roleId]: { ...current, ...patch } };
  }
</script>

<svelte:head>
  <title>Topes de descuento | GestionaSV</title>
</svelte:head>

<div class="space-y-5">
  <header>
    <p class="text-xs font-semibold uppercase tracking-wider text-primary">Ventas</p>
    <h1 class="page-title-echo mt-1 text-2xl font-bold tracking-tight text-foreground">
      Topes de descuento
    </h1>
    <p class="mt-1 max-w-3xl text-sm text-foreground-muted">
      Cuánto descuento puede dar cada rol sin pedir autorización, por línea y sobre el total. Un
      usuario con varios roles toma el tope más alto. Un rol sin topes no puede dar descuento.
      Ningún rol puede vender por debajo del costo del kardex.
    </p>
  </header>

  {#if saved}
    <p
      class="rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-success"
      role="status"
    >
      {saved}
    </p>
  {/if}

  <section class="overflow-hidden rounded-xl border border-border bg-surface-elevated">
    {#if loading}
      <div class="space-y-3 p-4" aria-busy="true">
        <p class="sr-only" role="status">Cargando topes…</p>
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
    {:else if roles.length === 0}
      <div class="flex flex-col items-center gap-3 px-6 py-12 text-center">
        <p class="text-sm font-semibold text-foreground">La empresa no tiene roles</p>
        <p class="max-w-md text-sm text-foreground-muted">
          Crea los roles en Roles y permisos y vuelve aquí para fijar sus topes.
        </p>
        <a
          href="/roles"
          class="inline-flex min-h-9 items-center rounded-lg border border-border px-3 text-sm font-medium text-foreground hover:bg-surface-hover"
          >Ir a roles</a
        >
      </div>
    {:else}
      <ul class="divide-y divide-border">
        {#each roles as role (role.role_id)}
          {@const draft = drafts[role.role_id]}
          {#if draft}
            <li class="grid gap-3 p-4 md:grid-cols-[minmax(0,1.4fr)_8rem_8rem_auto] md:items-end">
              <div class="min-w-0">
                <p class="truncate text-sm font-medium text-foreground">{role.role_name}</p>
                {#if !role.configured}<Badge variant="neutral">Sin topes</Badge>{/if}
              </div>
              <label class="text-xs text-foreground-muted">
                Por línea (%)
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="any"
                  value={draft.line}
                  oninput={(e) => update(role.role_id, { line: e.currentTarget.value })}
                  class="mt-1 h-10 w-full rounded-lg border border-border bg-surface px-2 text-sm text-foreground"
                />
              </label>
              <label class="text-xs text-foreground-muted">
                Global (%)
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="any"
                  value={draft.global}
                  oninput={(e) => update(role.role_id, { global: e.currentTarget.value })}
                  class="mt-1 h-10 w-full rounded-lg border border-border bg-surface px-2 text-sm text-foreground"
                />
              </label>
              <Button
                size="sm"
                disabled={!changed(role) || savingId === role.role_id}
                onclick={() => void save(role)}
              >
                {savingId === role.role_id ? 'Guardando…' : 'Guardar'}
              </Button>
              {#if rowError[role.role_id]}
                <p class="text-sm text-danger md:col-span-4" role="alert">
                  {rowError[role.role_id]}
                </p>
              {/if}
            </li>
          {/if}
        {/each}
      </ul>
    {/if}
  </section>
</div>
