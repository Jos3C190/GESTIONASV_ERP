<script lang="ts">
  import Badge from '#lib/components/ui/Badge.svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import Modal from '#lib/components/ui/Modal.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { priceListsApi } from '#lib/api/price-lists.ts';
  import {
    STATUS_LABELS,
    STATUS_TONES,
    todayInElSalvador,
    validityText
  } from '#lib/features/price-lists/labels.ts';
  import type { SellableUnit, VolumeDiscount } from '#lib/types/price-list.ts';

  let {
    listId,
    unit,
    canManage,
    onclose
  }: {
    listId: string;
    unit: SellableUnit | null;
    canManage: boolean;
    onclose: () => void;
  } = $props();

  const inputClass =
    'h-11 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary';
  const labelClass = 'mb-1 block text-sm font-medium text-foreground';

  let scales = $state<VolumeDiscount[]>([]);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let minQuantity = $state('');
  let percent = $state('');
  let validFrom = $state(todayInElSalvador());
  let saving = $state(false);

  const mine = $derived(
    unit
      ? scales
          .filter(
            (s) =>
              s.product_id === unit.product_id &&
              s.variant_id === unit.variant_id &&
              s.unit_id === unit.unit_id &&
              s.status !== 'expired'
          )
          .sort((a, b) => Number(a.min_quantity) - Number(b.min_quantity))
      : []
  );

  async function load() {
    loading = true;
    error = null;
    try {
      scales = await priceListsApi.volumeDiscounts(listId);
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudieron cargar las escalas.';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    if (unit) {
      minQuantity = '';
      percent = '';
      validFrom = todayInElSalvador();
      void load();
    }
  });

  async function add(event: SubmitEvent) {
    event.preventDefault();
    if (!unit) return;
    saving = true;
    error = null;
    try {
      await priceListsApi.addVolumeDiscount(listId, {
        product_id: unit.product_id,
        variant_id: unit.variant_id,
        unit_id: unit.unit_id,
        min_quantity: String(minQuantity),
        discount_percent: String(percent),
        valid_from: validFrom
      });
      minQuantity = '';
      percent = '';
      await load();
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudo guardar la escala.';
    } finally {
      saving = false;
    }
  }

  async function remove(scale: VolumeDiscount) {
    error = null;
    try {
      await priceListsApi.removeVolumeDiscount(scale.id);
      await load();
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudo quitar la escala.';
    }
  }
</script>

<Modal open={unit !== null} title={unit ? `Descuento por volumen: ${unit.name}` : ''} {onclose}>
  {#if unit}
    <div class="space-y-4">
      <p class="text-sm text-foreground-muted">
        {unit.unit_name}. Aplica la escala más alta que alcance la cantidad. Si el cliente tiene un
        descuento fijo mayor, se usa ese; no se suman.
      </p>
      {#if error}
        <p
          class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
          role="alert"
        >
          {error}
        </p>
      {/if}
      {#if loading}
        <div class="skeleton h-16 rounded-lg motion-reduce:animate-none" aria-busy="true"></div>
      {:else if mine.length === 0}
        <p class="rounded-lg bg-surface-muted/50 p-4 text-center text-sm text-foreground-muted">
          Este producto no tiene escalas en la lista.
        </p>
      {:else}
        <ul class="divide-y divide-border rounded-lg border border-border">
          {#each mine as scale (scale.id)}
            <li class="flex items-center justify-between gap-3 p-3 text-sm">
              <span>
                <span class="font-medium text-foreground"
                  >Desde {Number(scale.min_quantity)}: {Number(scale.discount_percent)} %</span
                >
                <Badge variant={STATUS_TONES[scale.status]}>{STATUS_LABELS[scale.status]}</Badge>
                <span class="block text-foreground-muted"
                  >{validityText(scale.valid_from, scale.valid_to)}</span
                >
              </span>
              {#if canManage}
                <Button variant="ghost" size="sm" onclick={() => void remove(scale)}>
                  {scale.status === 'scheduled' ? 'Anular' : 'Terminar hoy'}
                </Button>
              {/if}
            </li>
          {/each}
        </ul>
      {/if}
      {#if canManage}
        <form class="grid gap-3 border-t border-border pt-4 sm:grid-cols-3" onsubmit={add}>
          <div>
            <label for="scale-quantity" class={labelClass}>Desde la cantidad</label>
            <input
              id="scale-quantity"
              type="number"
              min="0"
              step="any"
              bind:value={minQuantity}
              required
              class={inputClass}
            />
          </div>
          <div>
            <label for="scale-percent" class={labelClass}>Descuento (%)</label>
            <input
              id="scale-percent"
              type="number"
              min="0"
              max="100"
              step="any"
              bind:value={percent}
              required
              class={inputClass}
            />
          </div>
          <div>
            <label for="scale-from" class={labelClass}>Rige desde</label>
            <input
              id="scale-from"
              type="date"
              min={todayInElSalvador()}
              bind:value={validFrom}
              required
              class={inputClass}
            />
          </div>
          <div class="flex justify-end sm:col-span-3">
            <Button type="submit" disabled={saving}>
              {saving ? 'Guardando…' : 'Agregar escala'}
            </Button>
          </div>
        </form>
      {/if}
    </div>
  {/if}
</Modal>
