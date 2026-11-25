<script lang="ts">
  import { onMount } from 'svelte';
  import Badge from '#lib/components/ui/Badge.svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { salesApi } from '#lib/api/sales.ts';
  import { salesPromotionsApi } from '#lib/api/sales-promotions.ts';
  import { formatDay, formatPercent } from '#lib/features/sales/quotation-labels.ts';
  import { branch } from '#lib/stores/branch.svelte.ts';
  import { permissions } from '#lib/stores/permissions.svelte.ts';
  import type { SalesPromotion, PromotionStatus } from '#lib/types/sales-promotions.ts';

  const STATUS: Record<
    PromotionStatus,
    { label: string; variant: 'success' | 'primary' | 'neutral' }
  > = {
    current: { label: 'Vigente', variant: 'success' },
    scheduled: { label: 'Programada', variant: 'primary' },
    expired: { label: 'Vencida', variant: 'neutral' },
    ended: { label: 'Terminada', variant: 'neutral' }
  };
  const inputClass =
    'mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground';

  const canManage = $derived(permissions.hasPermission('sales_promotions:manage'));
  const branches = $derived(branch.branches.filter((item) => item.is_active));

  let promotions = $state<SalesPromotion[]>([]);
  let products = $state<{ id: number; label: string }[]>([]);
  let loading = $state(true);
  let loadError = $state<string | null>(null);
  let includeEnded = $state(false);
  let formOpen = $state(false);
  let saving = $state(false);
  let formError = $state<string | null>(null);
  let notice = $state<string | null>(null);
  let endingId = $state<string | null>(null);

  let draftBranch = $state('');
  let draftProduct = $state('');
  let draftPercent = $state('');
  let draftFrom = $state('');
  let draftTo = $state('');
  let draftNotes = $state('');

  async function load() {
    loading = true;
    loadError = null;
    try {
      promotions = await salesPromotionsApi.list({ include_ended: includeEnded });
    } catch (cause) {
      loadError =
        cause instanceof HttpError ? cause.message : 'No se pudieron cargar las promociones.';
    } finally {
      loading = false;
    }
  }

  async function loadProducts() {
    if (products.length) return;
    const seen = new Map<number, string>();
    for (const item of await salesApi.catalog()) {
      if (!seen.has(item.product_id)) seen.set(item.product_id, `${item.sku} · ${item.name}`);
    }
    products = [...seen].map(([id, label]) => ({ id, label }));
  }

  onMount(() => void load());

  async function openForm() {
    formOpen = true;
    formError = null;
    notice = null;
    draftBranch = branch.id ?? branches[0]?.id ?? '';
    try {
      await loadProducts();
    } catch {
      formError = 'No se pudo cargar el catálogo de productos.';
    }
  }

  const ready = $derived(
    draftBranch !== '' &&
      draftProduct !== '' &&
      Number(draftPercent) > 0 &&
      Number(draftPercent) < 100 &&
      (!draftTo || !draftFrom || draftTo >= draftFrom)
  );

  async function save(event: SubmitEvent) {
    event.preventDefault();
    if (!ready || saving) return;
    saving = true;
    formError = null;
    try {
      const created = await salesPromotionsApi.create({
        branch_id: draftBranch,
        product_id: Number(draftProduct),
        discount_percent: draftPercent,
        valid_from: draftFrom || null,
        valid_to: draftTo || null,
        notes: draftNotes.trim() || null
      });
      notice = `Se creó la promoción del ${formatPercent(created.discount_percent)} para ${created.product_name} en ${created.branch_name}.`;
      formOpen = false;
      draftProduct = '';
      draftPercent = '';
      draftFrom = '';
      draftTo = '';
      draftNotes = '';
      await load();
    } catch (cause) {
      formError = cause instanceof HttpError ? cause.message : 'No se pudo crear la promoción.';
    } finally {
      saving = false;
    }
  }

  async function end(promotion: SalesPromotion) {
    if (endingId) return;
    endingId = promotion.id;
    notice = null;
    loadError = null;
    try {
      await salesPromotionsApi.end(promotion.id);
      notice = `Se terminó la promoción de ${promotion.product_name}.`;
      await load();
    } catch (cause) {
      loadError = cause instanceof HttpError ? cause.message : 'No se pudo terminar la promoción.';
    } finally {
      endingId = null;
    }
  }
</script>

<div class="space-y-5">
  <header class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
    <div>
      <h1 class="text-2xl font-bold tracking-tight text-foreground">Promociones por sucursal</h1>
      <p class="mt-1 max-w-3xl text-sm text-foreground-muted">
        Un porcentaje de descuento para un producto en una sucursal. En las ventas de esa sucursal
        reemplaza a los demás descuentos: el vendedor no puede cambiarlo, no se suman el del cliente
        ni el de volumen, y el documento no admite descuento global. Nunca deja vender bajo el
        costo.
      </p>
    </div>
    {#if canManage && !formOpen}
      <div class="shrink-0"><Button onclick={() => void openForm()}>Nueva promoción</Button></div>
    {/if}
  </header>

  {#if notice}
    <p
      class="rounded-lg border border-success/30 bg-success/10 px-4 py-3 text-sm text-success"
      aria-live="polite"
    >
      {notice}
    </p>
  {/if}

  {#if formOpen}
    <form class="space-y-3 rounded-xl border border-border bg-surface p-4" onsubmit={save}>
      <h2 class="font-semibold text-foreground">Nueva promoción</h2>
      {#if formError}
        <div
          class="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger"
          role="alert"
        >
          {formError}
        </div>
      {/if}
      <div class="grid gap-3 sm:grid-cols-2">
        <label class="text-sm text-foreground-muted"
          >Sucursal
          <select
            class={inputClass}
            value={draftBranch}
            onchange={(e) => (draftBranch = e.currentTarget.value)}
          >
            {#each branches as item (item.id)}
              <option value={item.id}>{item.name}</option>
            {/each}
          </select>
        </label>
        <label class="text-sm text-foreground-muted"
          >Producto
          <select
            class={inputClass}
            value={draftProduct}
            onchange={(e) => (draftProduct = e.currentTarget.value)}
          >
            <option value="">Elige el producto</option>
            {#each products as item (item.id)}
              <option value={String(item.id)}>{item.label}</option>
            {/each}
          </select>
        </label>
        <label class="text-sm text-foreground-muted"
          >Descuento de la promoción (%)
          <input
            class={inputClass}
            type="number"
            min="0.01"
            max="99.99"
            step="any"
            value={draftPercent}
            oninput={(e) => (draftPercent = e.currentTarget.value)}
          />
        </label>
        <label class="text-sm text-foreground-muted"
          >Nota (opcional)
          <input
            class={inputClass}
            maxlength="200"
            value={draftNotes}
            oninput={(e) => (draftNotes = e.currentTarget.value)}
          />
        </label>
        <label class="text-sm text-foreground-muted"
          >Desde (vacío: hoy)
          <input
            class={inputClass}
            type="date"
            value={draftFrom}
            oninput={(e) => (draftFrom = e.currentTarget.value)}
          />
        </label>
        <label class="text-sm text-foreground-muted"
          >Hasta (vacío: sin fecha de fin)
          <input
            class={inputClass}
            type="date"
            value={draftTo}
            oninput={(e) => (draftTo = e.currentTarget.value)}
          />
        </label>
      </div>
      <div class="flex flex-wrap gap-2">
        <Button type="submit" disabled={!ready || saving}
          >{saving ? 'Guardando…' : 'Crear promoción'}</Button
        >
        <Button variant="secondary" onclick={() => (formOpen = false)}>Cancelar</Button>
      </div>
    </form>
  {/if}

  <section class="rounded-xl border border-border bg-surface">
    <div class="flex items-center justify-between border-b border-border px-4 py-3">
      <h2 class="font-semibold text-foreground">Promociones</h2>
      <label class="flex items-center gap-2 text-sm text-foreground-muted">
        <input
          type="checkbox"
          checked={includeEnded}
          onchange={(e) => {
            includeEnded = e.currentTarget.checked;
            void load();
          }}
        />
        Mostrar terminadas
      </label>
    </div>
    {#if loading}
      <div class="space-y-2 p-4" aria-busy="true">
        <div class="skeleton h-9 w-full rounded-md"></div>
        <div class="skeleton h-9 w-full rounded-md"></div>
      </div>
    {:else if loadError}
      <div
        class="m-4 rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
        role="alert"
      >
        {loadError}
        <button class="ml-2 underline" onclick={() => void load()}>Reintentar</button>
      </div>
    {:else if promotions.length === 0}
      <div class="flex flex-col items-center gap-2 p-10 text-center">
        <span
          class="flex h-12 w-12 items-center justify-center rounded-full bg-surface-muted text-lg text-foreground-muted"
          aria-hidden="true">%</span
        >
        <p class="font-medium text-foreground">No hay promociones vigentes ni programadas.</p>
        {#if canManage}
          <Button variant="secondary" onclick={() => void openForm()}
            >Crear la primera promoción</Button
          >
        {/if}
      </div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full min-w-[720px] text-left text-sm">
          <thead class="bg-surface-muted text-xs uppercase text-foreground-muted">
            <tr>
              <th class="px-4 py-3">Producto</th>
              <th class="px-4 py-3">Sucursal</th>
              <th class="px-4 py-3 text-right">Descuento</th>
              <th class="px-4 py-3">Vigencia</th>
              <th class="px-4 py-3">Estado</th>
              <th class="px-4 py-3"><span class="sr-only">Acciones</span></th>
            </tr>
          </thead>
          <tbody class="divide-y divide-border">
            {#each promotions as item (item.id)}
              <tr>
                <td class="px-4 py-3 text-foreground">
                  {item.product_name}
                  <span class="block font-mono text-xs text-foreground-muted"
                    >{item.product_sku}</span
                  >
                </td>
                <td class="px-4 py-3 text-foreground">{item.branch_name}</td>
                <td class="px-4 py-3 text-right font-mono"
                  >{formatPercent(item.discount_percent)}</td
                >
                <td class="px-4 py-3 text-foreground-muted">
                  {formatDay(item.valid_from)} — {item.valid_to
                    ? formatDay(item.valid_to)
                    : 'sin fin'}
                </td>
                <td class="px-4 py-3"
                  ><Badge variant={STATUS[item.status].variant}>{STATUS[item.status].label}</Badge
                  ></td
                >
                <td class="px-4 py-3 text-right">
                  {#if canManage && (item.status === 'current' || item.status === 'scheduled')}
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={endingId === item.id}
                      onclick={() => void end(item)}
                    >
                      {endingId === item.id ? 'Terminando…' : 'Terminar'}
                    </Button>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </section>
</div>
