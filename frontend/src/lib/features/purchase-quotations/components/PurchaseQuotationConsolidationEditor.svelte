<script lang="ts">
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import Card from '$lib/components/ui/Card.svelte';
  import { HttpError } from '$lib/api/client';
  import { purchaseConsolidationsApi } from '$lib/api/purchase-consolidations';
  import { purchaseQuotationsApi } from '$lib/api/purchase-quotations';
  import { suppliersApi } from '$lib/api/suppliers';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { Currency, Supplier } from '$lib/types/supplier';
  import type { PurchaseConsolidation, ConsolidationLine } from '$lib/types/purchase-consolidation';

  let { consolidationId }: { consolidationId: string } = $props();

  let consolidation = $state<PurchaseConsolidation | null>(null);
  let suppliers = $state<Supplier[]>([]);
  let currencies = $state<Currency[]>([]);
  let selectedSupplierId = $state('');
  let currency = $state('USD');
  let selectedLineIds = $state<string[]>([]);
  let notes = $state('');
  let loading = $state(true);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let loadGeneration = 0;

  let canManage = $derived(
    permissions.hasPermission('purchase_requests:read') &&
      permissions.hasPermission('purchase_quotations:manage')
  );
  let eligibleLines = $derived(
    (consolidation?.lines ?? []).filter((line) => Number(line.total_quantity) > 0)
  );
  let allSelected = $derived(
    eligibleLines.length > 0 && eligibleLines.every((line) => selectedLineIds.includes(line.id))
  );

  function message(cause: unknown): string {
    if (cause instanceof HttpError) return cause.message;
    if (cause instanceof Error && cause.message.trim()) return cause.message;
    return 'No se pudo preparar la RFQ.';
  }

  function formatQuantity(value: string): string {
    return new Intl.NumberFormat('es-SV', { maximumFractionDigits: 6 }).format(Number(value));
  }

  function toggleLine(lineId: string, checked: boolean) {
    selectedLineIds = checked
      ? [...new Set([...selectedLineIds, lineId])]
      : selectedLineIds.filter((id) => id !== lineId);
  }

  function selectAll(checked: boolean) {
    selectedLineIds = checked ? eligibleLines.map((line) => line.id) : [];
  }

  async function load() {
    const current = ++loadGeneration;
    loading = true;
    error = null;
    try {
      const [loaded, suppliersPage, activeCurrencies] = await Promise.all([
        purchaseConsolidationsApi.get(consolidationId),
        suppliersApi.listSuppliers({ active_only: true, page: 1, size: 100 }),
        suppliersApi.currencies()
      ]);
      if (current !== loadGeneration) return;
      consolidation = loaded;
      suppliers = suppliersPage.items.filter(
        (supplier) => supplier.is_active && supplier.supplier_status === 'approved'
      );
      currencies = activeCurrencies.filter((option) => option.is_active);
      selectedLineIds = loaded.lines
        .filter((line) => Number(line.total_quantity) > 0)
        .map((line) => line.id);
      if (!currencies.some((option) => option.code === currency)) {
        currency = currencies[0]?.code ?? '';
      }
    } catch (cause: unknown) {
      if (current !== loadGeneration) return;
      consolidation = null;
      suppliers = [];
      currencies = [];
      error = message(cause);
    } finally {
      if (current === loadGeneration) loading = false;
    }
  }

  async function submit() {
    if (!consolidation || saving || !canManage) return;
    if (consolidation.status === 'cancelled' || consolidation.status === 'closed') {
      error = consolidation.status === 'closed'
        ? 'El consolidado está cerrado; ya no puedes preparar nuevas RFQ.'
        : 'No puedes preparar una RFQ desde un consolidado cancelado.';
      return;
    }
    if (!selectedSupplierId) {
      error = 'Selecciona el proveedor que recibirá esta solicitud.';
      return;
    }
    if (!currency) {
      error = 'Selecciona una moneda activa.';
      return;
    }
    if (selectedLineIds.length === 0) {
      error = 'Selecciona al menos un producto con cantidad vigente.';
      return;
    }

    saving = true;
    error = null;
    try {
      const quotation = await purchaseQuotationsApi.createFromConsolidation(consolidation.id, {
        supplier_id: Number(selectedSupplierId),
        currency,
        consolidation_line_ids: selectedLineIds,
        notes: notes.trim() || null
      });
      await goto(`/purchase-quotations/${quotation.id}?consolidation_id=${consolidation.id}`);
    } catch (cause: unknown) {
      error = message(cause);
    } finally {
      saving = false;
    }
  }

  $effect(() => {
    const id = consolidationId;
    if (id && canManage) void load();
    else loading = false;
  });
</script>

<div class="min-h-full bg-background px-4 pb-8 pt-4 sm:px-6 sm:pt-6 md:px-8 md:pt-8">
  <header class="mb-6 flex items-start gap-3 border-b border-border pb-4">
    <a
      href={consolidationId ? `/purchase-consolidations/${consolidationId}` : '/purchase-requests'}
      class="flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-foreground-muted hover:bg-surface-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      aria-label="Volver al consolidado"
    >
      <span aria-hidden="true">←</span>
    </a>
    <div class="min-w-0">
      <p class="text-xs font-semibold uppercase tracking-wide text-primary">Solicitud al proveedor</p>
      <h1 class="mt-1 text-2xl font-semibold tracking-tight text-foreground">Preparar RFQ</h1>
      <p class="mt-1 max-w-3xl text-sm text-foreground-muted">
        Elige proveedor y productos. Se guardará una copia de las cantidades actuales del consolidado; después podrás descargarla para enviarla.
      </p>
    </div>
  </header>

  {#if !canManage}
    <div class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger" role="alert">
      Necesitas permiso para consultar compras y gestionar cotizaciones.
    </div>
  {:else if loading}
    <div class="space-y-4" role="status" aria-label="Cargando consolidado y proveedores">
      <div class="skeleton h-32 rounded-xl"></div>
      <div class="skeleton h-64 rounded-xl"></div>
    </div>
  {:else if error && !consolidation}
    <div class="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger" role="alert">
      <span>{error}</span>
      <Button size="sm" variant="secondary" onclick={() => void load()}>Reintentar</Button>
    </div>
  {:else if consolidation}
    {#if error}
      <div class="mb-4 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert">{error}</div>
    {/if}

    {#if consolidation.status === 'cancelled' || consolidation.status === 'closed'}
      <div class="rounded-xl border border-border bg-surface p-5" role="status">
        <h2 class="font-semibold text-foreground">{consolidation.status === 'closed' ? 'Consolidado cerrado' : 'Consolidado cancelado'}</h2>
        <p class="mt-1 text-sm text-foreground-muted">{consolidation.status === 'closed' ? 'La gestión del consolidado terminó. No se pueden crear nuevas solicitudes a proveedores; puedes continuar con las órdenes de compra existentes.' : 'No se pueden crear nuevas solicitudes a proveedores desde este consolidado.'}</p>
      </div>
    {:else}
      <form
        class="space-y-5"
        onsubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <Card class="space-y-4 p-5">
          <div>
            <h2 class="font-semibold text-foreground">Datos de la RFQ</h2>
            <p class="mt-1 text-sm text-foreground-muted">Origen: {consolidation.code} · versión asignada automáticamente por proveedor.</p>
          </div>
          <div class="grid gap-4 sm:grid-cols-2">
            <label class="block text-sm font-medium text-foreground" for="rfq-supplier">
              Proveedor <span class="text-danger">*</span>
              <select
                id="rfq-supplier"
                bind:value={selectedSupplierId}
                required
                class="mt-1 h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              >
                <option value="">Selecciona un proveedor</option>
                {#each suppliers as supplier (supplier.id_supplier)}
                  <option value={String(supplier.id_supplier)}>{supplier.code} · {supplier.name}</option>
                {/each}
              </select>
              {#if suppliers.length === 0}
                <span class="mt-1 block text-xs text-warning">No hay proveedores activos y aprobados. Revisa el catálogo de proveedores.</span>
              {/if}
            </label>
            <label class="block text-sm font-medium text-foreground" for="rfq-currency">
              Moneda <span class="text-danger">*</span>
              <select
                id="rfq-currency"
                bind:value={currency}
                disabled={currencies.length === 0}
                required
                class="mt-1 h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              >
                {#each currencies as option (option.code)}
                  <option value={option.code}>{option.code} · {option.name}</option>
                {/each}
              </select>
              {#if currencies.length === 0}
                <span class="mt-1 block text-xs text-warning">No hay monedas activas. Activa una moneda en el catálogo para preparar la RFQ.</span>
              {/if}
            </label>
          </div>
          <label class="block text-sm font-medium text-foreground" for="rfq-notes">
            Nota para el proveedor
            <textarea
              id="rfq-notes"
              bind:value={notes}
              maxlength="4000"
              rows="3"
              placeholder="Plazo de respuesta, condiciones o indicaciones para cotizar"
              class="mt-1 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            ></textarea>
          </label>
        </Card>

        <Card class="overflow-hidden p-0">
          <div class="flex flex-wrap items-center justify-between gap-3 border-b border-border p-4">
            <div>
              <h2 class="font-semibold text-foreground">Productos para cotizar</h2>
              <p class="mt-1 text-sm text-foreground-muted">Las cantidades son de solo lectura y quedan copiadas en esta versión.</p>
            </div>
            <label class="flex min-h-10 cursor-pointer items-center gap-2 rounded-md px-2 text-sm font-medium text-foreground hover:bg-surface-muted">
              <input type="checkbox" checked={allSelected} onchange={(event) => selectAll((event.currentTarget as HTMLInputElement).checked)} class="h-4 w-4 accent-primary" />
              Seleccionar todos
            </label>
          </div>

          {#if eligibleLines.length === 0}
            <div class="p-8 text-center">
              <p class="font-medium text-foreground">No hay productos con cantidad para cotizar</p>
              <p class="mt-1 text-sm text-foreground-muted">Vuelve al consolidado y agrega una solicitud o demanda central.</p>
            </div>
          {:else}
            <ul class="divide-y divide-border">
              {#each eligibleLines as line (line.id)}
                {@const checked = selectedLineIds.includes(line.id)}
                <li>
                  <label class="flex cursor-pointer items-start gap-3 p-4 hover:bg-surface-muted/40">
                    <input
                      type="checkbox"
                      checked={checked}
                      onchange={(event) => toggleLine(line.id, (event.currentTarget as HTMLInputElement).checked)}
                      class="mt-1 h-4 w-4 shrink-0 accent-primary"
                    />
                    <span class="min-w-0 flex-1">
                      <span class="block break-words font-medium text-foreground">{line.product_name}</span>
                      <span class="mt-1 block font-mono text-xs text-foreground-muted">{line.product_sku} · {line.unit_name}</span>
                      <span class="mt-3 grid gap-2 text-xs sm:grid-cols-3">
                        <span class="rounded-md bg-surface-muted px-2.5 py-2 text-foreground-muted">Sucursales: <strong class="font-mono text-foreground">{formatQuantity(line.branch_quantity)}</strong></span>
                        <span class="rounded-md bg-surface-muted px-2.5 py-2 text-foreground-muted">Bodega central: <strong class="font-mono text-foreground">{formatQuantity(line.central_quantity)}</strong></span>
                        <span class="rounded-md border border-primary/20 bg-primary/5 px-2.5 py-2 text-foreground-muted">Cantidad enviada: <strong class="font-mono text-primary">{formatQuantity(line.total_quantity)} {line.unit_name}</strong></span>
                      </span>
                    </span>
                  </label>
                  {#if checked && line.sources.length > 0}
                    <details class="ml-10 mr-4 mb-3 rounded-lg border border-border bg-surface-muted/30 px-3 py-2">
                      <summary class="cursor-pointer text-xs font-medium text-primary">Ver origen de sucursal ({line.sources.length})</summary>
                      <ul class="mt-2 space-y-1 text-xs text-foreground-muted">
                        {#each line.sources as source (source.id)}
                          <li class="flex flex-wrap justify-between gap-2">
                            <span>{source.request_code} · {source.branch_name ?? 'Sucursal'} · {source.warehouse_name ?? 'Almacén'}</span>
                            <span class="font-mono">{formatQuantity(source.included_quantity)} {line.unit_name}</span>
                          </li>
                        {/each}
                      </ul>
                    </details>
                  {/if}
                </li>
              {/each}
            </ul>
          {/if}
        </Card>

        <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <a
            href={`/purchase-consolidations/${consolidation.id}`}
            class="inline-flex min-h-10 items-center justify-center rounded-lg border border-border px-4 text-sm font-medium text-foreground hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            Cancelar
          </a>
          <Button type="submit" disabled={saving || eligibleLines.length === 0 || suppliers.length === 0 || currencies.length === 0}>
            {saving ? 'Creando RFQ…' : 'Crear borrador RFQ'}
          </Button>
        </div>
      </form>
    {/if}
  {/if}
</div>
