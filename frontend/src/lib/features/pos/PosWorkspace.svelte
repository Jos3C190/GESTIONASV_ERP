<script lang="ts">
  /**
   * La caja de quien está conectado: abrir turno, mover efectivo, contar y entregar. El esperado
   * nunca se muestra al cajero mientras el turno no se cierra (cierre ciego).
   */
  import Badge from '#lib/components/ui/Badge.svelte';
  import Button from '#lib/components/ui/Button.svelte';
  import { posApi } from '#lib/api/pos.ts';
  import { branch } from '#lib/stores/branch.svelte.ts';
  import { company } from '#lib/stores/company.svelte.ts';
  import { permissions } from '#lib/stores/permissions.svelte.ts';
  import type { MovementKind, PosMe, PosShiftDetail } from '#lib/types/pos.ts';
  import CountDialog from './CountDialog.svelte';
  import MovementDialog from './MovementDialog.svelte';
  import OpenShiftPanel from './OpenShiftPanel.svelte';
  import PinDialog from './PinDialog.svelte';
  import { MOVEMENT_KIND, SHIFT_STATUS, formatDateTime, formatMoney } from './format.ts';

  let me = $state<PosMe | null>(null);
  let detail = $state<PosShiftDetail | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let movementKind = $state<MovementKind | null>(null);
  let counting = $state(false);
  let pinOpen = $state(false);
  let notice = $state<string | null>(null);

  const shift = $derived(detail?.shift ?? null);
  const canOpen = $derived(permissions.hasPermission('pos:shift_open'));
  const canMove = $derived(permissions.hasPermission('pos:cash_movements'));
  const canClose = $derived(permissions.hasPermission('pos:shift_close'));
  const canManageRegisters = $derived(permissions.hasPermission('pos:registers_manage'));

  async function load() {
    loading = true;
    error = null;
    try {
      me = await posApi.me();
      detail = me.shift ? await posApi.shift(me.shift.id) : null;
    } catch (err) {
      error = err instanceof Error ? err.message : 'No se pudo cargar tu caja.';
    } finally {
      loading = false;
    }
  }

  async function refresh() {
    if (!me?.shift && !detail) return load();
    try {
      me = await posApi.me();
      detail = me.shift ? await posApi.shift(me.shift.id) : null;
    } catch (err) {
      error = err instanceof Error ? err.message : 'No se pudo actualizar tu caja.';
    }
  }

  $effect(() => {
    void company.id;
    void branch.id;
    void load();
  });
</script>

<div class="flex min-h-full flex-col bg-surface-muted/40">
  <div class="border-b border-border bg-surface px-4 py-3 md:px-6">
    <div class="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-3">
      <div class="min-w-0 basis-full sm:basis-0 sm:flex-1">
        <p class="text-xs font-semibold uppercase tracking-wider text-primary">Punto de venta</p>
        <h1 class="truncate text-lg font-bold text-foreground">
          {shift ? `${shift.register_code} · ${shift.register_name}` : 'Caja'}
        </h1>
        <p class="truncate text-sm text-foreground-muted">
          {me?.user.name ?? '—'}{shift ? ` · ${shift.branch_name}` : ''}
        </p>
      </div>
      {#if shift}
        <div class="flex items-center gap-2">
          <Badge variant={SHIFT_STATUS[shift.status].variant}
            >{SHIFT_STATUS[shift.status].label}</Badge
          >
          <span class="text-sm font-semibold tabular-nums text-foreground">{shift.code}</span>
        </div>
      {/if}
      {#if me?.can_supervise}
        <Button variant="secondary" size="sm" onclick={() => (pinOpen = true)}>
          {me.has_pin ? 'Cambiar mi PIN' : 'Definir mi PIN'}
        </Button>
      {/if}
    </div>
  </div>

  <div class="mx-auto w-full max-w-6xl flex-1 px-4 py-6 md:px-6">
    {#if notice}
      <div
        class="mb-4 rounded-xl border border-success/30 bg-success/10 p-3 text-sm text-foreground"
        role="status"
      >
        {notice}
      </div>
    {/if}
    {#if loading}
      <div class="space-y-3" aria-label="Cargando tu caja">
        <div class="h-24 rounded-xl skeleton"></div>
        <div class="h-64 rounded-xl skeleton"></div>
      </div>
    {:else if error}
      <div
        class="rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm text-danger"
        role="alert"
      >
        <p class="font-semibold">No se puede abrir la caja</p>
        <p class="mt-1">{error}</p>
        <div class="mt-3">
          <Button variant="secondary" size="sm" onclick={load}>Reintentar</Button>
        </div>
      </div>
    {:else if me && !shift}
      {#if canOpen}
        <OpenShiftPanel
          branchId={branch.id}
          {canManageRegisters}
          onopened={() => {
            notice = 'Turno abierto. Ya puedes trabajar en tu caja.';
            void load();
          }}
        />
      {:else}
        <div
          class="rounded-xl border border-border bg-surface p-8 text-center text-sm text-foreground-muted"
        >
          No tienes un turno abierto y tu rol no permite abrir uno.
        </div>
      {/if}
    {:else if shift && detail}
      {#if detail.drawer_limit_reached && shift.status === 'open'}
        <div
          class="mb-4 rounded-xl border border-warning/30 bg-warning/10 p-3 text-sm text-foreground"
          role="alert"
        >
          La gaveta llegó a su límite de efectivo. Haz un retiro a caja fuerte.
        </div>
      {/if}

      {#if shift.status === 'counted'}
        <div class="rounded-xl border border-border bg-surface p-8 text-center">
          <p class="text-lg font-semibold text-foreground">Turno entregado</p>
          <p class="mt-1 text-sm text-foreground-muted">
            Contaste {formatMoney(shift.counted_cash)} en efectivo el {formatDateTime(
              shift.counted_at
            )}. Espera a que el supervisor revise el cierre.
          </p>
          <div class="mt-4"><Button variant="secondary" onclick={refresh}>Actualizar</Button></div>
        </div>
      {:else}
        {#if shift.status === 'recount'}
          <div
            class="mb-4 rounded-xl border border-danger/30 bg-danger/10 p-4 text-sm"
            role="alert"
          >
            <p class="font-semibold text-danger">El supervisor pidió recontar</p>
            <p class="mt-1 text-foreground">{shift.recount_reason}</p>
            {#if canClose}
              <div class="mt-3">
                <Button onclick={() => (counting = true)}>Volver a contar</Button>
              </div>
            {/if}
          </div>
        {/if}

        <div class="grid gap-4 lg:grid-cols-[1fr_320px]">
          <section
            class="rounded-xl border border-border bg-surface p-5"
            aria-labelledby="shift-title"
          >
            <h2 id="shift-title" class="text-base font-semibold text-foreground">Tu turno</h2>
            <dl class="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
              <div>
                <dt class="text-foreground-muted">Apertura</dt>
                <dd class="font-medium text-foreground">{formatDateTime(shift.opened_at)}</dd>
              </div>
              <div>
                <dt class="text-foreground-muted">Fondo inicial</dt>
                <dd class="font-medium tabular-nums text-foreground">
                  {formatMoney(shift.opening_float)}
                </dd>
              </div>
              <div>
                <dt class="text-foreground-muted">Movimientos</dt>
                <dd class="font-medium text-foreground">{detail.movements.length}</dd>
              </div>
            </dl>

            <h3 class="mt-6 text-sm font-semibold text-foreground">Movimientos de efectivo</h3>
            {#if detail.movements.length === 0}
              <p class="mt-2 text-sm text-foreground-muted">
                Todavía no hay entradas, salidas ni retiros.
              </p>
            {:else}
              <ul class="mt-2 divide-y divide-border">
                {#each detail.movements as movement (movement.id)}
                  <li class="flex items-start justify-between gap-3 py-2 text-sm">
                    <div class="min-w-0">
                      <p class="font-medium text-foreground">
                        {MOVEMENT_KIND[movement.kind].label}
                      </p>
                      <p class="truncate text-foreground-muted">
                        {movement.reason}{movement.authorized_by
                          ? ` · autorizó ${movement.authorized_by.name}`
                          : ''}
                      </p>
                      <p class="text-xs text-foreground-subtle">
                        {formatDateTime(movement.created_at)}
                      </p>
                    </div>
                    <span
                      class={`flex-none font-semibold tabular-nums ${MOVEMENT_KIND[movement.kind].sign < 0 ? 'text-danger' : 'text-success'}`}
                      >{MOVEMENT_KIND[movement.kind].sign < 0 ? '−' : '+'}{formatMoney(
                        movement.amount
                      )}</span
                    >
                  </li>
                {/each}
              </ul>
            {/if}
          </section>

          <aside class="space-y-3">
            {#if shift.status === 'open'}
              {#if canMove}
                {#each ['cash_in', 'cash_out', 'safe_drop'] as const as kind (kind)}
                  <button
                    type="button"
                    class="flex w-full items-center justify-between rounded-xl border border-border bg-surface px-4 py-3 text-left text-sm font-medium text-foreground hover:bg-surface-hover"
                    onclick={() => (movementKind = kind)}
                  >
                    {MOVEMENT_KIND[kind].label}
                    <span aria-hidden="true" class="text-foreground-subtle">›</span>
                  </button>
                {/each}
              {/if}
              {#if canClose}
                <Button size="lg" class="w-full" onclick={() => (counting = true)}>
                  Contar y entregar turno
                </Button>
              {/if}
            {/if}
          </aside>
        </div>
      {/if}

      {#if movementKind}
        <MovementDialog
          open={movementKind !== null}
          kind={movementKind}
          shiftId={shift.id}
          branchId={shift.branch_id}
          threshold={detail.register_detail.cash_out_approval_threshold}
          onclose={() => (movementKind = null)}
          onsaved={(movement) => {
            notice = `${MOVEMENT_KIND[movement.kind].label} de ${formatMoney(movement.amount)} registrada.`;
            movementKind = null;
            void refresh();
          }}
        />
      {/if}
      <CountDialog
        open={counting}
        {shift}
        onclose={() => (counting = false)}
        oncounted={() => {
          counting = false;
          notice = 'Conteo entregado. El supervisor revisará el cierre.';
          void refresh();
        }}
      />
    {/if}
  </div>
</div>

{#if me}
  <PinDialog
    open={pinOpen}
    hasPin={me.has_pin}
    onclose={() => (pinOpen = false)}
    onsaved={() => {
      pinOpen = false;
      notice = 'PIN guardado.';
      void refresh();
    }}
  />
{/if}
