<script lang="ts">
  import { untrack } from 'svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { salesAnalyticsApi } from '#lib/api/sales-analytics.ts';
  import type { BranchGoal } from '#lib/types/sales-analytics.ts';

  /** Metas de venta sin IVA por sucursal para un mes (`sales_goals:manage`). */
  let {
    period,
    branchId,
    onSaved,
    onCancel
  }: {
    period: string;
    branchId: string | null;
    onSaved: () => void;
    onCancel: () => void;
  } = $props();

  const inputClass =
    'h-10 w-36 rounded-md border border-border bg-background px-3 text-right text-sm text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary';

  let goals = $state<BranchGoal[]>([]);
  let amounts = $state<Record<string, string>>({});
  let loading = $state(true);
  let busy = $state(false);
  let error = $state<string | null>(null);

  async function load() {
    const [key, scope] = untrack(() => [period, branchId] as const);
    loading = true;
    error = null;
    try {
      goals = (await salesAnalyticsApi.goals(key, scope)).goals;
      amounts = Object.fromEntries(goals.map((item) => [item.branch_id, item.amount ?? '']));
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudieron cargar las metas.';
    } finally {
      loading = false;
    }
  }

  void load();

  async function save(event: SubmitEvent) {
    event.preventDefault();
    busy = true;
    error = null;
    try {
      await salesAnalyticsApi.saveGoals(
        period,
        goals.map((item) => {
          const value = (amounts[item.branch_id] ?? '').toString().trim();
          return { branch_id: item.branch_id, amount: value ? Number(value).toFixed(2) : null };
        }),
        branchId
      );
      onSaved();
    } catch (cause) {
      error = cause instanceof HttpError ? cause.message : 'No se pudieron guardar las metas.';
    } finally {
      busy = false;
    }
  }
</script>

<form
  class="space-y-3 rounded-xl border border-border bg-surface p-4 text-sm"
  aria-label="Metas de venta del mes"
  onsubmit={save}
>
  <p class="font-medium text-foreground">Metas de venta sin IVA · {period}</p>
  <p class="text-xs text-foreground-muted">
    Deja vacío el monto para quitar la meta de una sucursal.
  </p>
  {#if error}
    <div class="rounded-md border border-danger/30 bg-danger/10 p-2 text-danger" role="alert">
      {error}
    </div>
  {/if}
  {#if loading}
    <div class="skeleton h-20 rounded-md" aria-hidden="true"></div>
  {:else}
    <div class="space-y-2">
      {#each goals as item (item.branch_id)}
        <label class="flex items-center justify-between gap-3 text-foreground-muted">
          <span class="flex-1 text-foreground">{item.branch_name}</span>
          <input
            class={inputClass}
            type="number"
            min="0.01"
            step="0.01"
            aria-label="Meta de {item.branch_name}"
            value={amounts[item.branch_id] ?? ''}
            oninput={(event) =>
              (amounts = { ...amounts, [item.branch_id]: event.currentTarget.value })}
          />
        </label>
      {/each}
    </div>
    <div class="flex gap-2">
      <Button type="submit" disabled={busy}>Guardar metas</Button>
      <Button variant="ghost" onclick={onCancel}>Cancelar</Button>
    </div>
  {/if}
</form>
