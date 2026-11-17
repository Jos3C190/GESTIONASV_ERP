<script lang="ts">
  import { onMount } from 'svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { salesApi } from '#lib/api/sales.ts';

  let { canManage }: { canManage: boolean } = $props();
  let days = $state<number | null>(null);
  let saved = $state<number | null>(null);
  let loading = $state(true);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let notice = $state<string | null>(null);

  onMount(async () => {
    try {
      const settings = await salesApi.quotationSettings();
      days = settings.quotation_validity_days;
      saved = days;
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudo cargar la configuración.';
    } finally {
      loading = false;
    }
  });

  async function save(event: SubmitEvent) {
    event.preventDefault();
    if (days === null || !Number.isInteger(days) || days < 1 || days > 365) {
      error = 'La vigencia va de 1 a 365 días.';
      return;
    }
    saving = true;
    error = null;
    notice = null;
    try {
      const result = await salesApi.saveQuotationSettings({ quotation_validity_days: days });
      days = result.quotation_validity_days;
      saved = days;
      notice = 'Vigencia guardada. Se aplica a las cotizaciones nuevas.';
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudo guardar la vigencia.';
    } finally {
      saving = false;
    }
  }
</script>

<section class="space-y-4 rounded-xl border border-border bg-surface p-5">
  <div>
    <h2 class="font-semibold text-foreground">Vigencia de las cotizaciones</h2>
    <p class="mt-1 text-sm text-foreground-muted">
      Días que una cotización nueva queda válida si no se indica otra fecha. Cada cotización puede
      cambiarla al editarse.
    </p>
  </div>
  {#if error}
    <div
      class="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>
  {/if}
  {#if notice}
    <div
      class="rounded-lg border border-success/30 bg-success/10 px-4 py-3 text-sm text-success"
      role="status"
    >
      {notice}
    </div>
  {/if}
  {#if loading}
    <div class="skeleton h-10 w-48 rounded-md" aria-busy="true"></div>
  {:else}
    <form class="flex flex-wrap items-end gap-3" onsubmit={save}>
      <label class="text-sm text-foreground-muted">
        Días de vigencia
        <input
          class="mt-1 h-10 w-32 rounded-md border border-border bg-background px-3 text-foreground"
          type="number"
          min="1"
          max="365"
          step="1"
          bind:value={days}
          disabled={!canManage}
        />
      </label>
      {#if canManage}
        <button
          class="h-10 rounded-md bg-primary px-4 text-sm font-semibold text-primary-foreground disabled:opacity-50"
          disabled={saving || days === saved}
        >
          {saving ? 'Guardando…' : 'Guardar'}
        </button>
      {/if}
    </form>
  {/if}
</section>
