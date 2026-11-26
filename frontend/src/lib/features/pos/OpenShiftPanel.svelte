<script lang="ts">
  /** Apertura del turno: elegir la caja y contar el fondo por denominación. */
  import Button from '#lib/components/ui/Button.svelte';
  import { HttpError } from '#lib/api/client.ts';
  import { posApi } from '#lib/api/pos.ts';
  import type { DenominationLine, PosRegister, PosShift } from '#lib/types/pos.ts';
  import DenominationCounter from './DenominationCounter.svelte';
  import {
    centsToAmount,
    countTotalCents,
    countedLines,
    emptyCount,
    formatMoney,
    idempotencyKey,
    toCents
  } from './format.ts';

  interface Props {
    branchId: string | null;
    canManageRegisters: boolean;
    onopened: (shift: PosShift) => void;
  }

  let { branchId, canManageRegisters, onopened }: Props = $props();
  let registers = $state<PosRegister[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let registerId = $state('');
  let lines = $state<DenominationLine[]>(emptyCount());
  let notes = $state('');
  let submitting = $state(false);
  let submitError = $state<string | null>(null);
  // Una llave por intento de apertura: reintentar tras un corte no abre dos turnos.
  let key = $state(idempotencyKey('apertura'));

  const register = $derived(registers.find((item) => item.id === registerId) ?? null);
  const counted = $derived(countTotalCents(lines));
  const expected = $derived(register ? toCents(register.opening_float) : null);
  const differs = $derived(expected !== null && counted !== expected);
  const canOpen = $derived(!!register && !submitting && (!differs || notes.trim().length >= 5));

  async function load() {
    loading = true;
    error = null;
    try {
      registers = (await posApi.registers(branchId)).filter((item) => item.is_active);
      const free = registers.filter((item) => !item.unclosed_shift_id);
      if (free.length === 1) registerId = free[0]!.id;
    } catch (err) {
      error = err instanceof Error ? err.message : 'No se pudieron cargar las cajas.';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    void branchId;
    void load();
  });

  async function open() {
    if (!register) return;
    submitting = true;
    submitError = null;
    try {
      const shift = await posApi.openShift(
        register.id,
        countedLines(lines),
        notes.trim() || null,
        key
      );
      onopened(shift);
    } catch (err) {
      submitError = err instanceof Error ? err.message : 'No se pudo abrir el turno.';
      // Sin respuesta del servidor se conserva la llave: el reintento no abre otro turno.
      if (!(err instanceof HttpError && err.status === 0)) key = idempotencyKey('apertura');
    } finally {
      submitting = false;
    }
  }
</script>

<section class="mx-auto w-full max-w-4xl space-y-5" aria-labelledby="open-shift-title">
  <header>
    <h2 id="open-shift-title" class="text-xl font-bold text-foreground">Abrir turno</h2>
    <p class="mt-1 text-sm text-foreground-muted">
      Elige tu caja y cuenta el fondo que recibes. Ese conteo es el punto de partida del arqueo.
    </p>
  </header>

  {#if loading}
    <div class="grid gap-3 sm:grid-cols-3">
      {#each [1, 2, 3] as item (item)}<div class="h-20 rounded-xl skeleton"></div>{/each}
    </div>
  {:else if error}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
      role="alert"
    >
      <p>{error}</p>
      <div class="mt-3">
        <Button variant="secondary" size="sm" onclick={load}>Reintentar</Button>
      </div>
    </div>
  {:else if registers.length === 0}
    <div
      class="flex flex-col items-center rounded-xl border border-border bg-surface p-10 text-center"
    >
      <span
        class="flex h-12 w-12 items-center justify-center rounded-full bg-surface-muted text-foreground-subtle"
        aria-hidden="true"
      >
        <svg
          width="22"
          height="22"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          ><rect x="3" y="7" width="18" height="12" rx="2" /><path d="M7 7V5h10v2M3 12h18" /></svg
        >
      </span>
      <p class="mt-3 font-semibold text-foreground">No hay cajas activas en esta sucursal</p>
      <p class="mt-1 max-w-sm text-sm text-foreground-muted">
        Una caja se crea sobre un punto de venta de la configuración fiscal.
      </p>
      {#if canManageRegisters}
        <a
          href="/pos/registers"
          class="mt-4 inline-flex h-9 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground"
          >Configurar cajas</a
        >
      {/if}
    </div>
  {:else}
    <fieldset>
      <legend class="mb-2 text-sm font-medium text-foreground">Caja</legend>
      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {#each registers as item (item.id)}
          {@const busy = !!item.unclosed_shift_id}
          <label
            class={`flex cursor-pointer flex-col rounded-xl border p-4 transition-colors ${
              registerId === item.id
                ? 'border-primary bg-primary/5 ring-1 ring-primary'
                : 'border-border bg-surface hover:bg-surface-hover'
            } ${busy ? 'cursor-not-allowed opacity-60' : ''}`}
          >
            <input
              type="radio"
              name="register"
              class="sr-only"
              value={item.id}
              checked={registerId === item.id}
              disabled={busy}
              onchange={() => (registerId = item.id)}
            />
            <span class="text-base font-semibold text-foreground">{item.code}</span>
            <span class="text-sm text-foreground-muted">{item.name}</span>
            <span class="mt-2 text-xs text-foreground-subtle">
              {busy
                ? `En uso por ${item.unclosed_shift_cashier}`
                : `Fondo ${formatMoney(item.opening_float)}`}
            </span>
          </label>
        {/each}
      </div>
    </fieldset>

    {#if register}
      <DenominationCounter {lines} onchange={(next) => (lines = next)} label="Fondo inicial" />
      {#if differs}
        <div class="space-y-2 rounded-xl border border-warning/30 bg-warning/10 p-3">
          <p class="text-sm text-foreground">
            Contaste {formatMoney(centsToAmount(counted))}; la caja trabaja con un fondo de
            {formatMoney(register.opening_float)}. Explica la diferencia para abrir.
          </p>
          <label class="block text-xs font-medium text-foreground-muted">
            Explicación
            <textarea
              class="mt-1 w-full rounded-lg border border-border bg-surface p-2 text-sm text-foreground"
              rows="2"
              maxlength="300"
              bind:value={notes}
            ></textarea>
          </label>
        </div>
      {/if}
      {#if submitError}
        <p
          class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
          role="alert"
        >
          {submitError}
        </p>
      {/if}
      <div class="flex justify-end">
        <Button size="lg" disabled={!canOpen} onclick={open}>
          {submitting ? 'Abriendo…' : `Abrir turno en ${register.code}`}
        </Button>
      </div>
    {/if}
  {/if}
</section>
