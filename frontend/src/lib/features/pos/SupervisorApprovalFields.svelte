<script lang="ts">
  /**
   * Autorización de un supervisor en la caja: elige quién autoriza y escribe su PIN de 6 dígitos.
   * El PIN nunca se guarda en la pantalla después de enviarlo.
   */
  import { posApi } from '#lib/api/pos.ts';
  import type { PosPerson, SupervisorApproval } from '#lib/types/pos.ts';

  interface Props {
    branchId: string;
    onchange: (value: SupervisorApproval | null) => void;
    reason?: string;
  }

  let { branchId, onchange, reason }: Props = $props();
  let people = $state<PosPerson[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let supervisorId = $state('');
  let pin = $state('');

  $effect(() => {
    const id = branchId;
    loading = true;
    error = null;
    posApi
      .supervisors(id)
      .then((items) => {
        people = items;
        if (items.length === 1) supervisorId = items[0]!.id;
      })
      .catch((err: unknown) => {
        error = err instanceof Error ? err.message : 'No se pudo cargar quién autoriza.';
      })
      .finally(() => (loading = false));
  });

  function emit() {
    onchange(supervisorId && /^\d{6}$/.test(pin) ? { supervisor_id: supervisorId, pin } : null);
  }
</script>

<div class="space-y-3 rounded-xl border border-warning/30 bg-warning/10 p-3">
  <p class="text-sm font-medium text-foreground">Autorización del supervisor</p>
  {#if reason}<p class="text-xs text-foreground-muted">{reason}</p>{/if}
  {#if loading}
    <div class="h-9 rounded-lg skeleton" aria-label="Cargando supervisores"></div>
  {:else if error}
    <p class="text-sm text-danger" role="alert">{error}</p>
  {:else if people.length === 0}
    <p class="text-sm text-foreground-muted">
      Nadie con permiso de supervisor tiene acceso a esta sucursal.
    </p>
  {:else}
    <div class="grid gap-3 sm:grid-cols-2">
      <label class="block text-xs font-medium text-foreground-muted">
        Autoriza
        <select
          class="mt-1 h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm text-foreground"
          value={supervisorId}
          onchange={(event) => {
            supervisorId = (event.currentTarget as HTMLSelectElement).value;
            emit();
          }}
        >
          <option value="">Elige al supervisor</option>
          {#each people as person (person.id)}
            <option value={person.id}>{person.name}</option>
          {/each}
        </select>
      </label>
      <label class="block text-xs font-medium text-foreground-muted">
        PIN del supervisor
        <input
          type="password"
          inputmode="numeric"
          autocomplete="off"
          maxlength="6"
          class="mt-1 h-10 w-full rounded-lg border border-border bg-surface px-3 text-center text-lg tracking-[0.4em] text-foreground"
          value={pin}
          oninput={(event) => {
            pin = (event.currentTarget as HTMLInputElement).value.replace(/\D/g, '').slice(0, 6);
            (event.currentTarget as HTMLInputElement).value = pin;
            emit();
          }}
        />
      </label>
    </div>
  {/if}
</div>
