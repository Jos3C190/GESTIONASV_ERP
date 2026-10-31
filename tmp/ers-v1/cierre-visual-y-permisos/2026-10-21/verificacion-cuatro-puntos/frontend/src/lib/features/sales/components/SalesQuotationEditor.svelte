<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { HttpError } from '$lib/api/client';
  import { salesApi } from '$lib/api/sales';
  import { formatUnitLabel } from '$lib/features/sales/unit-label';
  import { branch } from '$lib/stores/branch.svelte';
  import type { SalesCatalogItem, SalesCustomer, SalesLine, SalesLineInput } from '$lib/types/sales';

  type DraftLine = { key: string; option: SalesCatalogItem | null; unitId: number | null; quantity: string; unitPrice: string; sourceLineId?: string };
  let customers = $state<SalesCustomer[]>([]);
  let catalog = $state<SalesCatalogItem[]>([]);
  let branches = $state(branch.branches.filter((item) => item.is_active));
  let branchId = $state(branch.id ?? '');
  let customerId = $state('');
  let validUntil = $state('');
  let notes = $state('');
  let lines = $state<DraftLine[]>([{ key: crypto.randomUUID(), option: null, unitId: null, quantity: '1', unitPrice: '0.00' }]);
  let loading = $state(true);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let quotation = $state<Awaited<ReturnType<typeof salesApi.quotation>> | null>(null);

  let { quotationId = null }: { quotationId?: string | null } = $props();

  function localDate(days = 0) {
    const date = new Date();
    date.setDate(date.getDate() + days);
    const offset = date.getTimezoneOffset();
    return new Date(date.getTime() - offset * 60_000).toISOString().slice(0, 10);
  }

  onMount(async () => {
    loading = true;
    error = null;
    try {
      branches = branch.branches.filter((item) => item.is_active);
      if (!branchId && branches.length === 1) branchId = branches[0]?.id ?? '';
      const [customerResponse, items] = await Promise.all([
        salesApi.customers({ active: true, size: 100 }), salesApi.catalog()
      ]);
      customers = customerResponse.items;
      catalog = items;
      if (quotationId) {
        quotation = await salesApi.quotation(quotationId);
        if (quotation.status !== 'draft') throw new Error('Esta cotización ya no admite edición.');
        branchId = quotation.branch_id;
        customerId = quotation.customer_id;
        validUntil = quotation.valid_until;
        notes = quotation.notes ?? '';
        lines = quotation.lines.map((line: SalesLine) => {
          const option = catalog.find((item) => item.product_id === line.product_id && item.variant_id === line.variant_id) ?? null;
          return { key: line.id, option, unitId: line.unit_id, quantity: line.quantity, unitPrice: line.unit_price, sourceLineId: line.id };
        });
        if (lines.some((line) => !line.option)) throw new Error('Un producto de esta cotización ya no está disponible en el catálogo. Recarga el documento y solicita apoyo para editarlo.');
      } else {
        validUntil = localDate(7);
      }
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : cause instanceof Error ? cause.message : 'No se pudieron preparar los datos.';
    } finally {
      loading = false;
    }
  });

  function setOption(line: DraftLine, value: string) {
    const option = catalog.find((item) => `${item.product_id}:${item.variant_id ?? ''}` === value) ?? null;
    line.option = option;
    line.unitId = option?.base_unit_id ?? null;
  }

  function addLine() {
    lines = [...lines, { key: crypto.randomUUID(), option: null, unitId: null, quantity: '1', unitPrice: '0.00' }];
  }

  function payloadLines(): SalesLineInput[] {
    return lines.map((line) => {
      if (!line.option || !line.unitId) throw new Error('Selecciona un producto y su presentación en cada renglón.');
      return { product_id: line.option.product_id, variant_id: line.option.variant_id, unit_id: line.unitId, quantity: line.quantity, unit_price: line.unitPrice };
    });
  }

  async function save(event: SubmitEvent) {
    event.preventDefault();
    error = null;
    saving = true;
    try {
      const items = payloadLines();
      if (!customerId) throw new Error('Selecciona un cliente activo.');
      if (!validUntil) throw new Error('Indica la vigencia de la cotización.');
      let saved;
      if (quotationId && quotation) {
        saved = await salesApi.updateQuotation(quotationId, { expected_version: quotation.version, valid_until: validUntil, currency: 'USD', notes: notes || null, lines: items });
      } else {
        if (!branchId) throw new Error('Selecciona la sucursal autorizada del documento.');
        const body = { branch_id: branchId, customer_id: customerId, valid_until: validUntil, currency: 'USD' as const, notes: notes || null, lines: items };
        const fingerprint = JSON.stringify(body);
        const storageKey = 'sales-quotation-create-pending';
        const previous = sessionStorage.getItem(storageKey);
        let idempotencyKey = '';
        if (previous) {
          try {
            const parsed = JSON.parse(previous) as { fingerprint: string; key: string };
            if (parsed.fingerprint === fingerprint) idempotencyKey = parsed.key;
          } catch { /* replace invalid local retry state */ }
        }
        if (!idempotencyKey) {
          idempotencyKey = crypto.randomUUID();
          sessionStorage.setItem(storageKey, JSON.stringify({ fingerprint, key: idempotencyKey }));
        }
        saved = await salesApi.createQuotation(body, idempotencyKey);
        sessionStorage.removeItem(storageKey);
      }
      await goto(`/sales/quotations/${saved.id}`);
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : cause instanceof Error ? cause.message : 'No se pudo guardar la cotización.';
    } finally {
      saving = false;
    }
  }

  function removeLine(key: string) {
    if (lines.length <= 1) return;
    lines = lines.filter((line) => line.key !== key);
  }

  const total = $derived(lines.reduce((sum, line) => sum + (Number(line.quantity) || 0) * (Number(line.unitPrice) || 0), 0));
</script>

<svelte:head><title>{quotationId ? 'Editar cotización' : 'Nueva cotización'} | GestionaSV</title></svelte:head>
<main class="mx-auto max-w-5xl space-y-5 px-4 pb-10 pt-6 sm:px-6">
  <a class="text-sm text-primary hover:underline" href="/sales/quotations">← Cotizaciones de venta</a>
  <header><p class="text-xs font-semibold uppercase tracking-widest text-primary">Ventas · USD</p><h1 class="mt-1 text-2xl font-bold text-foreground">{quotationId ? `Editar ${quotation?.code ?? 'cotización'}` : 'Nueva cotización'}</h1><p class="mt-1 text-sm text-foreground-muted">Los precios se capturan aquí. Los totales los calcula el servidor; esta acción no verifica ni reserva existencias.</p></header>
  {#if error}<div class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger" role="alert">{error}</div>{/if}
  {#if loading}<section class="rounded-xl border border-border bg-surface p-10 text-center text-sm text-foreground-muted">Cargando catálogo y clientes…</section>{:else}
    <form class="space-y-5" onsubmit={save}>
      <section class="grid gap-4 rounded-xl border border-border bg-surface p-5 sm:grid-cols-2">
        <label class="text-sm text-foreground-muted">Cliente activo<select bind:value={customerId} class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-foreground" required><option value="">Selecciona un cliente</option>{#each customers as customer (customer.id)}<option value={customer.id}>{customer.code} · {customer.name}</option>{/each}</select></label>
        <label class="text-sm text-foreground-muted">Sucursal del documento<select bind:value={branchId} class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-foreground" required disabled={!!quotationId}><option value="">Selecciona una sucursal</option>{#each branches as item (item.id)}<option value={item.id}>{item.name}{item.code ? ` · ${item.code}` : ''}</option>{/each}</select></label>
        <label class="text-sm text-foreground-muted">Válida hasta<input bind:value={validUntil} type="date" min={localDate()} required class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-foreground" /></label>
        <label class="text-sm text-foreground-muted">Notas (opcional)<input bind:value={notes} maxlength="4000" class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-foreground" /></label>
      </section>
      <section class="overflow-hidden rounded-xl border border-border bg-surface">
        <div class="flex items-center justify-between border-b border-border p-4"><div><h2 class="font-semibold text-foreground">Productos</h2><p class="mt-1 text-xs text-foreground-muted">Se conserva la unidad elegida y su equivalencia vigente en unidad base.</p></div><button type="button" class="rounded-md border border-border px-3 py-2 text-sm text-foreground" onclick={addLine}>Agregar producto</button></div>
        {#if catalog.length === 0}<p class="p-5 text-sm text-warning">No hay artículos activos y vendibles con identidad de inventario y unidad configuradas.</p>{/if}
        <div class="divide-y divide-border">{#each lines as line, index (line.key)}<div class="grid gap-3 p-4 md:grid-cols-[minmax(220px,2fr)_minmax(160px,1.2fr)_110px_130px_auto] md:items-end">
          <label class="text-xs font-medium text-foreground-muted">Producto<select class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground" value={line.option ? `${line.option.product_id}:${line.option.variant_id ?? ''}` : ''} onchange={(event) => setOption(line, event.currentTarget.value)} required><option value="">Selecciona producto</option>{#each catalog as item (`${item.product_id}:${item.variant_id ?? ''}`)}<option value={`${item.product_id}:${item.variant_id ?? ''}`}>{item.sku} · {item.name}</option>{/each}</select></label>
          <label class="text-xs font-medium text-foreground-muted">Unidad<select class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground" bind:value={line.unitId} required disabled={!line.option}><option value="">Selecciona unidad</option>{#each line.option?.units ?? [] as unit (unit.unit_id)}<option value={unit.unit_id}>{unit.name} · ×{unit.factor} base</option>{/each}</select></label>
          <label class="text-xs font-medium text-foreground-muted">Cantidad<input class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground" type="number" min="0.000001" step="0.000001" bind:value={line.quantity} required /></label>
          <label class="text-xs font-medium text-foreground-muted">Precio unitario (USD)<input class="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground" type="number" min="0" step="0.000001" bind:value={line.unitPrice} required /></label>
          <button type="button" class="h-10 rounded-md border border-border px-3 text-sm text-foreground-muted disabled:opacity-30" aria-label={`Quitar producto ${index + 1}`} disabled={lines.length <= 1} onclick={() => removeLine(line.key)}>Quitar</button>
          {#if line.option && line.unitId}<p class="text-xs text-foreground-muted md:col-span-5">{line.option.name} · Cantidad base estimada: {((Number(line.quantity) || 0) * Number(line.option.units.find((unit) => unit.unit_id === Number(line.unitId))?.factor ?? 1)).toFixed(6)} {formatUnitLabel(line.option.base_unit_name)}</p>{/if}
        </div>{/each}</div>
        <div class="flex flex-col gap-2 border-t border-border bg-surface-muted p-4 text-right"><p class="text-xs text-foreground-muted">Estimación visual; el servidor calcula y redondea cada renglón a centavos.</p><p class="text-lg font-semibold text-foreground">Total estimado: USD {total.toFixed(2)}</p></div>
      </section>
      <div class="flex flex-wrap justify-end gap-2"><a class="rounded-md border border-border px-4 py-2 text-sm text-foreground" href={quotationId ? `/sales/quotations/${quotationId}` : '/sales/quotations'}>Cancelar</a><button class="rounded-md bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50" disabled={saving || loading || customers.length === 0 || catalog.length === 0}>{saving ? 'Guardando…' : 'Guardar borrador'}</button></div>
    </form>
  {/if}
</main>
