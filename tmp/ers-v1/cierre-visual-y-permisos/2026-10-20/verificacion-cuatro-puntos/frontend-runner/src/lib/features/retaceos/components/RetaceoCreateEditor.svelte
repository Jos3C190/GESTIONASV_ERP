<script lang="ts">
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { purchasesApi } from '$lib/api/purchases';
  import { retaceosApi } from '$lib/api/retaceos';
  import CustomsReferencePanel from '$lib/features/retaceos/components/CustomsReferencePanel.svelte';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { Purchase } from '$lib/types/purchase';

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

    try {
      const current = await purchasesApi.get(currentPurchaseId);

      if (sequence !== requestSequence) return;

      purchase = current;
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

    try {
      const created = await retaceosApi.create({
        purchase_id: purchase.id,
        total_freight: '0',
        total_expenses: '0',
        total_dai: '0',
        import_vat: '0',
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
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
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
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
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
        class="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
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

    <CustomsReferencePanel />

    <form
      class="space-y-5"
      onsubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <article class="space-y-4 rounded-xl border border-border bg-surface p-4">
        <div class="rounded-xl border border-primary/20 bg-primary/5 p-4">
          <h2 class="font-semibold text-foreground">
            Siguiente paso: registrar costos y comprobantes
          </h2>
          <p class="mt-1 text-sm leading-6 text-foreground-muted">
            Al crear el borrador se copiarán los gastos y comprobantes de la orden de compra. En la
            siguiente pantalla podrás agregar gastos reales, adjuntar sus documentos y asignar cada
            monto manualmente a los productos aceptados. El IVA de importación se guarda aparte y no
            aumenta el costo aterrizado.
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
            class="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none disabled:opacity-60"
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
