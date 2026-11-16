<script lang="ts">
  import { onMount } from 'svelte';
  import Badge from '#lib/components/ui/Badge.svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import Modal from '#lib/components/ui/Modal.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { priceListsApi } from '#lib/api/price-lists.ts';
  import { permissions } from '#lib/stores/permissions.svelte.ts';
  import type { PriceList, PriceListInput } from '#lib/types/price-list.ts';

  const inputClass =
    'h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary';
  const labelClass = 'mb-1 block text-sm font-medium text-foreground';

  let lists = $state<PriceList[]>([]);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let editing = $state<PriceList | null>(null);
  let open = $state(false);
  let form = $state<PriceListInput>(blank());
  let saving = $state(false);
  let formError = $state<string | null>(null);

  const canManage = $derived(permissions.hasPermission('price_lists:manage'));

  function blank(): PriceListInput {
    return {
      code: '',
      name: '',
      description: null,
      prices_include_vat: true,
      is_default: false,
      is_active: true
    };
  }

  async function load() {
    loading = true;
    loadError = null;
    try {
      lists = await priceListsApi.list();
    } catch (cause) {
      loadError =
        cause instanceof HttpError ? cause.message : 'No se pudieron cargar las listas de precios.';
    } finally {
      loading = false;
    }
  }

  onMount(() => void load());

  function openEditor(item: PriceList | null) {
    editing = item;
    form = item
      ? {
          code: item.code,
          name: item.name,
          description: item.description,
          prices_include_vat: item.prices_include_vat,
          is_default: item.is_default,
          is_active: item.is_active
        }
      : { ...blank(), is_default: lists.length === 0 };
    formError = null;
    open = true;
  }

  async function save(event: SubmitEvent) {
    event.preventDefault();
    saving = true;
    formError = null;
    try {
      if (editing) await priceListsApi.update(editing.id, form);
      else await priceListsApi.create(form);
      open = false;
      await load();
    } catch (cause) {
      formError = cause instanceof HttpError ? cause.message : 'No se pudo guardar la lista.';
    } finally {
      saving = false;
    }
  }
</script>

<svelte:head>
  <title>Listas de precios | GestionaSV</title>
</svelte:head>

<div class="space-y-5">
  <header class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
    <div>
      <p class="text-xs font-semibold uppercase tracking-wider text-primary">Ventas</p>
      <h1 class="page-title-echo mt-1 text-2xl font-bold tracking-tight text-foreground">
        Listas de precios
      </h1>
      <p class="mt-1 max-w-3xl text-sm text-foreground-muted">
        El precio de venta sale de una lista, no lo teclea el vendedor. Cada cliente usa su lista o,
        si no tiene, la predeterminada. Los cambios de precio quedan en el historial.
      </p>
    </div>
    {#if canManage && !loading && lists.length > 0}
      <Button class="shrink-0" onclick={() => openEditor(null)}>Nueva lista</Button>
    {/if}
  </header>

  {#if loading}
    <div class="grid gap-3 sm:grid-cols-2" aria-busy="true">
      <p class="sr-only" role="status">Cargando listas de precios…</p>
      <div class="skeleton h-32 rounded-xl motion-reduce:animate-none" aria-hidden="true"></div>
      <div class="skeleton h-32 rounded-xl motion-reduce:animate-none" aria-hidden="true"></div>
    </div>
  {:else if loadError}
    <div
      class="flex flex-col gap-3 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger sm:flex-row sm:items-center sm:justify-between"
      role="alert"
    >
      <span>{loadError}</span>
      <Button variant="secondary" size="sm" onclick={() => void load()}>Reintentar</Button>
    </div>
  {:else if lists.length === 0}
    <div
      class="flex flex-col items-center gap-3 rounded-xl border border-border bg-surface-elevated px-6 py-12 text-center"
    >
      <span
        class="flex h-12 w-12 items-center justify-center rounded-full bg-surface-muted text-foreground-muted"
        aria-hidden="true"
      >
        <svg
          viewBox="0 0 24 24"
          class="h-6 w-6"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
        >
          <path
            d="M7 7h.01M3 11.5V4a1 1 0 011-1h7.5a1 1 0 01.7.3l8.5 8.5a1 1 0 010 1.4l-7.5 7.5a1 1 0 01-1.4 0L3.3 12.2a1 1 0 01-.3-.7z"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </span>
      <div>
        <p class="text-sm font-semibold text-foreground">Aún no hay listas de precios</p>
        <p class="mt-1 max-w-md text-sm text-foreground-muted">
          Crea la primera, por ejemplo «Mostrador» con IVA incluido. Será la predeterminada.
        </p>
      </div>
      {#if canManage}
        <Button variant="secondary" onclick={() => openEditor(null)}>Crear lista</Button>
      {/if}
    </div>
  {:else}
    <ul class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {#each lists as item (item.id)}
        <li class="flex flex-col rounded-xl border border-border bg-surface-elevated p-4">
          <div class="flex flex-wrap items-center gap-2">
            <a
              href={`/sales/price-lists/${item.id}`}
              class="font-semibold text-foreground hover:underline">{item.name}</a
            >
            {#if item.is_default}<Badge variant="primary">Predeterminada</Badge>{/if}
            {#if !item.is_active}<Badge variant="neutral">Inactiva</Badge>{/if}
          </div>
          <p class="mt-1 font-mono text-xs text-foreground-muted">{item.code}</p>
          <p class="mt-2 text-sm text-foreground-muted">
            {item.prices_include_vat ? 'Precios con IVA incluido' : 'Precios sin IVA'} ·
            {item.price_count}
            {item.price_count === 1 ? 'precio' : 'precios'} ·
            {item.customer_count}
            {item.customer_count === 1 ? 'cliente' : 'clientes'}
          </p>
          {#if item.description}
            <p class="mt-2 line-clamp-2 text-sm text-foreground">{item.description}</p>
          {/if}
          <div class="mt-auto flex gap-2 pt-3">
            <a
              href={`/sales/price-lists/${item.id}`}
              class="inline-flex min-h-9 items-center rounded-lg border border-border bg-surface-elevated px-3 text-sm font-medium text-foreground shadow-soft hover:border-border-strong hover:bg-surface-hover"
            >
              Ver precios
            </a>
            {#if canManage}
              <Button variant="ghost" size="sm" onclick={() => openEditor(item)}>Editar</Button>
            {/if}
          </div>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<Modal
  {open}
  title={editing ? `Editar ${editing.name}` : 'Nueva lista de precios'}
  onclose={() => (open = false)}
>
  <form class="space-y-4" onsubmit={save}>
    {#if formError}
      <p
        class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
        role="alert"
      >
        {formError}
      </p>
    {/if}
    <div class="grid gap-4 sm:grid-cols-3">
      <div>
        <label for="list-code" class={labelClass}>Código</label>
        <input
          id="list-code"
          bind:value={form.code}
          required
          maxlength="20"
          placeholder="MAYOREO"
          class="{inputClass} font-mono uppercase"
        />
      </div>
      <div class="sm:col-span-2">
        <label for="list-name" class={labelClass}>Nombre</label>
        <input id="list-name" bind:value={form.name} required maxlength="120" class={inputClass} />
      </div>
    </div>
    <div>
      <label for="list-description" class={labelClass}>Descripción (opcional)</label>
      <textarea
        id="list-description"
        value={form.description ?? ''}
        oninput={(e) => (form.description = e.currentTarget.value || null)}
        rows="2"
        class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
      ></textarea>
    </div>
    <fieldset>
      <legend class={labelClass}>Los precios de esta lista</legend>
      <div class="grid gap-2 sm:grid-cols-2">
        <label class="flex items-start gap-2 rounded-lg border border-border p-3 text-sm">
          <input
            type="radio"
            name="list-vat"
            checked={form.prices_include_vat}
            onchange={() => (form.prices_include_vat = true)}
            class="mt-1"
          />
          <span>
            <span class="font-medium text-foreground">Incluyen IVA</span>
            <span class="block text-foreground-muted">Mostrador y consumidor final.</span>
          </span>
        </label>
        <label class="flex items-start gap-2 rounded-lg border border-border p-3 text-sm">
          <input
            type="radio"
            name="list-vat"
            checked={!form.prices_include_vat}
            onchange={() => (form.prices_include_vat = false)}
            class="mt-1"
          />
          <span>
            <span class="font-medium text-foreground">No incluyen IVA</span>
            <span class="block text-foreground-muted">Mayoreo y contribuyentes.</span>
          </span>
        </label>
      </div>
      {#if editing && editing.price_count > 0 && form.prices_include_vat !== editing.prices_include_vat}
        <p class="mt-2 text-sm text-warning" role="status">
          Los precios guardados no se convierten: revisa que sigan siendo correctos.
        </p>
      {/if}
    </fieldset>
    <div class="space-y-2">
      <label class="flex items-center gap-2 text-sm text-foreground">
        <input
          type="checkbox"
          checked={form.is_default}
          disabled={editing?.is_default}
          onchange={(e) => {
            form.is_default = e.currentTarget.checked;
            if (form.is_default) form.is_active = true;
          }}
        />
        Lista predeterminada (para clientes sin lista asignada)
      </label>
      <label class="flex items-center gap-2 text-sm text-foreground">
        <input
          type="checkbox"
          checked={form.is_active}
          disabled={form.is_default}
          onchange={(e) => (form.is_active = e.currentTarget.checked)}
        />
        Activa
      </label>
      {#if editing?.is_default}
        <p class="text-xs text-foreground-muted">
          Para que deje de ser la predeterminada, marca otra lista como predeterminada.
        </p>
      {/if}
    </div>
    <div class="flex justify-end gap-2 border-t border-border pt-4">
      <Button type="button" variant="ghost" onclick={() => (open = false)}>Cancelar</Button>
      <Button type="submit" disabled={saving}>{saving ? 'Guardando…' : 'Guardar'}</Button>
    </div>
  </form>
</Modal>
