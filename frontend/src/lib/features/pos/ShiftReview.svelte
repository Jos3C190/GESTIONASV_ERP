<script lang="ts">
  /**
   * Revisión del turno por el supervisor: esperado contra contado, conteos y movimientos; aprobar
   * el cierre o pedir que se vuelva a contar. También arma el informe X o Z para imprimir.
   */
  import Badge from '#lib/components/ui/Badge.svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import Modal from '#lib/components/ui/Modal.svelte';
  import { posApi } from '#lib/api/pos.ts';
  import { company } from '#lib/stores/company.svelte.ts';
  import { permissions } from '#lib/stores/permissions.svelte.ts';
  import { session } from '#lib/stores/session.svelte.ts';
  import type { PosShift, PosShiftDetail } from '#lib/types/pos.ts';
  import ShiftReport from './ShiftReport.svelte';
  import { printReceipt } from './print.ts';
  import {
    MOVEMENT_KIND,
    SHIFT_STATUS,
    centsToAmount,
    formatDateTime,
    formatMoney,
    toCents
  } from './format.ts';

  interface Props {
    shiftId: string | null;
    onclose: () => void;
    onchanged: (shift: PosShift) => void;
  }

  let { shiftId, onclose, onchanged }: Props = $props();
  let detail = $state<PosShiftDetail | null>(null);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let retained = $state('');
  let notes = $state('');
  let recountReason = $state('');
  let mode = $state<'view' | 'recount'>('view');
  let saving = $state(false);
  let actionError = $state<string | null>(null);
  let reportNode = $state<HTMLElement | null>(null);

  const shift = $derived(detail?.shift ?? null);
  const totals = $derived(detail?.totals ?? null);
  const canSupervise = $derived(permissions.hasPermission('pos:supervise'));
  const ownShift = $derived(!!shift && shift.cashier.id === session.user?.id);
  const difference = $derived(
    shift && totals && shift.counted_cash !== null
      ? (toCents(shift.counted_cash) ?? 0) - (toCents(totals.expected_cash) ?? 0)
      : null
  );
  const retainedCents = $derived(toCents(retained));
  const canApprove = $derived(
    !!shift &&
      shift.status === 'counted' &&
      canSupervise &&
      !ownShift &&
      retainedCents !== null &&
      retainedCents <= (toCents(shift.counted_cash ?? '0') ?? 0) &&
      (difference === 0 || notes.trim().length >= 5)
  );

  async function load(id: string) {
    loading = true;
    error = null;
    mode = 'view';
    actionError = null;
    try {
      detail = await posApi.shift(id);
      const counted = toCents(detail.shift.counted_cash ?? '0') ?? 0;
      const suggested = toCents(detail.register_detail.opening_float) ?? 0;
      retained = centsToAmount(Math.min(counted, suggested));
      notes = '';
      recountReason = '';
    } catch (err) {
      error = err instanceof Error ? err.message : 'No se pudo cargar el turno.';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    if (shiftId) void load(shiftId);
    else detail = null;
  });

  async function approve() {
    if (!shift || retainedCents === null) return;
    saving = true;
    actionError = null;
    try {
      const updated = await posApi.approve(
        shift.id,
        shift.version,
        centsToAmount(retainedCents),
        notes.trim() || null
      );
      onchanged(updated);
      await load(shift.id);
    } catch (err) {
      actionError = err instanceof Error ? err.message : 'No se pudo aprobar el cierre.';
    } finally {
      saving = false;
    }
  }

  async function recount() {
    if (!shift) return;
    saving = true;
    actionError = null;
    try {
      const updated = await posApi.recount(shift.id, shift.version, recountReason.trim());
      onchanged(updated);
      await load(shift.id);
    } catch (err) {
      actionError = err instanceof Error ? err.message : 'No se pudo pedir el recuento.';
    } finally {
      saving = false;
    }
  }

  function differenceText(cents: number): string {
    if (cents === 0) return 'Cuadra';
    return `${cents > 0 ? 'Sobrante' : 'Faltante'} de ${formatMoney(centsToAmount(Math.abs(cents)))}`;
  }
</script>

<Modal
  open={shiftId !== null}
  title={shift ? `Turno ${shift.code}` : 'Turno'}
  {onclose}
  size="xl"
  mobileFullScreen
>
  {#if loading}
    <div class="space-y-3" aria-label="Cargando turno">
      <div class="h-20 rounded-xl skeleton"></div>
      <div class="h-40 rounded-xl skeleton"></div>
    </div>
  {:else if error}
    <div
      class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
      role="alert"
    >
      {error}
    </div>
  {:else if shift && detail}
    <div class="space-y-5">
      <div class="flex flex-wrap items-center gap-3">
        <Badge variant={SHIFT_STATUS[shift.status].variant}
          >{SHIFT_STATUS[shift.status].label}</Badge
        >
        <span class="text-sm text-foreground-muted">
          {shift.register_code} · {shift.branch_name} · {shift.cashier.name}
        </span>
      </div>

      {#if totals}
        <div class="grid gap-3 sm:grid-cols-3">
          <div class="rounded-xl border border-border p-3">
            <p class="text-xs text-foreground-muted">Esperado en gaveta</p>
            <p class="text-xl font-bold tabular-nums text-foreground">
              {formatMoney(totals.expected_cash)}
            </p>
          </div>
          <div class="rounded-xl border border-border p-3">
            <p class="text-xs text-foreground-muted">Contado</p>
            <p class="text-xl font-bold tabular-nums text-foreground">
              {formatMoney(shift.counted_cash)}
            </p>
          </div>
          <div
            class={`rounded-xl border p-3 ${difference === null || difference === 0 ? 'border-border' : 'border-danger/30 bg-danger/10'}`}
          >
            <p class="text-xs text-foreground-muted">Diferencia</p>
            <p class="text-xl font-bold tabular-nums text-foreground">
              {difference === null ? '—' : differenceText(difference)}
            </p>
          </div>
        </div>
        <dl class="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
          <div class="flex justify-between">
            <dt class="text-foreground-muted">Fondo inicial</dt>
            <dd class="tabular-nums">{formatMoney(totals.opening_float)}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-foreground-muted">Ventas en efectivo</dt>
            <dd class="tabular-nums">{formatMoney(totals.cash_sales)}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-foreground-muted">Entradas</dt>
            <dd class="tabular-nums">{formatMoney(totals.cash_in)}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-foreground-muted">Salidas</dt>
            <dd class="tabular-nums">{formatMoney(totals.cash_out)}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-foreground-muted">Retiros a caja fuerte</dt>
            <dd class="tabular-nums">{formatMoney(totals.safe_drops)}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-foreground-muted">Reintegros</dt>
            <dd class="tabular-nums">{formatMoney(totals.cash_refunds)}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-foreground-muted">Tarjeta esperada / según lote</dt>
            <dd class="tabular-nums">
              {formatMoney(totals.expected_card)} / {formatMoney(shift.declared_card)}
            </dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-foreground-muted">Transferencias esperadas / recibidas</dt>
            <dd class="tabular-nums">
              {formatMoney(totals.expected_transfer)} / {formatMoney(shift.declared_transfer)}
            </dd>
          </div>
        </dl>
      {/if}

      {#if detail.movements.length}
        <section>
          <h3 class="text-sm font-semibold text-foreground">Movimientos</h3>
          <ul class="mt-2 divide-y divide-border text-sm">
            {#each detail.movements as movement (movement.id)}
              <li class="flex justify-between gap-3 py-1.5">
                <span class="min-w-0 truncate">
                  {MOVEMENT_KIND[movement.kind].label} · {movement.reason}
                  {#if movement.authorized_by}<span class="text-foreground-muted">
                      · autorizó {movement.authorized_by.name}</span
                    >{/if}
                </span>
                <span class="flex-none tabular-nums"
                  >{MOVEMENT_KIND[movement.kind].sign < 0 ? '−' : '+'}{formatMoney(
                    movement.amount
                  )}</span
                >
              </li>
            {/each}
          </ul>
        </section>
      {/if}

      <section>
        <h3 class="text-sm font-semibold text-foreground">Conteos</h3>
        <ul class="mt-2 space-y-1 text-sm">
          {#each detail.counts as count (count.id)}
            <li class="flex justify-between gap-3">
              <span>
                {count.kind === 'opening' ? 'Apertura' : `Cierre ${count.sequence}`} · {count
                  .counted_by.name} · {formatDateTime(count.counted_at)}
                {#if count.notes}<span class="text-foreground-muted"> · {count.notes}</span>{/if}
              </span>
              <span class="tabular-nums">{formatMoney(count.cash_total)}</span>
            </li>
          {/each}
        </ul>
      </section>

      {#if shift.status === 'counted' && canSupervise}
        {#if ownShift}
          <p class="rounded-xl border border-warning/30 bg-warning/10 p-3 text-sm text-foreground">
            Es tu propio turno: otro supervisor debe revisarlo.
          </p>
        {:else if mode === 'recount'}
          <div class="space-y-2 rounded-xl border border-border p-4">
            <label class="block text-sm font-medium text-foreground">
              ¿Qué debe revisar el cajero?
              <textarea
                class="mt-1 w-full rounded-lg border border-border bg-surface p-2 text-sm"
                rows="2"
                maxlength="200"
                bind:value={recountReason}
              ></textarea>
            </label>
          </div>
        {:else}
          <div class="grid gap-3 rounded-xl border border-border p-4 sm:grid-cols-2">
            <label class="block text-sm font-medium text-foreground">
              Fondo que queda para el siguiente turno
              <input
                class="mt-1 h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm tabular-nums"
                inputmode="decimal"
                bind:value={retained}
              />
              {#if retainedCents === null}<span class="mt-1 block text-xs text-danger"
                  >Monto no válido.</span
                >{/if}
            </label>
            <div class="text-sm">
              <p class="text-foreground-muted">A depositar de este turno</p>
              <p class="text-lg font-semibold tabular-nums text-foreground">
                {retainedCents === null
                  ? '—'
                  : formatMoney(
                      centsToAmount(
                        (toCents(shift.counted_cash ?? '0') ?? 0) -
                          retainedCents +
                          (toCents(totals?.safe_drops ?? '0') ?? 0)
                      )
                    )}
              </p>
            </div>
            <label class="block text-sm font-medium text-foreground sm:col-span-2">
              {difference ? 'Explicación de la diferencia' : 'Notas (opcional)'}
              <textarea
                class="mt-1 w-full rounded-lg border border-border bg-surface p-2 text-sm"
                rows="2"
                maxlength="300"
                bind:value={notes}
              ></textarea>
            </label>
          </div>
        {/if}
      {/if}

      {#if shift.status === 'closed'}
        <p class="text-sm text-foreground-muted">
          Cerrado el {formatDateTime(shift.closed_at)} por {shift.approved_by?.name}.
          {#if shift.deposit_number}Depositado en DEP-{String(shift.deposit_number).padStart(
              6,
              '0'
            )}.{:else}Pendiente de depósito.{/if}
        </p>
      {/if}

      {#if actionError}
        <p
          class="rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger"
          role="alert"
        >
          {actionError}
        </p>
      {/if}

      {#if totals}
        <div class="hidden">
          <ShiftReport
            {detail}
            {totals}
            companyName={company.active?.commercial_name ?? ''}
            bind:node={reportNode}
          />
        </div>
      {/if}
    </div>
  {/if}
  {#snippet footer()}
    {#if shift && totals && permissions.hasAnyPermission(['pos:reports', 'pos:supervise'])}
      <Button
        variant="secondary"
        disabled={!reportNode}
        onclick={() =>
          reportNode &&
          printReceipt(
            reportNode,
            `${shift.status === 'closed' ? 'Cierre Z' : 'Corte X'} ${shift.code}`
          )}
      >
        {shift.status === 'closed' ? 'Imprimir cierre Z' : 'Imprimir corte X'}
      </Button>
    {/if}
    {#if shift?.status === 'counted' && canSupervise && !ownShift}
      {#if mode === 'recount'}
        <Button variant="secondary" onclick={() => (mode = 'view')}>Volver</Button>
        <Button
          variant="warning"
          disabled={saving || recountReason.trim().length < 5}
          onclick={recount}
        >
          {saving ? 'Enviando…' : 'Pedir recuento'}
        </Button>
      {:else}
        <Button variant="secondary" onclick={() => (mode = 'recount')}>Pedir recuento</Button>
        <Button disabled={!canApprove || saving} onclick={approve}
          >{saving ? 'Aprobando…' : 'Aprobar cierre'}</Button
        >
      {/if}
    {:else}
      <Button variant="secondary" onclick={onclose}>Cerrar</Button>
    {/if}
  {/snippet}
</Modal>
