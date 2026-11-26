<script lang="ts">
  /**
   * Conteo de cierre (ciego): el cajero declara lo que hay sin ver lo esperado. Al entregarlo, la caja
   * deja de vender hasta que el supervisor apruebe o pida recontar.
   */
  import Button from '#lib/components/ui/Button.svelte';
  import Modal from '#lib/components/ui/Modal.svelte';
  import { posApi } from '#lib/api/pos.ts';
  import type { DenominationLine, PosShift } from '#lib/types/pos.ts';
  import DenominationCounter from './DenominationCounter.svelte';
  import { centsToAmount, countedLines, emptyCount, toCents } from './format.ts';

  interface Props {
    open: boolean;
    shift: PosShift;
    onclose: () => void;
    oncounted: (shift: PosShift) => void;
  }

  let { open, shift, onclose, oncounted }: Props = $props();
  let lines = $state<DenominationLine[]>(emptyCount());
  let card = $state('0.00');
  let transfer = $state('0.00');
  let notes = $state('');
  let confirming = $state(false);
  let saving = $state(false);
  let error = $state<string | null>(null);

  const cardCents = $derived(toCents(card));
  const transferCents = $derived(toCents(transfer));
  const valid = $derived(cardCents !== null && transferCents !== null);

  $effect(() => {
    if (open) {
      lines = emptyCount();
      card = '0.00';
      transfer = '0.00';
      notes = '';
      confirming = false;
      error = null;
    }
  });

  async function submit() {
    if (!valid || cardCents === null || transferCents === null) return;
    saving = true;
    error = null;
    try {
      oncounted(
        await posApi.count(shift.id, {
          expected_version: shift.version,
          denominations: countedLines(lines),
          declared_card: centsToAmount(cardCents),
          declared_transfer: centsToAmount(transferCents),
          notes: notes.trim() || null
        })
      );
    } catch (err) {
      error = err instanceof Error ? err.message : 'No se pudo entregar el conteo.';
      confirming = false;
    } finally {
      saving = false;
    }
  }
</script>

<Modal {open} title="Contar y entregar el turno" {onclose} size="xl" mobileFullScreen>
  <div class="space-y-4">
    {#if shift.status === 'recount' && shift.recount_reason}
      <div
        class="rounded-xl border border-danger/30 bg-danger/10 p-3 text-sm text-foreground"
        role="alert"
      >
        <p class="font-semibold text-danger">El supervisor pidió recontar</p>
        <p class="mt-1">{shift.recount_reason}</p>
      </div>
    {/if}
    <p class="text-sm text-foreground-muted">
      Cuenta todo el efectivo de la gaveta, billete por billete. Luego escribe el total del cierre
      de lote del datáfono y el de las transferencias recibidas.
    </p>
    <DenominationCounter {lines} onchange={(next) => (lines = next)} label="Efectivo en gaveta" />
    <div class="grid gap-3 sm:grid-cols-2">
      <label class="block text-sm font-medium text-foreground">
        Total de tarjeta según el cierre de lote
        <input
          class="mt-1 h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm tabular-nums text-foreground"
          inputmode="decimal"
          bind:value={card}
        />
        {#if cardCents === null}<span class="mt-1 block text-xs text-danger">Monto no válido.</span
          >{/if}
      </label>
      <label class="block text-sm font-medium text-foreground">
        Total de transferencias recibidas
        <input
          class="mt-1 h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm tabular-nums text-foreground"
          inputmode="decimal"
          bind:value={transfer}
        />
        {#if transferCents === null}<span class="mt-1 block text-xs text-danger"
            >Monto no válido.</span
          >{/if}
      </label>
    </div>
    <label class="block text-sm font-medium text-foreground">
      Notas <span class="font-normal text-foreground-subtle">(opcional)</span>
      <textarea
        class="mt-1 w-full rounded-lg border border-border bg-surface p-2 text-sm text-foreground"
        rows="2"
        maxlength="300"
        bind:value={notes}
      ></textarea>
    </label>
    {#if confirming}
      <div
        class="rounded-xl border border-warning/30 bg-warning/10 p-3 text-sm text-foreground"
        role="alert"
      >
        Al entregar el conteo, la caja deja de vender hasta que el supervisor revise el turno.
      </div>
    {/if}
    {#if error}
      <p
        class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
        role="alert"
      >
        {error}
      </p>
    {/if}
  </div>
  {#snippet footer()}
    <Button variant="secondary" onclick={onclose}>Cancelar</Button>
    {#if confirming}
      <Button disabled={saving} onclick={submit}
        >{saving ? 'Entregando…' : 'Sí, entregar conteo'}</Button
      >
    {:else}
      <Button disabled={!valid} onclick={() => (confirming = true)}>Entregar conteo</Button>
    {/if}
  {/snippet}
</Modal>
