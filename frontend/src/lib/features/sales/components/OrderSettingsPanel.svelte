<script lang="ts">
  import { onMount } from 'svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { salesApi } from '#lib/api/sales.ts';

  let { canManage }: { canManage: boolean } = $props();
  let enabled = $state<boolean | null>(null);
  let loading = $state(true);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let notice = $state<string | null>(null);

  onMount(async () => {
    try {
      enabled = (await salesApi.orderSettings()).auto_deliver_on_confirm;
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudo cargar la configuración.';
    } finally {
      loading = false;
    }
  });

  async function toggle(next: boolean) {
    saving = true;
    error = null;
    notice = null;
    try {
      enabled = (await salesApi.saveOrderSettings({ auto_deliver_on_confirm: next }))
        .auto_deliver_on_confirm;
      notice = enabled
        ? 'Al confirmar un pedido se descontarán las existencias.'
        : 'Los pedidos confirmados quedarán apartados hasta preparar su entrega.';
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudo guardar.';
    } finally {
      saving = false;
    }
  }
</script>

<section class="space-y-3 rounded-xl border border-border bg-surface p-5" aria-label="Pedidos">
  <div>
    <h2 class="font-semibold text-foreground">Pedidos</h2>
    <p class="mt-1 text-sm text-foreground-muted">
      Si está activo, confirmar un pedido descuenta las existencias de la bodega y deja la salida en
      el kardex, con las unidades logísticas completas que cubren lo vendido (primero las que vencen
      antes). Lo que necesite separar una caja queda apartado para «Preparar entrega».
    </p>
  </div>
  {#if loading}
    <div class="skeleton h-10 w-2/3 rounded-md" aria-busy="true"></div>
  {:else if enabled !== null}
    <label class="flex items-center gap-2 text-sm text-foreground">
      <input
        type="checkbox"
        checked={enabled}
        disabled={!canManage || saving}
        onchange={(event) => void toggle(event.currentTarget.checked)}
      />
      Descontar existencias al confirmar el pedido
    </label>
  {/if}
  {#if error}
    <div
      class="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>
  {/if}
  {#if notice}<p class="text-sm text-success" aria-live="polite">{notice}</p>{/if}
</section>
