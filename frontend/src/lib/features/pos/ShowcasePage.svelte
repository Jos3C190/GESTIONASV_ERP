<script lang="ts">
  /**
   * Vitrina de la sucursal: existencias por producto con vencimientos, pasar unidades completas de la
   * bodega a la vitrina y el conteo de cierre que registra la merma.
   */
  import Badge from '#lib/components/ui/Badge.svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { posShowcaseApi } from '#lib/api/pos.ts';
  import { branch } from '#lib/stores/branch.svelte.ts';
  import { permissions } from '#lib/stores/permissions.svelte.ts';
  import type {
    PosShowcase,
    ShowcaseCandidate,
    ShowcaseCount,
    ShowcaseStock
  } from '#lib/types/pos.ts';
  import { formatDate, formatDateTime, formatMoney, idempotencyKey } from './format.ts';

  type Tab = 'stock' | 'open' | 'count';

  let showcase = $state<PosShowcase | null>(null);
  let stock = $state<ShowcaseStock[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let notice = $state<string | null>(null);
  let tab = $state<Tab>('stock');

  // Crear vitrina
  let warehouses = $state<{ id: string; name: string }[]>([]);
  let warehouseId = $state('');
  let creating = $state(false);

  // Pasar a vitrina
  let search = $state('');
  let candidates = $state<ShowcaseCandidate[]>([]);
  let chosen = $state<string[]>([]);
  let loadingCandidates = $state(false);
  let opening = $state(false);
  let openKey = $state(idempotencyKey('vitrina'));

  // Conteo
  let counted = $state<Record<string, string>>({});
  let reasons = $state<Record<string, string>>({});
  let countNotes = $state('');
  let counts = $state<ShowcaseCount[]>([]);
  let saving = $state(false);
  let countKey = $state(idempotencyKey('conteo-vitrina'));
  let actionError = $state<string | null>(null);

  const branchId = $derived(branch.id);
  const canManage = $derived(permissions.hasPermission('pos:registers_manage'));
  const canOperate = $derived(permissions.hasPermission('pos:showcase'));

  function quantity(value: string): string {
    const number = Number(value);
    return Number.isInteger(number)
      ? number.toLocaleString('es-SV')
      : number.toLocaleString('es-SV', { maximumFractionDigits: 3 });
  }

  function parse(value: string | undefined): number | null {
    if (value === undefined || value.trim() === '') return null;
    const text = value.trim().replace(',', '.');
    return /^\d+(\.\d{1,6})?$/.test(text) ? Number(text) : null;
  }

  const countLines = $derived(
    stock
      .filter(
        (item) =>
          counted[item.inventory_item_id] !== undefined && counted[item.inventory_item_id] !== ''
      )
      .map((item) => {
        const value = parse(counted[item.inventory_item_id]);
        const waste = value === null ? null : Number(item.quantity) - value;
        return { item, value, waste };
      })
  );
  const countValid = $derived(
    countLines.length > 0 &&
      countLines.every(
        ({ item, value, waste }) =>
          value !== null &&
          waste !== null &&
          waste >= 0 &&
          (waste === 0 || (reasons[item.inventory_item_id] ?? '').trim().length >= 3)
      )
  );

  async function load() {
    loading = true;
    error = null;
    showcase = null;
    stock = [];
    if (!branchId) {
      loading = false;
      return;
    }
    try {
      showcase = (await posShowcaseApi.list(branchId))[0] ?? null;
      if (showcase) {
        stock = await posShowcaseApi.stock(branchId);
        if (canOperate) counts = await posShowcaseApi.counts(branchId);
      } else if (canManage) {
        warehouses = await posShowcaseApi.warehouseOptions(branchId);
        if (warehouses.length === 1) warehouseId = warehouses[0]!.id;
      }
    } catch (err) {
      error = err instanceof Error ? err.message : 'No se pudo cargar la vitrina.';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    void branchId;
    void load();
  });

  async function create() {
    if (!branchId || !warehouseId) return;
    creating = true;
    actionError = null;
    try {
      await posShowcaseApi.create(branchId, warehouseId);
      notice = 'Vitrina creada. Ya puedes pasar productos a vitrina.';
      await load();
    } catch (err) {
      actionError = err instanceof Error ? err.message : 'No se pudo crear la vitrina.';
    } finally {
      creating = false;
    }
  }

  async function findCandidates() {
    if (!branchId) return;
    loadingCandidates = true;
    actionError = null;
    try {
      candidates = await posShowcaseApi.candidates(branchId, search.trim());
      chosen = chosen.filter((id) => candidates.some((item) => item.handling_unit_id === id));
    } catch (err) {
      actionError = err instanceof Error ? err.message : 'No se pudieron cargar las unidades.';
    } finally {
      loadingCandidates = false;
    }
  }

  $effect(() => {
    if (tab === 'open' && showcase && candidates.length === 0) void findCandidates();
  });

  async function openUnits() {
    if (!branchId || chosen.length === 0) return;
    opening = true;
    actionError = null;
    try {
      const result = await posShowcaseApi.open(branchId, chosen, openKey);
      stock = result.stock;
      notice = `${chosen.length === 1 ? 'Una unidad pasó' : `${chosen.length} unidades pasaron`} a vitrina.`;
      chosen = [];
      openKey = idempotencyKey('vitrina');
      await findCandidates();
      tab = 'stock';
    } catch (err) {
      actionError = err instanceof Error ? err.message : 'No se pudo pasar a vitrina.';
      if (!(err instanceof HttpError && err.status === 0)) openKey = idempotencyKey('vitrina');
    } finally {
      opening = false;
    }
  }

  async function saveCount() {
    if (!branchId || !countValid) return;
    saving = true;
    actionError = null;
    try {
      const result = await posShowcaseApi.count(
        branchId,
        countLines.map(({ item, value }) => ({
          inventory_item_id: item.inventory_item_id,
          counted_quantity: String(value),
          reason: (reasons[item.inventory_item_id] ?? '').trim() || null
        })),
        countNotes.trim() || null,
        countKey
      );
      notice =
        Number(result.waste_cost) > 0
          ? `Conteo ${result.code} registrado: merma de ${formatMoney(result.waste_cost)} al costo.`
          : `Conteo ${result.code} registrado sin merma.`;
      counted = {};
      reasons = {};
      countNotes = '';
      countKey = idempotencyKey('conteo-vitrina');
      await load();
      tab = 'stock';
    } catch (err) {
      actionError = err instanceof Error ? err.message : 'No se pudo registrar el conteo.';
      if (!(err instanceof HttpError && err.status === 0)) {
        countKey = idempotencyKey('conteo-vitrina');
      }
    } finally {
      saving = false;
    }
  }
</script>

<div class="space-y-4">
  {#if notice}
    <div
      class="rounded-xl border border-success/30 bg-success/10 p-3 text-sm text-foreground"
      role="status"
    >
      {notice}
    </div>
  {/if}

  {#if !branchId}
    <div class="rounded-xl border border-border bg-surface p-6 text-sm text-foreground-muted">
      Elige una sucursal en el menú: cada sucursal tiene su propia vitrina.
    </div>
  {:else if loading}
    <div class="space-y-2" aria-label="Cargando vitrina">
      {#each [1, 2, 3] as item (item)}<div class="h-14 rounded-lg skeleton"></div>{/each}
    </div>
  {:else if error}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
      role="alert"
    >
      <p>{error}</p>
      <div class="mt-3">
        <Button variant="secondary" size="sm" onclick={load}>Reintentar</Button>
      </div>
    </div>
  {:else if !showcase}
    <div
      class="flex flex-col items-center rounded-xl border border-border bg-surface p-10 text-center"
    >
      <span
        class="flex h-12 w-12 items-center justify-center rounded-full bg-surface-muted text-foreground-subtle"
        aria-hidden="true"
      >
        <svg
          width="22"
          height="22"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          ><rect x="3" y="4" width="18" height="16" rx="2" /><path
            d="M3 12h18M8 16h2M14 16h2"
          /></svg
        >
      </span>
      <p class="mt-3 font-semibold text-foreground">Esta sucursal todavía no tiene vitrina</p>
      <p class="mt-1 max-w-md text-sm text-foreground-muted">
        La vitrina es la existencia suelta del mostrador: lo que pasa a vitrina se vende por pieza.
      </p>
      {#if canManage}
        {#if warehouses.length === 0}
          <p class="mt-4 text-sm text-foreground-muted">La sucursal no tiene una bodega activa.</p>
        {:else}
          <div class="mt-4 flex flex-wrap items-end justify-center gap-2">
            <label class="text-left text-xs font-medium text-foreground-muted">
              Bodega
              <select
                class="mt-1 block h-10 rounded-lg border border-border bg-surface px-3 text-sm"
                value={warehouseId}
                onchange={(event) =>
                  (warehouseId = (event.currentTarget as HTMLSelectElement).value)}
              >
                <option value="">Elige la bodega</option>
                {#each warehouses as warehouse (warehouse.id)}<option value={warehouse.id}
                    >{warehouse.name}</option
                  >{/each}
              </select>
            </label>
            <Button disabled={!warehouseId || creating} onclick={create}
              >{creating ? 'Creando…' : 'Crear vitrina'}</Button
            >
          </div>
        {/if}
      {:else}
        <p class="mt-4 text-sm text-foreground-muted">
          Pide a quien configura las cajas que la cree.
        </p>
      {/if}
      {#if actionError}<p class="mt-3 text-sm text-danger" role="alert">{actionError}</p>{/if}
    </div>
  {:else}
    <div class="flex flex-wrap items-center justify-between gap-3">
      <p class="text-sm text-foreground-muted">
        {showcase.location_code} · {showcase.warehouse_name}
      </p>
      <div
        class="flex flex-wrap gap-1 rounded-lg border border-border bg-surface-muted p-1"
        role="tablist"
      >
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'stock'}
          class={`rounded-md px-3 py-1.5 text-sm font-medium ${tab === 'stock' ? 'bg-surface text-foreground shadow-sm' : 'text-foreground-muted'}`}
          onclick={() => (tab = 'stock')}>Existencias</button
        >
        {#if canOperate}
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'open'}
            class={`rounded-md px-3 py-1.5 text-sm font-medium ${tab === 'open' ? 'bg-surface text-foreground shadow-sm' : 'text-foreground-muted'}`}
            onclick={() => (tab = 'open')}>Pasar a vitrina</button
          >
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'count'}
            class={`rounded-md px-3 py-1.5 text-sm font-medium ${tab === 'count' ? 'bg-surface text-foreground shadow-sm' : 'text-foreground-muted'}`}
            onclick={() => (tab = 'count')}>Conteo de cierre</button
          >
        {/if}
      </div>
    </div>

    {#if actionError}
      <p
        class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
        role="alert"
      >
        {actionError}
      </p>
    {/if}

    {#if tab === 'stock'}
      {#if stock.length === 0}
        <div
          class="flex flex-col items-center rounded-xl border border-border bg-surface p-10 text-center"
        >
          <p class="font-semibold text-foreground">La vitrina está vacía</p>
          <p class="mt-1 text-sm text-foreground-muted">
            Pasa unidades completas desde la bodega para venderlas por pieza.
          </p>
          {#if canOperate}<div class="mt-4">
              <Button onclick={() => (tab = 'open')}>Pasar a vitrina</Button>
            </div>{/if}
        </div>
      {:else}
        <div class="overflow-x-auto rounded-xl border border-border bg-surface">
          <table class="w-full min-w-[640px] text-sm">
            <thead
              class="bg-surface-muted text-left text-xs uppercase tracking-wider text-foreground-muted"
            >
              <tr
                ><th class="px-4 py-2">Producto</th><th class="px-4 py-2 text-right">Para vender</th
                ><th class="px-4 py-2 text-right">Vencido</th><th class="px-4 py-2"
                  >Próximo vencimiento</th
                ><th class="px-4 py-2 text-right">Unidades abiertas</th></tr
              >
            </thead>
            <tbody class="divide-y divide-border">
              {#each stock as item (item.inventory_item_id)}
                <tr>
                  <td class="px-4 py-2"
                    >{item.product_name}<span class="block text-xs text-foreground-muted"
                      >{item.sku}</span
                    ></td
                  >
                  <td class="px-4 py-2 text-right font-semibold tabular-nums"
                    >{quantity(item.sellable)} {item.unit_symbol}</td
                  >
                  <td class="px-4 py-2 text-right tabular-nums">
                    {#if Number(item.expired) > 0}<Badge variant="danger"
                        >{quantity(item.expired)} {item.unit_symbol}</Badge
                      >{:else}—{/if}
                  </td>
                  <td class="px-4 py-2 tabular-nums">{formatDate(item.next_expiry)}</td>
                  <td class="px-4 py-2 text-right tabular-nums">{item.units.length}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    {:else if tab === 'open'}
      <section
        class="space-y-3 rounded-xl border border-border bg-surface p-4"
        aria-label="Pasar a vitrina"
      >
        <p class="text-sm text-foreground-muted">
          Pasan unidades completas de {showcase.warehouse_name}, primero las que vencen antes. Si
          solo va una parte, fracciónala antes en la bodega.
        </p>
        <form
          class="flex gap-2"
          onsubmit={(event) => {
            event.preventDefault();
            void findCandidates();
          }}
        >
          <input
            class="h-10 flex-1 rounded-lg border border-border bg-surface px-3 text-sm"
            placeholder="Buscar producto, código o unidad"
            bind:value={search}
          />
          <Button type="submit" variant="secondary">Buscar</Button>
        </form>
        {#if loadingCandidates}
          <div class="h-24 rounded-lg skeleton" aria-label="Cargando unidades"></div>
        {:else if candidates.length === 0}
          <p class="text-sm text-foreground-muted">
            No hay unidades completas disponibles en la bodega.
          </p>
        {:else}
          <ul class="divide-y divide-border rounded-lg border border-border">
            {#each candidates as item (item.handling_unit_id)}
              <li>
                <label class="flex cursor-pointer items-center gap-3 px-3 py-2 text-sm">
                  <input
                    type="checkbox"
                    aria-label={`Pasar a vitrina ${item.product_name}, unidad ${item.code}`}
                    checked={chosen.includes(item.handling_unit_id)}
                    onchange={(event) =>
                      (chosen = (event.currentTarget as HTMLInputElement).checked
                        ? [...chosen, item.handling_unit_id]
                        : chosen.filter((id) => id !== item.handling_unit_id))}
                  />
                  <span class="flex-1"
                    >{item.product_name}<span class="block text-xs text-foreground-muted"
                      >{item.code} · {item.location_code}{item.lot_code
                        ? ` · lote ${item.lot_code}`
                        : ''}{item.expiry_date
                        ? ` · vence ${formatDate(item.expiry_date)}`
                        : ''}</span
                    ></span
                  >
                  <span class="font-semibold tabular-nums"
                    >{quantity(item.quantity)} {item.unit_symbol}</span
                  >
                </label>
              </li>
            {/each}
          </ul>
          <div class="flex justify-end">
            <Button disabled={chosen.length === 0 || opening} onclick={openUnits}>
              {opening ? 'Pasando…' : `Pasar ${chosen.length || ''} a vitrina`}
            </Button>
          </div>
        {/if}
      </section>
    {:else}
      <section
        class="space-y-3 rounded-xl border border-border bg-surface p-4"
        aria-label="Conteo de cierre"
      >
        <p class="text-sm text-foreground-muted">
          Cuenta lo que queda en la vitrina. Lo que falta contra el sistema es merma: sale del
          inventario al costo promedio, con su motivo. Deja en blanco lo que no cuentes hoy.
        </p>
        {#if stock.length === 0}
          <p class="text-sm text-foreground-muted">
            La vitrina está vacía: no hay nada que contar.
          </p>
        {:else}
          <div class="overflow-x-auto">
            <table class="w-full min-w-[640px] text-sm">
              <thead class="text-left text-xs uppercase tracking-wider text-foreground-muted">
                <tr
                  ><th class="py-2">Producto</th><th class="py-2 text-right">En sistema</th><th
                    class="py-2 text-right">Contado</th
                  ><th class="py-2 text-right">Merma</th><th class="py-2">Motivo</th></tr
                >
              </thead>
              <tbody class="divide-y divide-border">
                {#each stock as item (item.inventory_item_id)}
                  {@const value = parse(counted[item.inventory_item_id])}
                  {@const waste = value === null ? null : Number(item.quantity) - value}
                  <tr>
                    <td class="py-2 pr-2">{item.product_name}</td>
                    <td class="py-2 text-right tabular-nums"
                      >{quantity(item.quantity)} {item.unit_symbol}</td
                    >
                    <td class="py-2 text-right">
                      <input
                        aria-label={`Contado de ${item.product_name}`}
                        class="h-9 w-24 rounded-lg border border-border bg-surface px-2 text-right text-sm tabular-nums"
                        inputmode="decimal"
                        value={counted[item.inventory_item_id] ?? ''}
                        oninput={(event) =>
                          (counted = {
                            ...counted,
                            [item.inventory_item_id]: (event.currentTarget as HTMLInputElement)
                              .value
                          })}
                      />
                    </td>
                    <td
                      class={`py-2 text-right tabular-nums ${waste !== null && waste > 0 ? 'font-semibold text-danger' : ''}`}
                    >
                      {#if waste === null}—{:else if waste < 0}<span class="text-danger"
                          >Contaste de más</span
                        >{:else}{quantity(String(waste))}{/if}
                    </td>
                    <td class="py-2 pl-2">
                      {#if waste !== null && waste > 0}
                        <input
                          aria-label={`Motivo de la merma de ${item.product_name}`}
                          class="h-9 w-full min-w-40 rounded-lg border border-border bg-surface px-2 text-sm"
                          maxlength="200"
                          placeholder="Vencido, aplastado…"
                          value={reasons[item.inventory_item_id] ?? ''}
                          oninput={(event) =>
                            (reasons = {
                              ...reasons,
                              [item.inventory_item_id]: (event.currentTarget as HTMLInputElement)
                                .value
                            })}
                        />
                      {/if}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
          <label class="block text-sm font-medium text-foreground">
            Notas <span class="font-normal text-foreground-subtle">(opcional)</span>
            <textarea
              class="mt-1 w-full rounded-lg border border-border bg-surface p-2 text-sm"
              rows="2"
              maxlength="300"
              bind:value={countNotes}
            ></textarea>
          </label>
          <div class="flex justify-end">
            <Button disabled={!countValid || saving} onclick={saveCount}
              >{saving ? 'Registrando…' : 'Registrar conteo'}</Button
            >
          </div>
        {/if}

        {#if counts.length}
          <h3 class="pt-2 text-sm font-semibold text-foreground">Conteos anteriores</h3>
          <ul class="divide-y divide-border text-sm">
            {#each counts as item (item.id)}
              <li class="flex flex-wrap justify-between gap-2 py-2">
                <span>{item.code} · {formatDateTime(item.counted_at)} · {item.counted_by_name}</span
                >
                <span
                  class={Number(item.waste_cost) > 0
                    ? 'font-semibold text-danger'
                    : 'text-foreground-muted'}
                >
                  {Number(item.waste_cost) > 0
                    ? `Merma ${formatMoney(item.waste_cost)}`
                    : 'Sin merma'}
                </span>
              </li>
            {/each}
          </ul>
        {/if}
      </section>
    {/if}
  {/if}
</div>
