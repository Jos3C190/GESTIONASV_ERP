<script lang="ts">
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { purchasesApi } from '$lib/api/purchases';
  import { catalogApi } from '$lib/api/catalog';
  import { retaceosApi } from '$lib/api/retaceos';
  import CustomsReferencePanel from '$lib/features/retaceos/components/CustomsReferencePanel.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { Purchase } from '$lib/types/purchase';
  import type { RetaceoImportData } from '$lib/types/retaceo';
  import RetaceoImportFields from './RetaceoImportFields.svelte';
  import RetaceoFixedAmounts from './RetaceoFixedAmounts.svelte';
  import type { FixedAmounts } from '../manual-costs';

  let { purchaseId }: { purchaseId: string } = $props();

  const PURCHASE_STATUS_LABELS: Record<Purchase['status'], string> = {
    draft: 'Borrador',
    received: 'Recibida',
    verified: 'Verificada',
    cancelled: 'Cancelada',
    closed: 'Cerrada'
  };

  let purchase = $state<Purchase | null>(null);
  let notes = $state('');
  let importData = $state<RetaceoImportData>({
    origin_country: null,
    import_invoice_number: null,
    import_invoice_date: null,
    import_policy_number: null,
    import_policy_date: null
  });
  let fobAmounts = $state<Record<string, string>>({});
  const manualFob = true;
  let fixedAmounts = $state<FixedAmounts>({ freight: '', dai: '', vat: '' });
  let receivedLines = $derived(
    purchase?.details.filter(
      (line) => Number(line.quantity_accepted ?? line.quantity_received) > 0
    ) ?? []
  );
  let productLabels = $state<Map<number, string>>(new Map());
  let loading = $state(true);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let requestSequence = 0;

  let canManage = $derived(permissions.hasPermission('retaceos:manage'));

  function errorMessage(cause: unknown, fallback: string): string {
    if (cause instanceof HttpError) return cause.message;
    if (cause instanceof Error && cause.message.trim()) return cause.message;
    return fallback;
  }

  function formatMoney(value: string, currency: string): string {
    const amount = Number(value);
    if (!Number.isFinite(amount)) return value;

    return new Intl.NumberFormat('es-SV', {
      style: 'currency',
      currency
    }).format(amount);
  }

  async function load(currentPurchaseId: string) {
    const sequence = ++requestSequence;
    loading = true;
    error = null;
    purchase = null;
    notes = '';
    fixedAmounts = { freight: '', dai: '', vat: '' };
    importData = {
      origin_country: null,
      import_invoice_number: null,
      import_invoice_date: null,
      import_policy_number: null,
      import_policy_date: null
    };

    try {
      const current = await purchasesApi.get(currentPurchaseId);

      if (sequence !== requestSequence) return;

      purchase = current;
      importData = {
        ...importData,
        import_invoice_number: current.supplier_invoice_number,
        import_invoice_date: current.supplier_invoice_date
      };
      fobAmounts = {};
      const products = await Promise.all(
        [...new Set(current.details.map((line) => line.product_id))].map((id) =>
          catalogApi.getProduct(id).catch(() => null)
        )
      );
      if (sequence !== requestSequence) return;
      productLabels = new Map(
        products
          .filter((product) => product !== null)
          .map((product) => [product.id_product, `${product.sku} · ${product.name}`])
      );
    } catch (cause: unknown) {
      if (sequence !== requestSequence) return;

      purchase = null;
      error = errorMessage(cause, 'No se pudo cargar la compra origen.');
    } finally {
      if (sequence === requestSequence) loading = false;
    }
  }

  async function submit() {
    if (!canManage || !purchase || saving) return;

    saving = true;
    error = null;
    if (receivedLines.length === 0) {
      error = 'Esta recepción no tiene cantidades elegibles para retaceo.';
      saving = false;
      return;
    }
    if (
      Object.values(fixedAmounts).some(
        (value) => !value.trim() || !Number.isFinite(Number(value)) || Number(value) < 0
      )
    ) {
      error = 'Completa flete, DAI e IVA; escribe 0 cuando no apliquen.';
      saving = false;
      return;
    }

    if (
      manualFob &&
      receivedLines.some(
        (line) =>
          !fobAmounts[line.id]?.trim() ||
          !Number.isFinite(Number(fobAmounts[line.id])) ||
          Number(fobAmounts[line.id]) <= 0
      )
    ) {
      error = 'Escribe el FOB documentado de cada producto; debe ser mayor que cero.';
      saving = false;
      return;
    }

    try {
      const created = await retaceosApi.create({
        purchase_id: purchase.id,
        import_data: importData,
        ...(manualFob
          ? {
              fob_lines: receivedLines.map((line) => ({
                purchase_detail_id: line.id,
                amount: fobAmounts[line.id] ?? ''
              }))
            }
          : {}),
        total_freight: fixedAmounts.freight,
        total_expenses: '0',
        total_dai: fixedAmounts.dai,
        import_vat: fixedAmounts.vat,
        notes: notes.trim() || null
      });

      await goto(`/retaceos/${created.id}/edit`);
    } catch (cause: unknown) {
      error = errorMessage(cause, 'No se pudo crear el retaceo.');
    } finally {
      saving = false;
    }
  }

  function retry() {
    if (purchaseId) void load(purchaseId);
  }

  $effect(() => {
    const currentPurchaseId = purchaseId;

    if (!canManage) {
      loading = false;
      return;
    }

    if (!currentPurchaseId) {
      purchase = null;
      loading = false;
      error = 'Selecciona una compra origen para crear el retaceo.';
      return;
    }

    void load(currentPurchaseId);
  });
</script>

<section class="space-y-5">
  <div>
    <a
      href={purchaseId ? `/purchases/${purchaseId}` : '/retaceos'}
      class="text-sm font-medium text-primary hover:underline"
    >
      ← Volver
    </a>
  </div>

  {#if !canManage}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-foreground"
      role="alert"
    >
      No tienes permiso para gestionar retaceos.
    </div>
  {:else if loading}
    <div class="space-y-4" aria-label="Cargando compra origen">
      <div class="skeleton h-28 rounded-xl"></div>
      <div class="skeleton h-72 rounded-xl"></div>
    </div>
  {:else if !purchase}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-foreground"
      role="alert"
    >
      <div class="flex flex-wrap items-center justify-between gap-3">
        <span>{error ?? 'No se pudo cargar la compra origen.'}</span>

        {#if purchaseId}
          <Button size="sm" variant="secondary" onclick={retry}>Reintentar</Button>
        {/if}
      </div>
    </div>
  {:else}
    <header>
      <p class="text-sm font-medium text-primary">Retaceo</p>

      <h1 class="text-2xl font-semibold tracking-tight text-foreground">Nuevo retaceo</h1>

      <p class="mt-1 text-sm text-foreground-muted">
        Registra los costos de importación asociados a la compra {purchase.code}.
      </p>
    </header>

    {#if error}
      <div
        class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-foreground"
        role="alert"
      >
        {error}
      </div>
    {/if}

    <article class="rounded-xl border border-border bg-surface p-4">
      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div>
          <p class="text-xs font-medium uppercase tracking-wide text-foreground-muted">
            Compra origen
          </p>

          <a
            href={`/purchases/${purchase.id}`}
            class="mt-2 inline-block font-medium text-primary hover:underline"
          >
            {purchase.code}
          </a>
        </div>

        <div>
          <p class="text-xs font-medium uppercase tracking-wide text-foreground-muted">
            Estado compra
          </p>
          <p class="mt-2 font-medium text-foreground">
            {PURCHASE_STATUS_LABELS[purchase.status]}
          </p>
        </div>

        <div>
          <p class="text-xs font-medium uppercase tracking-wide text-foreground-muted">
            Subtotal compra
          </p>
          <p class="mt-2 font-medium text-foreground">
            {formatMoney(purchase.subtotal, purchase.currency)}
          </p>
        </div>

        <div>
          <p class="text-xs font-medium uppercase tracking-wide text-foreground-muted">Moneda</p>
          <p class="mt-2 font-medium text-foreground">{purchase.currency}</p>
        </div>
      </div>
    </article>

    <details class="rounded-xl border border-border bg-surface p-4">
      <summary
        class="cursor-pointer rounded text-sm font-medium text-foreground focus-visible:ring-2 focus-visible:ring-primary"
        >Consultar referencias de aduana y DAI</summary
      >
      <div class="mt-4"><CustomsReferencePanel /></div>
    </details>

    {#if !['retaceo_before_inventory', 'placement_before_inventory'].includes(purchase.inventory_workflow ?? '')}
      <div
        class="rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm leading-6 text-foreground"
        role="note"
      >
        Esta recepción pertenece al flujo anterior y puede estar en inventario. Si corriges su FOB,
        explica el importe anterior, el correcto y el respaldo en Notas (mínimo 20 caracteres). Al
        aplicar el retaceo se añadirá un ajuste de valor; se conserva la recepción original y no se
        suman unidades otra vez.
      </div>
    {/if}

    <form
      class="space-y-5"
      onsubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      {#if manualFob}
        <RetaceoImportFields
          value={importData}
          oninput={(value) => (importData = value)}
          disabled={saving}
          invoiceLocked
        />
        <article class="space-y-4 rounded-xl border border-border bg-surface p-4">
          <h2 class="font-semibold text-foreground">FOB documentado por producto</h2>
          <p class="max-w-prose text-sm leading-6 text-foreground-muted">
            Importe total documentado de cada producto, sin flete ni DAI.
          </p>
          {#each receivedLines as line, index (line.id)}
            <label class="block rounded-lg border border-border p-4">
              <span class="block text-sm font-medium text-foreground"
                >{productLabels.get(line.product_id) ?? `Producto de la línea ${index + 1}`}</span
              >
              <span class="mt-1 block text-xs text-foreground-muted"
                >Cantidad: {line.quantity_received} · Subtotal: {formatMoney(
                  line.subtotal,
                  purchase.currency
                )} · Descuento: {formatMoney(line.discount, purchase.currency)} · Impuesto de compra:
                {formatMoney(line.tax_amount, purchase.currency)}</span
              >
              <span class="mb-1 mt-3 block text-xs font-medium text-foreground"
                >FOB total de la línea ({purchase.currency})</span
              >
              <input
                type="number"
                required
                min="0.000001"
                step="0.000001"
                value={fobAmounts[line.id] ?? ''}
                oninput={(event) => (fobAmounts[line.id] = event.currentTarget.value)}
                disabled={saving}
                class="h-10 w-full rounded-lg border border-border-control bg-surface px-3 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              />
            </label>
          {/each}
        </article>
      {/if}
      <RetaceoFixedAmounts
        value={fixedAmounts}
        currency={purchase.currency}
        disabled={saving}
        oninput={(key, value) => (fixedAmounts[key] = value)}
      />
      <article class="space-y-4 rounded-xl border border-border bg-surface p-4">
        <div class="rounded-xl border border-primary/20 bg-primary/5 p-4">
          <h2 class="font-semibold text-foreground">
            Siguiente paso: registrar costos y comprobantes
          </h2>
          <p class="mt-1 max-w-prose text-sm leading-6 text-foreground-muted">
            Guarda para desglosar otros gastos y, si lo deseas, adjuntar comprobantes. El
            presupuesto no se carga automáticamente.
          </p>
        </div>

        <label class="block space-y-1.5 text-sm font-medium text-foreground">
          <span>Notas</span>

          <textarea
            aria-label="Notas"
            rows="3"
            maxlength="4000"
            bind:value={notes}
            disabled={saving}
            class="w-full rounded-md border border-border-control bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none disabled:opacity-60"
          ></textarea>
        </label>
      </article>

      <div class="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <a
          href={`/purchases/${purchase.id}`}
          class="inline-flex h-10 items-center justify-center rounded-lg border border-border bg-surface px-4 text-sm font-medium text-foreground hover:bg-surface-muted"
        >
          Cancelar
        </a>

        <Button type="submit" disabled={saving}>
          {saving ? 'Creando…' : 'Crear retaceo'}
        </Button>
      </div>
    </form>
  {/if}
</section>
