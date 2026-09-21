<script lang="ts">
  import { goto } from '$app/navigation';
  import Button from '$lib/components/ui/Button.svelte';
  import { HttpError } from '$lib/api/client';
  import { purchasesApi } from '$lib/api/purchases';
  import { retaceosApi } from '$lib/api/retaceos';
  import { permissions } from '$lib/stores/permissions.svelte';
  import type { Retaceo } from '$lib/types/retaceo';

  let { retaceoId }: { retaceoId: string } = $props();

  let item = $state<Retaceo | null>(null);
  let purchaseLabel = $state('');
  let totalFreight = $state('');
  let totalExpenses = $state('');
  let totalDai = $state('');
  let importVat = $state('');
  let notes = $state('');
  let loading = $state(true);
  let saving = $state(false);
  let editable = $state(true);
  let error = $state<string | null>(null);
  let validation = $state<Record<string, string>>({});
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

  async function load(currentRetaceoId: string) {
    const sequence = ++requestSequence;
    loading = true;
    editable = true;
    error = null;
    validation = {};

    try {
      const current = await retaceosApi.get(currentRetaceoId);

      if (sequence !== requestSequence) return;

      item = current;

      if (current.status !== 'draft') {
        editable = false;
        error = 'Solo los retaceos en borrador pueden editarse.';
        return;
      }

      totalFreight = current.total_freight;
      totalExpenses = current.total_expenses;
      totalDai = current.total_dai;
      importVat = current.import_vat;
      notes = current.notes ?? '';

      const purchase = await purchasesApi.get(current.purchase_id).catch(() => null);

      if (sequence !== requestSequence) return;

      purchaseLabel = purchase?.code ?? current.purchase_id;
    } catch (cause: unknown) {
      if (sequence !== requestSequence) return;

      item = null;
      purchaseLabel = '';
      editable = false;
      error = errorMessage(cause, 'No se pudo cargar el borrador de retaceo.');
    } finally {
      if (sequence === requestSequence) loading = false;
    }
  }

  function validateAmount(
    value: string,
    field: string,
    label: string,
    next: Record<string, string>
  ) {
    const amount = Number(value);

    if (!value.trim() || !Number.isFinite(amount) || amount < 0) {
      next[field] = `${label} debe ser un valor mayor o igual a cero.`;
    }
  }

  function validate(): boolean {
    const next: Record<string, string> = {};

    validateAmount(totalFreight, 'totalFreight', 'El flete', next);
    validateAmount(totalExpenses, 'totalExpenses', 'Los gastos', next);
    validateAmount(totalDai, 'totalDai', 'El DAI', next);
    validateAmount(importVat, 'importVat', 'El IVA de importación', next);

    validation = next;
    return Object.keys(next).length === 0;
  }

  async function submit() {
    if (!canManage || !editable || saving || !item || !validate()) return;

    saving = true;
    error = null;

    try {
      const updated = await retaceosApi.update(item.id, {
        total_freight: totalFreight,
        total_expenses: totalExpenses,
        total_dai: totalDai,
        import_vat: importVat,
        notes: notes.trim() || null
      });

      await goto(`/retaceos/${updated.id}`);
    } catch (cause: unknown) {
      error = errorMessage(cause, 'No se pudo actualizar el borrador de retaceo.');
    } finally {
      saving = false;
    }
  }

  function retry() {
    if (retaceoId) void load(retaceoId);
  }

  $effect(() => {
    const currentRetaceoId = retaceoId;

    if (canManage && currentRetaceoId) {
      void load(currentRetaceoId);
    } else {
      loading = false;
    }
  });
</script>

<section class="space-y-5">
  <div>
    <a
      href={retaceoId ? `/retaceos/${retaceoId}` : '/retaceos'}
      class="text-sm font-medium text-primary hover:underline"
    >
      ← Volver al retaceo
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
    <div class="space-y-4" aria-label="Cargando formulario de retaceo">
      <div class="skeleton h-28 rounded-xl"></div>
      <div class="skeleton h-72 rounded-xl"></div>
    </div>
  {:else if !editable}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
      role="alert"
    >
      <div class="flex flex-wrap items-center justify-between gap-3">
        <span>{error ?? 'Este retaceo no puede editarse.'}</span>

        {#if retaceoId}
          <Button size="sm" variant="secondary" onclick={retry}>Reintentar</Button>
        {/if}
      </div>
    </div>
  {:else if item}
    <header>
      <p class="text-sm font-medium text-primary">Retaceo</p>

      <h1 class="text-2xl font-semibold tracking-tight text-foreground">
        Editar {item.code}
      </h1>

      <p class="mt-1 text-sm text-foreground-muted">
        Modifica los costos mientras el retaceo permanezca en borrador.
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
      <div class="grid gap-4 md:grid-cols-3">
        <div>
          <p class="text-xs font-medium uppercase tracking-wide text-foreground-muted">
            Compra origen
          </p>

          <a
            href={`/purchases/${item.purchase_id}`}
            class="mt-2 inline-block font-medium text-primary hover:underline"
          >
            {purchaseLabel || item.purchase_id}
          </a>
        </div>

        <div>
          <p class="text-xs font-medium uppercase tracking-wide text-foreground-muted">FOB total</p>

          <p class="mt-2 font-medium text-foreground">
            {formatMoney(item.total_fob, item.currency)}
          </p>
        </div>

        <div>
          <p class="text-xs font-medium uppercase tracking-wide text-foreground-muted">Moneda</p>

          <p class="mt-2 font-medium text-foreground">{item.currency}</p>
        </div>
      </div>
    </article>

    <form
      class="space-y-5"
      onsubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <article class="rounded-xl border border-border bg-surface p-4">
        <div>
          <h2 class="font-semibold text-foreground">Costos de importación</h2>

          <p class="mt-1 text-sm text-foreground-muted">
            Al guardar, el backend vuelve a distribuir los costos sobre el FOB de la compra.
          </p>
        </div>

        <div class="mt-4 grid gap-4 md:grid-cols-2">
          <label class="space-y-1.5 text-sm font-medium text-foreground">
            <span>Flete</span>

            <input
              aria-label="Flete"
              type="number"
              min="0"
              step="0.000001"
              value={totalFreight}
              oninput={(event) => (totalFreight = (event.currentTarget as HTMLInputElement).value)}
              disabled={saving}
              class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none disabled:opacity-60"
            />

            {#if validation.totalFreight}
              <span class="block text-xs text-danger">{validation.totalFreight}</span>
            {/if}
          </label>

          <label class="space-y-1.5 text-sm font-medium text-foreground">
            <span>Gastos</span>

            <input
              aria-label="Gastos"
              type="number"
              min="0"
              step="0.000001"
              value={totalExpenses}
              oninput={(event) => (totalExpenses = (event.currentTarget as HTMLInputElement).value)}
              disabled={saving}
              class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none disabled:opacity-60"
            />

            {#if validation.totalExpenses}
              <span class="block text-xs text-danger">{validation.totalExpenses}</span>
            {/if}
          </label>

          <label class="space-y-1.5 text-sm font-medium text-foreground">
            <span>DAI</span>

            <input
              aria-label="DAI"
              type="number"
              min="0"
              step="0.000001"
              value={totalDai}
              oninput={(event) => (totalDai = (event.currentTarget as HTMLInputElement).value)}
              disabled={saving}
              class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none disabled:opacity-60"
            />

            {#if validation.totalDai}
              <span class="block text-xs text-danger">{validation.totalDai}</span>
            {/if}
          </label>

          <label class="space-y-1.5 text-sm font-medium text-foreground">
            <span>IVA de importación</span>

            <input
              aria-label="IVA de importación"
              type="number"
              min="0"
              step="0.000001"
              value={importVat}
              oninput={(event) => (importVat = (event.currentTarget as HTMLInputElement).value)}
              disabled={saving}
              class="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none disabled:opacity-60"
            />

            {#if validation.importVat}
              <span class="block text-xs text-danger">{validation.importVat}</span>
            {/if}

            <span class="block text-xs font-normal text-foreground-muted">
              Informativo. No forma parte del costo aterrizado.
            </span>
          </label>
        </div>

        <label class="mt-4 block space-y-1.5 text-sm font-medium text-foreground">
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
          href={`/retaceos/${item.id}`}
          class="inline-flex h-10 items-center justify-center rounded-lg border border-border bg-surface px-4 text-sm font-medium text-foreground hover:bg-surface-muted"
        >
          Cancelar
        </a>

        <Button type="submit" disabled={saving}>
          {saving ? 'Guardando…' : 'Guardar cambios'}
        </Button>
      </div>
    </form>
  {/if}
</section>
