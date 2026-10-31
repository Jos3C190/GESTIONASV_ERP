<script lang="ts">
  import { untrack } from 'svelte';
  import Button from '$lib/components/ui/Button.svelte';
  import { workspaceField } from '../workspace';
  let {
    asOf,
    query,
    differenceOnly,
    loading,
    onquery
  }: {
    asOf: string;
    query: string;
    differenceOnly: boolean;
    loading: boolean;
    onquery: (filters: { as_of: string; q: string; difference_only: boolean }) => void;
  } = $props();
  let date = $state(untrack(() => asOf));
  let text = $state(untrack(() => query));
  let differences = $state(untrack(() => differenceOnly));
  $effect(() => {
    date = asOf;
    text = query;
    differences = differenceOnly;
  });
</script>

<form
  class="grid items-end gap-3 sm:grid-cols-2 lg:grid-cols-[1fr_1.5fr_auto_auto]"
  onsubmit={(event) => {
    event.preventDefault();
    onquery({ as_of: date, q: text.trim(), difference_only: differences });
  }}
>
  <label class="text-sm font-medium"
    >Corte por fecha de registro<input
      type="date"
      required
      class={workspaceField}
      bind:value={date}
    /></label
  >
  <label class="text-sm font-medium"
    >Producto o código<input
      type="search"
      maxlength="120"
      class={workspaceField}
      bind:value={text}
      placeholder="Ej. Azúcar o PRD-AZU-004"
    /></label
  >
  <label class="flex min-h-11 items-center gap-2 text-sm"
    ><input type="checkbox" bind:checked={differences} />Con diferencia o sin base</label
  >
  <Button type="submit" disabled={loading}>Consultar corte</Button>
</form>
<p class="text-xs text-foreground-muted">
  Reconstruye lo registrado hasta el final del día en El Salvador. Incluye todas las bodegas y
  conserva el promedio global de cada producto.
</p>
